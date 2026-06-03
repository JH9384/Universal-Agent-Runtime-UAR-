---
description: Prevent repeated identical tool-call loops
tags: [meta, discipline]
---

# No Repeated Tool-Call Loops

## Rule

If a `run_command` (or any tool call) has just failed or produced the same result **three times in a row**, STOP.

1. **Do not** issue the same tool call again.
2. **Escalate**: Explain to the user what is blocking you and ask for help, or switch to a fundamentally different approach.
3. If the loop involves `run_command`, check whether you forgot the `Cwd` parameter, whether the command needs different flags, or whether you should read a file instead.

## Anti-patterns

- Re-issuing `run_command` with the exact same `CommandLine` more than twice.
- Re-issuing `edit` with the same `old_string` after it already failed.
- Re-issuing `read_file` on the same path expecting different content.

## Good pattern

After 2 identical failures, switch tactics: read config, grep for clues, or ask the user.
