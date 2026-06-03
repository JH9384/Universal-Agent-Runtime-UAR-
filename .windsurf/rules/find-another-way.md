---
description: When a command fails repeatedly, find another way
tags: [meta, discipline, problem-solving]
---

# Find Another Way

## Rule

If a command has failed **twice** with the same error, STOP running it.

1. **Do not** run the same command a third time.
2. **Analyze** why it failed. Common causes:
   - Wrong working directory → use `Cwd` parameter
   - Missing dependencies → check if already installed elsewhere
   - Wrong tool → use a different tool (e.g., `python -m pytest` instead of `pytest`)
   - Environment issue → check `PATH`, `which`, `pwd`
3. **Find another way** to achieve the same goal:
   - Use an absolute path to the binary
   - Use a different tool that achieves the same result
   - Do the task manually (e.g., read file instead of grep)
   - Ask the user for help if truly stuck

## Anti-patterns

- Running `npm install` repeatedly when it fails with ENOENT
- Running `pytest` repeatedly when the venv isn't activated
- Running the same `curl` command that returns 404

## Good pattern

After 2 failures, switch tactics immediately. Never retry more than twice.
