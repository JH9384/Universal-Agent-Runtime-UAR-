# Recipe Condition Syntax Guide

## Overview

Recipes in UAR can include conditional execution logic. A recipe with a `condition` will only execute if the condition evaluates to `true` based on the current execution context (previously executed skill outputs).

## Condition Format

Conditions are JSON objects with the following structure:

```json
{
  "key": "context.data.key_name",
  "exists": true
}
```

Or:

```json
{
  "key": "context.data.key_name",
  "equals": "expected_value"
}
```

Or:

```json
{
  "key": "context.data.key_name",
  "not_equals": "unwanted_value"
}
```

## Supported Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `exists` | True if the key exists in context data | `"exists": true` |
| `equals` | True if the key's value equals the given value | `"equals": "pdf"` |
| `not_equals` | True if the key's value does not equal the given value | `"not_equals": ""` |

## How Conditions Work

1. Before a recipe executes, the executor evaluates its condition against `ctx.data`
2. `ctx.data` contains outputs from all previously executed skills
3. If the condition is `false`, the recipe emits a `recipe_skipped` event and its skills are not executed
4. If no condition is specified, the recipe always executes

## Key Resolution

The `key` field references a top-level key in the execution context. Context data is populated by skill outputs:

```python
# After doc_ingest runs:
ctx.data = {
    "doc_ingest": {
        "documents": [...],
        "document_count": 5,
        "format": "pdf"
    }
}
```

The key `"doc_ingest"` would refer to this entire output object.

## Examples

### Check if a skill produced output

Only run the `review` recipe if `doc_ingest` has been executed:

```json
{
  "id": "review",
  "label": "Review documents",
  "skills": ["doc_ingest", "ollama_generate"],
  "condition": {
    "key": "doc_ingest",
    "exists": true
  }
}
```

### Check output format

Only run OCR if the detected format is an image:

```json
{
  "id": "ocr_pipeline",
  "label": "OCR processing",
  "skills": ["tesseract_ocr", "ollama_generate"],
  "condition": {
    "key": "doc_ingest",
    "equals": "image"
  }
}
```

### Skip if already processed

Skip if a previous recipe already produced a dependency map:

```json
{
  "id": "deps",
  "label": "Dependency analysis",
  "skills": ["doc_ingest", "dependency_map", "sum_review"],
  "condition": {
    "key": "dependency_map",
    "exists": false
  }
}
```

### Using with execution_order

Conditions are evaluated in the unified execution order:

```json
{
  "goal": "Analyze project",
  "execution_order": [
    {"type": "skill", "content": "doc_ingest", "id": "s1"},
    {"type": "recipe", "content": "review", "id": "r1"},
    {"type": "recipe", "content": "deps", "id": "r2"}
  ]
}
```

In this case:
1. `doc_ingest` runs first (no condition)
2. `review` checks its condition against `ctx.data` (which now contains `doc_ingest` output)
3. `deps` checks its condition against `ctx.data` (which contains `doc_ingest` and possibly `review` outputs)

## Limitations

- **No nested keys**: Conditions only check top-level keys in `ctx.data`. You cannot reference nested fields like `doc_ingest.format`.
- **No comparison operators**: Only `exists`, `equals`, and `not_equals` are supported. No `<`, `>`, `contains`, or regex matching.
- **No logical combinators**: Cannot combine multiple conditions with `and`/`or`.
- **Static at expansion time**: Conditions are evaluated from the recipe definition, not dynamically computed.

## Event: recipe_skipped

When a condition evaluates to false, the executor emits:

```json
{
  "type": "recipe_skipped",
  "payload": {
    "recipe_id": "deps",
    "instance_id": "r2",
    "reason": "condition_false"
  }
}
```

This event is delivered to the client but does not stop execution of subsequent items.

## Best Practices

1. **Use conditions sparingly**: Overusing conditions makes execution flows hard to reason about
2. **Prefer explicit ordering**: Use `execution_order` to control sequence rather than relying on conditions
3. **Document conditions**: Add comments or recipe hints explaining when a recipe will be skipped
4. **Test both paths**: Verify your recipe works both when the condition is true and false

## Future Enhancements

Planned additions to the condition system:
- Nested key access (`doc_ingest.format`)
- Numeric comparisons (`>`, `<`, `>=`, `<=`)
- Array membership (`in`, `contains`)
- Logical combinators (`and`, `or`, `not`)

These are tracked in the project backlog and may be implemented in future releases.
