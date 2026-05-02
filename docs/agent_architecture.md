# UAR Agent Architecture

## Layers

- Runtime: deterministic execution (existing)
- Skills: reusable behavior definitions
- Planner: selects skill
- Strategy: tries multiple runtimes
- Memory: stores outcomes
- Context: shapes decisions

## Flow

Document → Sections → Planner → Strategy → Runtime → Result → Memory

## Next Steps

- Wire strategy into execution loop
- Upgrade memory to SQLite
- Add UI visualization for runs
