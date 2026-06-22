import os
from pathlib import Path


def load_vault_path() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not raw:
        raise RuntimeError("OBSIDIAN_VAULT_PATH environment variable is not set")
    path = Path(raw)
    if not path.exists():
        raise RuntimeError(f"OBSIDIAN_VAULT_PATH does not exist: {path}")
    if not path.is_dir():
        raise RuntimeError(f"OBSIDIAN_VAULT_PATH is not a directory: {path}")
    return path.resolve()
