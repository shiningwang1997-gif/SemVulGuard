"""Config loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from semvulguard.utils.config import load_config, load_configs


def test_load_single_config(tmp_path: Path):
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text("a: 1\nb:\n  c: 2\n", encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg["a"] == 1
    assert cfg["b"]["c"] == 2


def test_load_empty_config_returns_empty_dict(tmp_path: Path):
    cfg_path = tmp_path / "empty.yaml"
    cfg_path.write_text("", encoding="utf-8")
    assert load_config(cfg_path) == {}


def test_missing_config_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_non_mapping_root_raises(tmp_path: Path):
    cfg_path = tmp_path / "list.yaml"
    cfg_path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(cfg_path)


def test_load_configs_merge_override(tmp_path: Path):
    base = tmp_path / "base.yaml"
    override = tmp_path / "over.yaml"
    base.write_text("a: 1\nb: 2\n", encoding="utf-8")
    override.write_text("b: 99\nc: 3\n", encoding="utf-8")
    merged = load_configs(base, override)
    assert merged == {"a": 1, "b": 99, "c": 3}


@pytest.mark.parametrize(
    "name",
    ["dataset.yaml", "static.yaml", "train.yaml", "llm.yaml", "eval.yaml"],
)
def test_project_configs_load(configs_dir: Path, name: str):
    cfg = load_config(configs_dir / name)
    assert isinstance(cfg, dict)
    assert cfg  # non-empty
