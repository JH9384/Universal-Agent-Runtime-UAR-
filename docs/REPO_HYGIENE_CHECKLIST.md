# Repository Hygiene Checklist

## Core Rules
- Never run git commands outside the repo
- Never commit without reviewing `git diff`
- Never use `git add .` blindly

## Local Setup
- Repo cloned locally
- Correct branch checked out
- Backend runs (`/health` passes)
- Frontend builds successfully

## Backend
- Tests pass (`pytest`)
- Sandbox wiring applied and verified
- No large diffs in protected files

## Frontend
- `npm install` succeeds
- `npm run build` succeeds
- No TypeScript errors

## CI
- All workflows pass
- Destructive diff guard passes
- Frontend build passes

## Functional Gate
- Create object
- Run runtime
- Result appears
- Trace works
- Integrity verify works

## Do NOT proceed if
- UI broken
- Backend errors
- CI failing
- Large diff in core files
