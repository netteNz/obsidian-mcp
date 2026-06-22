# obsidian-mcp

An MCP server that exposes an Obsidian vault to Claude via direct filesystem access. No Obsidian app required, no plugin, no API key.

## Tools

| Tool | Description |
|------|-------------|
| `list_notes` | List vault-relative paths of `.md` files in a folder |
| `read_note` | Read a note's frontmatter and body content |
| `create_note` | Create a new note (fails if path already exists) |
| `update_note` | Overwrite, append to, or prepend to a note's body |
| `update_frontmatter` | Shallow-merge key/value updates into a note's frontmatter |

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo>
cd obsidian-mcp
uv venv
uv pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set your vault path:

```
OBSIDIAN_VAULT_PATH=/absolute/path/to/your/vault
```

## Claude Desktop / Claude Code config

Add to your MCP config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/obsidian-mcp", "run", "obsidian-mcp"],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/absolute/path/to/your/vault"
      }
    }
  }
}
```

## Smoke test

```bash
OBSIDIAN_VAULT_PATH=/path/to/vault mcp dev src/obsidian_mcp/server.py
```

## Run tests

```bash
python -m pytest tests/ -v
```

## Notes

- All paths are vault-relative. Path traversal attempts are rejected.
- `update_frontmatter` is a shallow merge — unlisted keys are preserved. Use `delete_keys` to remove a key.
- Out of scope for v1: full-text search, tag aggregation, backlinks, Dataview queries.
