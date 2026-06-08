# MCP Adapter

D4E hardens the UAR MCP adapter into a read-only inspection surface by default.

The adapter is for external agent clients that need to inspect UAR state without being granted mutation, shell, filesystem, or arbitrary skill execution authority.

## Security posture

Default stance:

```text
deny-by-default
read-only tools only
no shell execution
no file writes
no bulk delete
no runtime mutation
no automatic exposure of registered skills
```

The previous MCP scaffold exposed every registered UAR skill as an MCP tool. D4E replaces that with a small allowlist of diagnostic tools.

## Tool allowlist

```text
uar.health
uar.mission_control
uar.list_runs
uar.get_run
uar.replay_summary
uar.certification_status
uar.burnin_history
uar.failure_hotspots
```

Tools call the running UAR API through `UAR_MCP_API_URL`.

## Commands

Validate the MCP registry without starting a client:

```bash
make mcp-smoke
```

Run the stdio MCP server:

```bash
make mcp-server
```

Equivalent direct command:

```bash
python -m uar.mcp.server
```

## Environment

```text
UAR_MCP_API_URL      Base UAR API URL, default http://127.0.0.1:8000
UAR_MCP_API_TOKEN    Optional bearer token for guarded endpoints
UAR_MCP_TIMEOUT      HTTP timeout in seconds, default 5
```

## Client configuration example

Example shape for an MCP client that supports stdio servers:

```json
{
  "mcpServers": {
    "uar-readonly": {
      "command": "python",
      "args": ["-m", "uar.mcp.server"],
      "env": {
        "UAR_MCP_API_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

## Promotion path

Additional MCP tools should be admitted only if they pass all of the following:

1. The tool is explicitly allowlisted.
2. The tool has a narrow JSON schema.
3. The tool is auditable.
4. The tool does not mutate runtime state unless a separate governance gate approves it.
5. The tool has tests for unauthenticated, unauthorized, malformed, and happy-path behavior.

Runtime-mutating tools such as `run_goal`, delete operations, shell commands, or filesystem writes should remain out of the default MCP server.
