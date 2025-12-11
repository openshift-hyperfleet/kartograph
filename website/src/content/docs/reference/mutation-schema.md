---
title: Mutation Operation Schema
description: JSON Schema reference for mutation operations
---

## Overview

All mutation operations follow a strict JSON schema. This ensures consistency and enables validation at both the Extraction and Graph boundaries.

## Schema Location

The complete JSON Schema is available at: jsell:TODO:<add link to json schema viewer>

## Operation Types

### DEFINE

```json
{
  "op": "DEFINE",
  "type": "node" | "edge",
  "label": "string",
  "description": "string",
  "example_file_path": "string",
  "example_in_file_path": "string",
  "required_properties": ["array", "of", "strings"]
}
```

:::note
`required_properties` is a set of properties required when `CREATE`ing a node/edge
of the given `label`. These properties are required _in addition to_ any global
node/edge properties.
:::

### CREATE

```json
{
  "op": "CREATE",
  "type": "node" | "edge",
  "id": "string",
  "label": "string",
  "set_properties": {
    "data_source_id": "required",
    "source_path": "required",
    "slug": "required" // Only required for `CREATE node` operations
    ...
  }
}
```

For edges, add:
```json
{
  "start_id": "string",
  "end_id": "string"
}
```

### UPDATE

```json
{
  "op": "UPDATE",
  "type": "node" | "edge",
  "id": "string",
  "set_properties": {},
  "remove_properties": []
}
```

### DELETE

```json
{
  "op": "DELETE",
  "type": "node" | "edge",
  "id": "string"
}
```

## Required Properties

All node and edge CREATEs must include:

- `data_source_id` - Identifies which data source this entity came from
- `source_path` - The file path within the data source

## Validation

jsell:TODO:<add link to json schema viewer>

## Next Steps

- See [Extraction → Graph Mutations](/guides/extraction-mutations/) for examples
- Read about [Secure Enclave IDs](/reference/secure-enclave/)
