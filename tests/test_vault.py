from __future__ import annotations

import os
from pathlib import Path

import pytest

from obsidian_mcp.frontmatter_utils import merge_frontmatter
from obsidian_mcp.vault import VaultManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path: Path) -> VaultManager:
    return VaultManager(tmp_path)


@pytest.fixture
def note(vault: VaultManager, tmp_path: Path) -> str:
    """A note that already exists in the vault."""
    path = "existing.md"
    (tmp_path / path).write_text("---\ntitle: Existing\n---\nHello", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Path-traversal guard
# ---------------------------------------------------------------------------


def test_relative_traversal_rejected(vault: VaultManager) -> None:
    with pytest.raises(ValueError, match="escapes vault root"):
        vault.resolve_safe_path("../../etc/passwd")


def test_absolute_path_rejected(vault: VaultManager) -> None:
    with pytest.raises(ValueError, match="escapes vault root"):
        vault.resolve_safe_path("/etc/passwd")


def test_sibling_prefix_rejected(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    evil_dir = tmp_path / "vault-evil"
    evil_dir.mkdir()
    (evil_dir / "secret.md").write_text("secret", encoding="utf-8")

    vm = VaultManager(vault_dir)
    with pytest.raises(ValueError, match="escapes vault root"):
        vm.resolve_safe_path("../vault-evil/secret.md")


def test_empty_path_resolves_to_vault_root(vault: VaultManager, tmp_path: Path) -> None:
    resolved = vault.resolve_safe_path("")
    assert resolved == tmp_path.resolve()


@pytest.mark.skipif(os.name == "nt", reason="symlinks require elevated privileges on Windows")
def test_symlink_outside_vault_rejected(vault: VaultManager, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_target.md"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(outside)

    with pytest.raises(ValueError, match="escapes vault root"):
        vault.resolve_safe_path("link.md")


# ---------------------------------------------------------------------------
# list_notes
# ---------------------------------------------------------------------------


def test_list_notes_empty_vault(vault: VaultManager) -> None:
    assert vault.list_notes() == []


def test_list_notes_returns_md_files(vault: VaultManager, tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("", encoding="utf-8")
    (tmp_path / "b.txt").write_text("", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("", encoding="utf-8")

    assert vault.list_notes() == ["a.md", "sub/c.md"]


def test_list_notes_non_recursive(vault: VaultManager, tmp_path: Path) -> None:
    (tmp_path / "top.md").write_text("", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.md").write_text("", encoding="utf-8")

    assert vault.list_notes(recursive=False) == ["top.md"]


def test_list_notes_subfolder(vault: VaultManager, tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "note.md").write_text("", encoding="utf-8")
    (tmp_path / "root.md").write_text("", encoding="utf-8")

    assert vault.list_notes(folder="sub") == ["sub/note.md"]


def test_list_notes_missing_folder(vault: VaultManager) -> None:
    with pytest.raises(ValueError, match="Folder not found"):
        vault.list_notes(folder="nonexistent")


# ---------------------------------------------------------------------------
# read_note
# ---------------------------------------------------------------------------


def test_read_note_returns_frontmatter_and_content(vault: VaultManager, note: str) -> None:
    result = vault.read_note(note)
    assert result["frontmatter"] == {"title": "Existing"}
    assert result["content"] == "Hello"


def test_read_note_missing_raises(vault: VaultManager) -> None:
    with pytest.raises(FileNotFoundError):
        vault.read_note("missing.md")


# ---------------------------------------------------------------------------
# create_note
# ---------------------------------------------------------------------------


def test_create_note_creates_file(vault: VaultManager, tmp_path: Path) -> None:
    returned = vault.create_note("new.md", "Body text")
    assert returned == "new.md"
    assert (tmp_path / "new.md").exists()


def test_create_note_with_frontmatter(vault: VaultManager, tmp_path: Path) -> None:
    vault.create_note("fm.md", "Body", frontmatter_data={"title": "T", "tags": ["a", "b"]})
    result = vault.read_note("fm.md")
    assert result["frontmatter"]["title"] == "T"
    assert result["frontmatter"]["tags"] == ["a", "b"]
    assert result["content"] == "Body"


def test_create_note_handler_key_in_frontmatter(vault: VaultManager) -> None:
    """A frontmatter key named 'handler' must not be swallowed as a positional arg."""
    vault.create_note("handler_key.md", "Body", frontmatter_data={"handler": "custom"})
    result = vault.read_note("handler_key.md")
    assert result["frontmatter"]["handler"] == "custom"


def test_create_note_refuses_overwrite(vault: VaultManager, note: str) -> None:
    with pytest.raises(FileExistsError):
        vault.create_note(note, "New content")


def test_create_note_creates_parent_dirs(vault: VaultManager, tmp_path: Path) -> None:
    vault.create_note("a/b/c.md", "Nested")
    assert (tmp_path / "a" / "b" / "c.md").exists()


# ---------------------------------------------------------------------------
# update_note
# ---------------------------------------------------------------------------


def test_update_note_overwrite(vault: VaultManager, note: str) -> None:
    vault.update_note(note, "Replaced")
    assert vault.read_note(note)["content"] == "Replaced"


def test_update_note_append(vault: VaultManager, note: str) -> None:
    vault.update_note(note, "Appended", mode="append")
    assert vault.read_note(note)["content"] == "Hello\nAppended"


def test_update_note_prepend(vault: VaultManager, note: str) -> None:
    vault.update_note(note, "Prepended", mode="prepend")
    assert vault.read_note(note)["content"] == "Prepended\nHello"


def test_update_note_preserves_frontmatter(vault: VaultManager, note: str) -> None:
    vault.update_note(note, "New body")
    assert vault.read_note(note)["frontmatter"] == {"title": "Existing"}


def test_update_note_missing_raises(vault: VaultManager) -> None:
    with pytest.raises(FileNotFoundError):
        vault.update_note("missing.md", "Content")


# ---------------------------------------------------------------------------
# update_frontmatter
# ---------------------------------------------------------------------------


def test_update_frontmatter_adds_key(vault: VaultManager, note: str) -> None:
    result = vault.update_frontmatter(note, {"status": "draft"})
    assert result["title"] == "Existing"
    assert result["status"] == "draft"


def test_update_frontmatter_overwrites_key(vault: VaultManager, note: str) -> None:
    result = vault.update_frontmatter(note, {"title": "Updated"})
    assert result["title"] == "Updated"


def test_update_frontmatter_delete_key(vault: VaultManager, note: str) -> None:
    result = vault.update_frontmatter(note, {}, delete_keys=["title"])
    assert "title" not in result


def test_update_frontmatter_delete_missing_key_noop(vault: VaultManager, note: str) -> None:
    result = vault.update_frontmatter(note, {}, delete_keys=["nonexistent"])
    assert result == {"title": "Existing"}


def test_update_frontmatter_preserves_content(vault: VaultManager, note: str) -> None:
    vault.update_frontmatter(note, {"new": "val"})
    assert vault.read_note(note)["content"] == "Hello"


def test_update_frontmatter_missing_note_raises(vault: VaultManager) -> None:
    with pytest.raises(FileNotFoundError):
        vault.update_frontmatter("missing.md", {"k": "v"})


# ---------------------------------------------------------------------------
# merge_frontmatter unit tests
# ---------------------------------------------------------------------------


def test_merge_empty_existing() -> None:
    assert merge_frontmatter({}, {"a": 1}, []) == {"a": 1}


def test_merge_untouched_keys_survive() -> None:
    result = merge_frontmatter({"a": 1, "b": 2}, {"b": 99}, [])
    assert result == {"a": 1, "b": 99}


def test_merge_delete_key() -> None:
    result = merge_frontmatter({"a": 1, "b": 2}, {}, ["a"])
    assert "a" not in result
    assert result["b"] == 2


def test_merge_delete_missing_key_noop() -> None:
    result = merge_frontmatter({"a": 1}, {}, ["nonexistent"])
    assert result == {"a": 1}


def test_merge_delete_wins_over_update() -> None:
    result = merge_frontmatter({}, {"a": 1}, ["a"])
    assert "a" not in result


def test_merge_preserves_list_type() -> None:
    result = merge_frontmatter({"tags": ["x", "y"]}, {}, [])
    assert result["tags"] == ["x", "y"]
    assert isinstance(result["tags"], list)


def test_merge_preserves_nested_dict_type() -> None:
    nested = {"k": "v"}
    result = merge_frontmatter({"meta": nested}, {}, [])
    assert result["meta"] == {"k": "v"}
    assert isinstance(result["meta"], dict)


def test_merge_returns_copy_not_mutation() -> None:
    original = {"a": 1}
    result = merge_frontmatter(original, {}, [])
    result["b"] = 2
    assert "b" not in original
