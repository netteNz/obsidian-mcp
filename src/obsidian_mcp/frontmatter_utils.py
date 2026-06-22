from __future__ import annotations


def merge_frontmatter(
    existing: dict,
    updates: dict,
    delete_keys: list[str],
) -> dict:
    result = dict(existing)
    result.update(updates)
    for key in delete_keys:
        result.pop(key, None)
    return result
