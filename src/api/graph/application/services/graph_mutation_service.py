"""Graph mutation service for write operations.

Application service for applying mutations to the graph, including
handling DEFINE operations and delegating to the infrastructure layer.
"""

from __future__ import annotations

import json

from graph.application.observability import (
    DefaultGraphServiceProbe,
    GraphServiceProbe,
)
from graph.domain.value_objects import (
    MutationOperation,
    MutationResult,
)
from graph.ports.repositories import (
    IMutationApplier,
    ITypeDefinitionRepository,
)


class GraphMutationService:
    """Application service for graph mutation operations.

    This service orchestrates the application of mutations to the graph,
    including handling DEFINE operations and delegating to the infrastructure
    layer for actual database operations.
    """

    def __init__(
        self,
        mutation_applier: IMutationApplier,
        type_definition_repository: ITypeDefinitionRepository,
        probe: GraphServiceProbe | None = None,
    ):
        """Initialize the service.

        Args:
            mutation_applier: Component for applying mutations to the database.
            type_definition_repository: Repository for storing type definitions.
            probe: Optional domain probe for observability.
        """
        self._mutation_applier = mutation_applier
        self._type_definition_repository = type_definition_repository
        self._probe = probe or DefaultGraphServiceProbe()

    def apply_mutations(
        self,
        operations: list[MutationOperation],
    ) -> MutationResult:
        """Apply a batch of mutation operations.

        DEFINE operations are stored in the type definition repository.
        All operations are then delegated to the mutation applier for
        execution in the correct order.

        Validates that CREATE operations have corresponding type definitions.

        Args:
            operations: List of mutation operations to apply.

        Returns:
            MutationResult with success status and operation count.
        """
        # Collect DEFINE operations from this batch
        defines_in_batch = {
            (op.label, op.type)
            for op in operations
            if op.op == "DEFINE" and op.label is not None
        }

        # Validate CREATE operations have type definitions and required properties
        for op in operations:
            if op.op == "CREATE" and op.label is not None:
                # Check if type is defined in this batch or in repository
                is_defined_in_batch = (op.label, op.type) in defines_in_batch
                type_def = self._type_definition_repository.get(op.label, op.type)

                if not is_defined_in_batch and type_def is None:
                    error_msg = (
                        f"Type '{op.label}' for {op.type} is not defined. "
                        f"CREATE operations require a prior DEFINE operation."
                    )
                    return MutationResult(
                        success=False,
                        operations_applied=0,
                        errors=[error_msg],
                    )

                # Validate required properties if type definition exists in repository
                if type_def is not None:
                    provided_props = set(
                        op.set_properties.keys() if op.set_properties else []
                    )
                    required_props = set(type_def.required_properties)
                    missing_props = required_props - provided_props

                    if missing_props:
                        error_msg = (
                            f"CREATE operation for {op.type} '{op.label}' is missing "
                            f"required properties: {', '.join(sorted(missing_props))}"
                        )
                        return MutationResult(
                            success=False,
                            operations_applied=0,
                            errors=[error_msg],
                        )

                # Validate required properties for types defined in current batch
                if is_defined_in_batch and type_def is None:
                    # Find the DEFINE operation in the current batch
                    define_op = next(
                        (
                            o
                            for o in operations
                            if o.op == "DEFINE"
                            and o.label == op.label
                            and o.type == op.type
                        ),
                        None,
                    )
                    if define_op and define_op.required_properties:
                        provided_props = set(
                            op.set_properties.keys() if op.set_properties else []
                        )
                        required_props = set(define_op.required_properties)
                        missing_props = required_props - provided_props

                        if missing_props:
                            error_msg = (
                                f"CREATE operation for {op.type} '{op.label}' is missing "
                                f"required properties: {', '.join(sorted(missing_props))}"
                            )
                            return MutationResult(
                                success=False,
                                operations_applied=0,
                                errors=[error_msg],
                            )

        # Store DEFINE operations in the repository
        for op in operations:
            if op.op == "DEFINE":
                type_def = op.to_type_definition()
                self._type_definition_repository.save(type_def)

        # Delegate to mutation applier
        result = self._mutation_applier.apply_batch(operations)

        # Emit probe event
        self._probe.mutations_applied(
            operations_applied=result.operations_applied,
            success=result.success,
        )

        return result

    def apply_mutations_from_jsonl(
        self,
        jsonl_content: str,
    ) -> MutationResult:
        """Parse JSONL content and apply mutations.

        Each line in the JSONL should be a valid MutationOperation JSON object.
        Empty lines and whitespace-only lines are ignored.

        Args:
            jsonl_content: JSONL string with one operation per line.

        Returns:
            MutationResult with success status and operation count.
        """
        try:
            operations = []
            for line in jsonl_content.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # Parse JSON line
                operation_dict = json.loads(line)

                # Create MutationOperation (Pydantic will validate)
                operation = MutationOperation(**operation_dict)
                operations.append(operation)

            # Apply all parsed operations
            return self.apply_mutations(operations)

        except json.JSONDecodeError as e:
            return MutationResult(
                success=False,
                operations_applied=0,
                errors=[f"JSON parse error: {str(e)}"],
            )
        except Exception as e:
            return MutationResult(
                success=False,
                operations_applied=0,
                errors=[str(e)],
            )
