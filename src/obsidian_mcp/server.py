from __future__ import annotations

import sys
from typing import Literal

from mcp.server.fastmcp import FastMCP

from obsidian_mcp.config import load_vault_path
from obsidian_mcp.vault import VaultManager

mcp = FastMCP("obsidian")
_vault: VaultManager | None = None


def get_vault() -> VaultManager:
    global _vault
    if _vault is None:
        _vault = VaultManager(load_vault_path())
    return _vault


@mcp.tool()
def list_notes(folder: str = "", recursive: bool = True) -> list[str]:
    """List vault-relative paths of all .md files."""
    return get_vault().list_notes(folder=folder, recursive=recursive)


@mcp.tool()
def read_note(path: str) -> dict:
    """Read a note and return its frontmatter and body content."""
    return get_vault().read_note(path)


@mcp.tool()
def create_note(path: str, content: str, frontmatter_data: dict = {}) -> str:
    """Create a new note. Fails if the path already exists."""
    return get_vault().create_note(path, content, frontmatter_data or None)


@mcp.tool()
def update_note(
    path: str,
    content: str,
    mode: Literal["overwrite", "append", "prepend"] = "overwrite",
) -> str:
    """Update an existing note's body content."""
    return get_vault().update_note(path, content, mode=mode)


@mcp.tool()
def update_frontmatter(
    path: str,
    updates: dict,
    delete_keys: list[str] = [],
) -> dict:
    """Shallow-merge updates into a note's frontmatter; optionally delete keys."""
    return get_vault().update_frontmatter(path, updates, delete_keys=delete_keys or [])


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
