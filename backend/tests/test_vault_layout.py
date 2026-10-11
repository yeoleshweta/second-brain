from pathlib import Path

from src.services.vault_layout import V1_DIRS, V2_DIRS, ensure_v1_tree


def test_ensure_v1_tree_creates_dirs_and_template(tmp_path: Path) -> None:
    ensure_v1_tree(tmp_path)
    for rel in (*V1_DIRS, *V2_DIRS):
        assert (tmp_path / rel).is_dir()
    tpl = tmp_path / "99-System" / "Templates" / "tpl-daily.md"
    assert tpl.is_file()
    assert "## Log" in tpl.read_text(encoding="utf-8")


def test_ensure_v1_tree_none() -> None:
    ensure_v1_tree(None)
