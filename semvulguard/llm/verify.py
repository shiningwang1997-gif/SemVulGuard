"""CLI: run the static-evidence-guided semantic verifier over Top-K candidates.

Selects the Top-K samples by rank score, builds a
:class:`~semvulguard.schemas.records.VerificationPacket` (with a structured
static-evidence summary) for each, runs them through :class:`LLMVerifier`, and
writes one validated :class:`~semvulguard.schemas.records.LLMVerdict` per
candidate to a JSONL file.

Real runs use :class:`DeepSeekClient` and require ``DEEPSEEK_API_KEY``; ``--mock``
swaps in the offline :class:`MockLLMClient`, and ``--dry-run-prompts`` writes the
rendered prompts without calling any LLM.

Example::

    python -m semvulguard.llm.verify \
        --features path/to/features.jsonl \
        --rank-scores path/to/rank_scores.jsonl \
        --alerts path/to/static_alerts.jsonl \
        --output path/to/llm_verdicts.jsonl \
        --top-k 50 --mock
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from semvulguard.llm.client import DeepSeekClient
from semvulguard.llm.cost import CostLogger
from semvulguard.llm.mock import MockLLMClient
from semvulguard.llm.packet import build_verification_packet, select_topk_candidates
from semvulguard.llm.prompt_builder import PromptBuilder
from semvulguard.llm.verifier import LLMVerifier
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import LLMVerdict, StaticAlertRecord
from semvulguard.utils.jsonl import read_models, write_jsonl
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.llm.verify")


def _index_features(features_path: Path) -> dict[str, FeatureRecord]:
    """Load feature records into a sample_id -> record map."""
    return {r.sample_id: r for r in read_models(features_path, FeatureRecord)}


def _group_alerts(alerts_path: Path) -> dict[str, list[StaticAlertRecord]]:
    """Group static alerts by sample_id."""
    grouped: dict[str, list[StaticAlertRecord]] = defaultdict(list)
    for alert in read_models(alerts_path, StaticAlertRecord):
        grouped[alert.sample_id].append(alert)
    return grouped


def _index_rank_scores(rank_scores_path: Path) -> dict[str, float]:
    """Map sample_id -> rank_score from a rank-scores JSONL."""
    from semvulguard.utils.jsonl import read_jsonl

    return {
        row["sample_id"]: float(row["rank_score"])
        for row in read_jsonl(rank_scores_path)
    }


def _load_graph_evidence(path: Path | None) -> dict[str, dict]:
    """Load optional per-sample Joern evidence keyed by sample_id."""
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            "graph-evidence file must be a JSON object keyed by sample_id"
        )
    return data


def _build_packets(
    features_path: Path,
    rank_scores_path: Path,
    alerts_path: Path,
    top_k: int,
    graph_evidence_path: Path | None,
):
    """Select Top-K candidates and build their verification packets, in order."""
    features = _index_features(features_path)
    alerts_by_sample = _group_alerts(alerts_path)
    rank_scores = _index_rank_scores(rank_scores_path)
    graph_evidence = _load_graph_evidence(graph_evidence_path)
    sample_ids = select_topk_candidates(rank_scores_path, top_k)

    packets = []
    for sample_id in sample_ids:
        feature = features.get(sample_id)
        if feature is None:
            LOGGER.warning("no feature record for %s; skipping", sample_id)
            continue
        packets.append(
            build_verification_packet(
                feature_record=feature,
                alerts=alerts_by_sample.get(sample_id, []),
                rank_score=rank_scores.get(sample_id),
                joern_evidence=graph_evidence.get(sample_id),
            )
        )
    return packets


def verify(
    features_path: Path,
    rank_scores_path: Path,
    alerts_path: Path,
    output_path: Path,
    top_k: int = 50,
    client=None,
    graph_evidence_path: Path | None = None,
    model: str = "deepseek-chat",
    cost_log_path: Path | None = None,
) -> list[LLMVerdict]:
    """End-to-end verification of the Top-K candidates. Returns the verdicts.

    ``client`` must expose ``complete``/``complete_json``; it is required (the
    CLI builds it from flags). Verdicts are written to ``output_path`` as JSONL.
    """
    if client is None:
        raise ValueError("a client with complete/complete_json is required")

    packets = _build_packets(
        features_path=features_path,
        rank_scores_path=rank_scores_path,
        alerts_path=alerts_path,
        top_k=top_k,
        graph_evidence_path=graph_evidence_path,
    )

    cost_logger = CostLogger(cost_log_path) if cost_log_path else None
    verifier = LLMVerifier(client=client, model=model, cost_logger=cost_logger)
    verdicts = verifier.verify_batch(packets)

    n = write_jsonl(output_path, verdicts)
    LOGGER.info("wrote %d verdicts -> %s", n, output_path)
    return verdicts


def dry_run_prompts(
    features_path: Path,
    rank_scores_path: Path,
    alerts_path: Path,
    output_path: Path,
    top_k: int = 50,
    graph_evidence_path: Path | None = None,
) -> int:
    """Render prompts for the Top-K candidates without calling any LLM.

    Writes one JSON record per candidate -- ``{sample_id, messages}`` -- so the
    exact prompts can be inspected offline. Returns the number written.
    """
    packets = _build_packets(
        features_path=features_path,
        rank_scores_path=rank_scores_path,
        alerts_path=alerts_path,
        top_k=top_k,
        graph_evidence_path=graph_evidence_path,
    )
    builder = PromptBuilder()
    records = [
        {
            "sample_id": packet.sample_id,
            "messages": builder.build_verification_messages(packet),
        }
        for packet in packets
    ]
    n = write_jsonl(output_path, records)
    LOGGER.info("wrote %d prompt records -> %s", n, output_path)
    return n


def _build_client(args: argparse.Namespace):
    if args.mock:
        return MockLLMClient(mode=args.mock_mode)
    return DeepSeekClient(model=args.model, temperature=args.temperature)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.llm.verify",
        description="Verify Top-K ranked candidates with the semantic verifier.",
    )
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--rank-scores", required=True, type=Path)
    parser.add_argument("--alerts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--graph-evidence", type=Path, default=None)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--cost-log", type=Path, default=None)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="use the offline mock client instead of calling DeepSeek",
    )
    parser.add_argument(
        "--mock-mode",
        choices=MockLLMClient.MODES,
        default="rule",
        help="mock verdict behavior (only used with --mock)",
    )
    parser.add_argument(
        "--dry-run-prompts",
        action="store_true",
        help="write rendered prompts to --output without calling any LLM",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.dry_run_prompts:
        n = dry_run_prompts(
            features_path=args.features,
            rank_scores_path=args.rank_scores,
            alerts_path=args.alerts,
            output_path=args.output,
            top_k=args.top_k,
            graph_evidence_path=args.graph_evidence,
        )
        print(f"wrote {n} prompts -> {args.output} (no LLM calls)")
        return 0

    client = _build_client(args)
    verdicts = verify(
        features_path=args.features,
        rank_scores_path=args.rank_scores,
        alerts_path=args.alerts,
        output_path=args.output,
        top_k=args.top_k,
        client=client,
        graph_evidence_path=args.graph_evidence,
        model=args.model,
        cost_log_path=args.cost_log,
    )
    print(f"verified {len(verdicts)} candidates -> {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["verify", "dry_run_prompts", "main", "build_arg_parser"]
