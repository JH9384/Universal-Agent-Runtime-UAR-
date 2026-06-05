---
description: Always use the Cwd parameter instead of cd commands when running commands in subdirectories
tags: [commands, shell, cd, cwd, best-practices]
---

# Rule: Use Cwd Parameter, Never cd Commands

## Problem

When running commands that need to execute in a subdirectory (e.g., running `npm test` in `apps/operator-dashboard`), repeatedly calling `cd` before each command is error-prone and creates brittle sequences. More importantly, the `run_command` tool supports a `Cwd` parameter that should always be used instead.

## The Failure Mode

Repeating the same command without `Cwd` when the previous attempt from root failed:

```typescript
run_command({ CommandLine: "npx vitest run" })  // fails — wrong directory
run_command({ CommandLine: "npx vitest run" })  // fails — still wrong directory
run_command({ CommandLine: "npx vitest run" })  // fails — STILL wrong directory
```

## The Fix

Always pass `Cwd` when the command must run in a specific directory:

```typescript
run_command({
  CommandLine: "npx vitest run",
  Cwd: "/Volumes/Sabrent SSD/Projects/Universal-Agent-Runtime-UAR-/apps/operator-dashboard"
})
```

## CRITICAL: The Say-Do Gap

This rule exists because of a specific failure mode: **thinking about using `Cwd` but not actually including it in the tool call**. If you find yourself saying "I'll use `Cwd` this time" — STOP. Verify the actual tool call JSON includes `Cwd` before emitting it. The thought is not the action.

## Fallback When Cwd Cannot Be Used

If `Cwd` cannot be included (e.g., persistent tool-use failure), wrap the command in `bash -c` with an internal `cd`:

```bash
bash -c 'cd "/path/to/project/apps/foo" && npx vitest run 2>&1'
```

This is acceptable ONLY when `Cwd` has been attempted and failed multiple times.

## Checklist

- [ ] If a command needs to run in a subdirectory, use `Cwd`, never `cd`
- [ ] If a command failed because of a missing file/package, check the working directory first
- [ ] Never repeat the exact same failing command without changing parameters
- [ ] Before emitting `run_command`, verify `Cwd` is present in the JSON if the command needs a specific directory
