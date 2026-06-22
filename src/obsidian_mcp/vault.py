from __future__ import annotations

from pathlib import Path
from typing import Literal

import frontmatter

from obsidian_mcp.frontmatter_utils import merge_frontmatter


def _load(full_path: Path) -> tuple[dict, str]:
    """Parse a note file, returning (metadata, content) without constructing a Post.

    Using frontmatter.parse() avoids the Post(content, handler, **metadata) call
    in frontmatter.load(), which crashes when a note has 'handler' as a frontmatter key.
    """
    text = full_path.read_text(encoding="utf-8")
    metadata, content = frontmatter.parse(text)
    return dict(metadata), content


def _dump(metadata: dict, content: str) -> str:
    post = frontmatter.Post(content)
    post.metadata = metadata
    return frontmatter.dumps(post)


class VaultManager:
    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root.resolve()

    def resolve_safe_path(self, relative_path: str) -> Path:
        candidate = (self.vault_root / relative_path).resolve()
        if not candidate.is_relative_to(self.vault_root):
            raise ValueError(f"Path '{relative_path}' escapes vault root")
        return candidate

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list_notes(self, folder: str = "", recursive: bool = True) -> list[str]:
        base = self.resolve_safe_path(folder) if folder else self.vault_root
        if not base.is_dir():
            raise ValueError(f"Folder not found: {folder!r}")
        pattern = "**/*.md" if recursive else "*.md"
        return sorted(
            p.relative_to(self.vault_root).as_posix()
            for p in base.glob(pattern)
            if p.is_file()
        )

    def read_note(self, path: str) -> dict:
        full_path = self.resolve_safe_path(path)
        if not full_path.is_file():
            raise FileNotFoundError(f"Note not found: {path!r}")
        metadata, content = _load(full_path)
        return {"frontmatter": metadata, "content": content}

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create_note(
        self,
        path: str,
        content: str,
        frontmatter_data: dict | None = None,
    ) -> str:
        full_path = self.resolve_safe_path(path)
        if full_path.exists():
            raise FileExistsError(f"Note already exists: {path!r}")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(_dump(frontmatter_data or {}, content), encoding="utf-8")
        return path

    def update_note(
        self,
        path: str,
        content: str,
        mode: Literal["overwrite", "append", "prepend"] = "overwrite",
    ) -> str:
        full_path = self.resolve_safe_path(path)
        if not full_path.is_file():
            raise FileNotFoundError(f"Note not found: {path!r}")
        metadata, existing_content = _load(full_path)
        if mode == "overwrite":
            new_content = content
        elif mode == "append":
            new_content = existing_content + "\n" + content
        else:  # prepend
            new_content = content + "\n" + existing_content
        full_path.write_text(_dump(metadata, new_content), encoding="utf-8")
        return path

    def update_frontmatter(
        self,
        path: str,
        updates: dict,
        delete_keys: list[str] | None = None,
    ) -> dict:
        full_path = self.resolve_safe_path(path)
        if not full_path.is_file():
            raise FileNotFoundError(f"Note not found: {path!r}")
        metadata, content = _load(full_path)
        new_meta = merge_frontmatter(metadata, updates, delete_keys or [])
        full_path.write_text(_dump(new_meta, content), encoding="utf-8")
        return new_meta
