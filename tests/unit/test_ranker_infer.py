"""Tests for the train + infer scripts end-to-end (CPU, fallback, offline)."""

from __future__ import annotations

from pathlib import Path

from semvulguard.models.ranker.infer import infer
from semvulguard.models.ranker.infer import main as infer_main
from semvulguard.models.ranker.train import main as train_main
from semvulguard.models.ranker.train import train


def _features(fixtures_dir: Path) -> Path:
    return fixtures_dir / "model" / "features.jsonl"


def test_train_saves_checkpoint_and_metrics(fixtures_dir: Path, tmp_path: Path):
    out_dir = tmp_path / "ranker"
    metrics = train(
        features_path=_features(fixtures_dir),
        output_dir=out_dir,
        epochs=2,
        batch_size=2,
        fallback=True,
        use_gatv2=False,
    )
    assert (out_dir / "model.pt").exists()
    assert (out_dir / "train_metrics.json").exists()
    assert metrics["num_samples"] == 4
    assert len(metrics["epoch_losses"]) == 2
    assert metrics["uses_huggingface"] is False


def test_infer_writes_rank_scores(fixtures_dir: Path, tmp_path: Path):
    out_dir = tmp_path / "ranker"
    train(
        features_path=_features(fixtures_dir),
        output_dir=out_dir,
        epochs=1,
        batch_size=2,
        fallback=True,
        use_gatv2=False,
    )
    scores_path = tmp_path / "rank_scores.jsonl"
    rows = infer(
        features_path=_features(fixtures_dir),
        checkpoint_path=out_dir / "model.pt",
        output_path=scores_path,
        top_k=20,
    )
    assert scores_path.exists()
    assert len(rows) == 4
    # Required output fields are present.
    for row in rows:
        assert set(row) >= {"sample_id", "rank_score", "rank", "label", "metadata"}
        assert 0.0 <= row["rank_score"] <= 1.0


def test_infer_rows_sorted_by_descending_score(fixtures_dir: Path, tmp_path: Path):
    out_dir = tmp_path / "ranker"
    train(
        features_path=_features(fixtures_dir),
        output_dir=out_dir,
        epochs=1,
        batch_size=4,
        fallback=True,
        use_gatv2=False,
    )
    rows = infer(
        features_path=_features(fixtures_dir),
        checkpoint_path=out_dir / "model.pt",
        output_path=tmp_path / "scores.jsonl",
    )
    scores = [r["rank_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert [r["rank"] for r in rows] == [1, 2, 3, 4]


def test_top_k_limits_rows(fixtures_dir: Path, tmp_path: Path):
    out_dir = tmp_path / "ranker"
    train(
        features_path=_features(fixtures_dir),
        output_dir=out_dir,
        epochs=1,
        batch_size=4,
        fallback=True,
        use_gatv2=False,
    )
    rows = infer(
        features_path=_features(fixtures_dir),
        checkpoint_path=out_dir / "model.pt",
        output_path=tmp_path / "scores.jsonl",
        top_k=2,
    )
    assert len(rows) == 2


def test_train_and_infer_cli(fixtures_dir: Path, tmp_path: Path, capsys):
    out_dir = tmp_path / "ranker"
    rc = train_main(
        [
            "--features",
            str(_features(fixtures_dir)),
            "--output-dir",
            str(out_dir),
            "--epochs",
            "1",
            "--batch-size",
            "2",
            "--hidden-size",
            "16",
            "--fallback",
            "--no-gatv2",
        ]
    )
    assert rc == 0
    assert "trained 1 epochs" in capsys.readouterr().out

    scores_path = tmp_path / "rank_scores.jsonl"
    rc = infer_main(
        [
            "--features",
            str(_features(fixtures_dir)),
            "--checkpoint",
            str(out_dir / "model.pt"),
            "--output",
            str(scores_path),
            "--top-k",
            "20",
        ]
    )
    assert rc == 0
    assert scores_path.exists()
    assert "ranked 4 samples" in capsys.readouterr().out
