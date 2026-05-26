# Authoritative Documentation Map

## Purpose

This document defines the authoritative documentation hierarchy for UAR so runtime behavior, governance semantics, replay continuity, and deployment guidance remain coherent as the repository grows.

## Authoritative Areas

| Area | Authority |
|---|---|
| Runtime state | docs/CURRENT_RUNTIME_STATE.md |
| Roadmap history | docs/ROADMAP_HISTORY.md |
| Dependencies | docs/DEPENDENCY_MATRIX.md |
| Contracts | docs/CONTRACT_VERSION.md |
| Runtime governance | docs/runtime-governance/ |
| Deployment | docs/runtime-governance/runtime-deployment.md |
| Runtime API | docs/runtime-governance/runtime-api.md |
| Runtime quickstart | docs/runtime-governance/runtime-quickstart.md |

## Rule

If lower-level docs conflict with this authority map or CURRENT_RUNTIME_STATE.md, update the lower-level docs or promote the new state explicitly.
