# Next Unit of Work Workflow

This workflow returns a single, verifiable, unit of development work.

This is a read-only workflow.

## Workflow

1. Thoroughly read every spec in specs/
2. Thoroughly read the current implementation in the codebase.
3. Determine gaps between the specs and the implementation.
4. Organize the gaps by dependency.
5. Return the gap that is most critical, and does not depend on any other gaps. Format it as a verifiable
   unit of work, and include required testing scenarios. Do not provide implementation details. Return
   the spec path, the spec excerpt (if applicable), and the testing scenarios that must pass.
