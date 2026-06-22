# Obsidian MCP server — project context

## Purpose

An MCP (Model Context Protocol) server that exposes an Obsidian vault to Claude via direct filesystem access — no Obsidian app dependency, no plugin. Runs as a local stdio subprocess spawned by an MCP client (Claude Desktop or Claude Code).

## Architecture decisions already made — do not relitigate

- **Vault access: direct filesystem**, not the Obsidian Local REST API plugin. Rationale: works headless, no runtime dependency on Obsidian being open, no plugin/auth to maintain. Tradeoff knowingly accepted: no access to Obsidian's resolved link graph, Dataview engine, or "active file" state. Revisit only if a future requirement explicitly needs live Obsidian state.
- **Language: Python**, using the official `mcp` SDK (FastMCP decorator API), not TypeScript. Rationale: matches the existing stack, less boilerplate per tool (schema auto-generated from type hints), and `python-frontmatter` makes YAML frontmatter handling trivial.
- **Transport: stdio.** Logging must go to stderr, never stdout — stdout is the JSON-RPC channel and any stray `print()` will corrupt the protocol.

## Scope — v1 (this build)

Tools:

- `list_notes(folder: str = "", recursive: bool = True) -> list[str]` — vault-relative paths of `.md` files.
- `read_note(path: str) -> NoteContent` — returns `{frontmatter: dict, content: str}`.
- `create_note(path: str, content: str, frontmatter: dict = {}) -> str` — fails if path already exists; no silent overwrite.
- `update_note(path: str, content: str, mode: Literal["overwrite", "append", "prepend"] = "overwrite") -> str`
- `update_frontmatter(path: str, updates: dict, delete_keys: list[str] = []) -> dict` — shallow merge into existing frontmatter; body content untouched.

Explicitly OUT of scope for v1 — do not implement unless asked, flag to Ema if they come up: full-text search, tag aggregation, backlinks/link graph, Dataview queries. These need either an index or the Local REST API plugin.

## Non-negotiable: path safety

Every tool takes vault-relative paths. Before any read/write, resolve against the vault root and verify the resolved path is still inside it:

```python
from pathlib import Path

def resolve_safe_path(vault_root: Path, relative_path: str) -> Path:
    candidate = (vault_root / relative_path).resolve()
    if not candidate.is_relative_to(vault_root.resolve()):
        raise ValueError(f"Path '{relative_path}' escapes vault root")
    return candidate
```

Reject with a clear error otherwise. This must not regress — an LLM-facing filesystem write tool is real attack surface (path traversal via `../../`). Write tests for this before anything else.

**Implementation status: verified correct.** Reviewed against the actual `vault.py` source, not just description:
- Comparison is `Path.is_relative_to(Path)`, never stringified — no sibling-prefix false positive (e.g. `/vault` vs `/vault-evil`).
- Absolute-path injection (`/etc/passwd`) is caught: `Path.__truediv__` discards the left operand when the right is absolute, but `.resolve()` runs after the join and the comparison against the pre-resolved `self.vault_root` catches it.
- Symlinks are neutralised by `.resolve()` before comparison.
- Known, accepted tradeoff: `list_notes` uses `relative_to()` which is purely lexical — a symlink inside the vault pointing outside it will still show up in a listing (filename only, no content exposure). The actual block happens correctly the moment `read_note`/`update_note`/`create_note`/`update_frontmatter` resolves that same path. Not a bug, just documented so it isn't mistaken for one later.

## Frontmatter merge semantics

`update_frontmatter` is a **shallow merge**, not an overwrite: existing keys not mentioned in `updates` are preserved. `delete_keys` is the only way to remove a key. Don't stringify values on the way in/out — `python-frontmatter` round-trips YAML types natively (lists stay lists, etc.).

**Order of operations for `merge_frontmatter(existing, updates, delete_keys)`:** copy `existing` (never mutate the caller's dict), apply `updates` on top, then remove `delete_keys`. If a key appears in both `updates` and `delete_keys`, deletion wins — the key ends up absent. This needs to be an explicit test case, not just implied behavior.

## Directory layout

```plaintext
obsidian-mcp/
├── pyproject.toml
├── README.md
├── CLAUDE.md                  # this file
├── .env.example
├── src/
│   └── obsidian_mcp/
│       ├── __init__.py
│       ├── server.py          # FastMCP instance, tool registration, entrypoint
│       ├── config.py          # env var loading + startup validation of vault path
│       ├── vault.py           # VaultManager: path guard, file read/write
│       └── frontmatter_utils.py  # parse/merge/write, wraps python-frontmatter
└── tests/
    └── test_vault.py          # path-traversal guard tests are priority #1
```

## Dependencies

Runtime: `mcp[cli]`, `python-frontmatter`, `pydantic>=2`
Dev: `pytest`, `pytest-asyncio`

## Config

Single env var: `OBSIDIAN_VAULT_PATH` — absolute path to vault root. `config.py` validates on startup that it exists and is a directory; fail fast and loud, don't let a broken path surface later as a confusing per-tool error.

## Setup commands

```bash
uv venv
uv pip install -e ".[dev]"
```

## Claude Desktop / Code config (once built)

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/obsidian-mcp", "run", "obsidian-mcp"],
      "env": { "OBSIDIAN_VAULT_PATH": "/absolute/path/to/vault" }
    }
  }
}
```

## Build status

### Done
- `pyproject.toml` — hatchling build, runtime deps (`mcp[cli]`, `python-frontmatter`, `pydantic>=2`), dev deps (`pytest`, `pytest-asyncio`), entrypoint `obsidian-mcp = "obsidian_mcp.server:main"`, `asyncio_mode = "auto"` for pytest.
- `.env.example` — placeholder for `OBSIDIAN_VAULT_PATH`.
- `config.py` — loads `OBSIDIAN_VAULT_PATH`, validates exists + is_dir, returns `path.resolve()`. Fails fast with clear RuntimeError.
- `vault.py` — path-safety logic verified correct. All read/write goes through `_load()`/`_dump()` helpers that use `frontmatter.parse()` + manual `Post` construction to avoid a library bug where `Post(content, handler, **metadata)` crashes if metadata contains a `handler` key.
- `frontmatter_utils.py` — `merge_frontmatter(existing, updates, delete_keys)` pure function; copy-on-write, delete wins over update.
- `tests/test_vault.py` — 35 tests, 1 skipped (symlink test requires elevated privileges on Windows). Covers: path-traversal guard (relative, absolute, sibling-prefix, empty path, symlink), list/read/create/update/update_frontmatter CRUD, and all `merge_frontmatter` edge cases from CLAUDE.md.
- `server.py` — FastMCP wiring; all 5 tools registered with `@mcp.tool()`.

### Next

- Smoke test via `mcp dev src/obsidian_mcp/server.py` before touching Claude Desktop/Code config.
- Once smoke test passes, update Claude Desktop/Code config to point at this server.

## Confirmed decisions

- `create_note` fails loudly (`FileExistsError`) if the path already exists — no silent overwrite. Confirmed by Ema.

## Open questions for Ema — ask, don't assume

- Any vault-specific naming conventions (e.g. daily-note date paths) that should constrain or validate `create_note` paths.