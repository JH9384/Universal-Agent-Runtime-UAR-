# ADR-003: Skill Registry Pattern

## Status
Accepted

## Context
The UAR system needs to manage and execute a dynamic set of skills (AI capabilities). Skills can be:
- Added by developers
- Extended by plugins
- Selected by users at runtime
- Composed into recipes

Without a centralized registry, the system would have:
- Tight coupling between executor and skills
- No way to discover available skills
- Difficulties with skill validation
- No single source of truth for skill metadata

## Decision
Implement a centralized Skill Registry with decorator-based registration.

### Implementation Details

1. **Registry Module** (`uar/core/registry.py`)
   - `SkillRegistry` class with registration methods
   - `@register_skill` decorator for skill functions
   - Thread-safe skill storage
   - Validation on registration

2. **Decorator Pattern**
   - Skills register themselves at module import time
   - Decorator validates skill name and function
   - Prevents duplicate registrations
   - Provides metadata about available skills

3. **Integration**
   - Executor queries registry for skill functions
   - API endpoints can list available skills
   - Recipe system references skill names from registry

### Features
- `get(name)`: Retrieve skill function
- `list()`: List all registered skill names (cached)
- `is_registered(name)`: Check if skill exists
- Validation on registration (name format, callable check)

## Consequences

### Positive
- Single source of truth for skills
- Loose coupling between executor and skills
- Easy to add new skills
- Built-in validation prevents errors
- Discoverable skill inventory

### Negative
- All skills must be imported to register
- Cannot dynamically register skills at runtime (currently)
- Registry grows with all imported skills
- No skill metadata beyond name and function

### Alternatives Considered
1. **Manual registration**: More error-prone, boilerplate
2. **Configuration-based**: Harder to maintain, less flexible
3. **Plugin system**: More complex, not needed currently

## References
- Implementation: `uar/core/registry.py`
- Usage: Skills use `@register_skill("skill_name")` decorator
