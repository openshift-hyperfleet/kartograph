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
    get_system_properties_for_entity,
    MutationOperation,
    MutationResult,
    TypeDefinition,
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
                        # Get entity-specific system properties
                        system_props = get_system_properties_for_entity(op.type)

                        provided_props = set(
                            op.set_properties.keys() if op.set_properties else []
                        )
                        # Include system properties in validation!
                        required_props = (
                            set(define_op.required_properties) | system_props
                        )
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
        refined_ops: list[MutationOperation] = []
        for op in operations:
            if op.op == "DEFINE":
                # Get entity-specific system properties
                system_props = get_system_properties_for_entity(op.type)

                updated_op = op.model_copy(
                    update={
                        "required_properties": (op.required_properties or set())
                        | system_props
                    }
                )
                type_def = updated_op.to_type_definition()

                self._type_definition_repository.save(type_def)

                refined_ops.append(updated_op)
            else:
                refined_ops.append(op)

        del operations

        # Delegate to mutation applier
        result = self._mutation_applier.apply_batch(refined_ops)

        # Schema learning: Only discover optional properties if mutations succeeded
        if result.success:
            self._discover_optional_properties(refined_ops)

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
            lines = jsonl_content.strip().split("\n")

            for line_num, line in enumerate(lines, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    # Parse JSON line
                    operation_dict = json.loads(line)

                    # Create MutationOperation (Pydantic will validate)
                    operation = MutationOperation(**operation_dict)
                    operations.append(operation)

                except json.JSONDecodeError as e:
                    # Include line number and snippet in error
                    line_preview = line[:100] + "..." if len(line) > 100 else line
                    return MutationResult(
                        success=False,
                        operations_applied=0,
                        errors=[
                            f"JSON parse error on line {line_num}: {str(e)}",
                            f"Line content: {line_preview}",
                        ],
                    )
                except Exception as e:
                    # Validation error from Pydantic
                    line_preview = line[:100] + "..." if len(line) > 100 else line
                    return MutationResult(
                        success=False,
                        operations_applied=0,
                        errors=[
                            f"Validation error on line {line_num}: {str(e)}",
                            f"Line content: {line_preview}",
                        ],
                    )

            # Apply all parsed operations
            return self.apply_mutations(operations)

        except Exception as e:
            # Catch-all for unexpected errors
            return MutationResult(
                success=False,
                operations_applied=0,
                errors=[f"Unexpected error: {str(e)}"],
            )

    def _discover_optional_properties(
        self,
        operations: list[MutationOperation],
    ) -> None:
        """Discover and store optional properties from CREATE and UPDATE operations.

        Both CREATE and UPDATE can introduce new properties to entities. When either
        operation provides properties beyond required_properties, those extra
        properties are added to the type definition's optional_properties.

        This supports incremental entity discovery where:
        - CREATE represents entity discovery (e.g., AI agent finding entities in files)
        - UPDATE represents entity modification (e.g., deterministic processor corrections)

        Both operations add properties incrementally, so both should contribute to
        schema learning.

        System properties (via get_system_properties_for_entity) are excluded.

        Args:
            operations: List of mutation operations to analyze
        """

        for op in operations:
            # Schema learning works for both CREATE and UPDATE
            # Both can add properties, so both should update the schema
            if op.op not in ("CREATE", "UPDATE"):
                continue

            # Need label to look up type definition
            if op.label is None or op.set_properties is None:
                continue

            # Get existing type definition
            type_def = self._type_definition_repository.get(op.label, op.type)
            if type_def is None:
                continue

            # Calculate extra properties
            provided_props = set(op.set_properties.keys())

            # Get entity-specific system properties
            system_props = get_system_properties_for_entity(op.type)

            required_props = type_def.required_properties | system_props
            existing_optional = set(type_def.optional_properties)

            # Extra props = provided - required - already_optional
            extra_props = provided_props - required_props - existing_optional

            if not extra_props:
                # No new optional properties discovered
                continue

            # Create updated type definition with merged optional properties
            updated_type_def = TypeDefinition(
                label=type_def.label,
                entity_type=type_def.entity_type,
                description=type_def.description,
                example_file_path=type_def.example_file_path,
                example_in_file_path=type_def.example_in_file_path,
                required_properties=type_def.required_properties,
                optional_properties=existing_optional | extra_props,
            )

            # Save updated type definition
            self._type_definition_repository.save(updated_type_def)
