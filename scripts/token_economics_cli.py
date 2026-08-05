#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.token_economics import (  # noqa: E402
    LedgerStore,
    authorize_budget,
    build_token_economics_summary,
    default_config_root,
    estimate_usage_cost,
    load_budget_envelope,
    load_rate_cards,
    normalize_usage,
    reconcile_records,
    redacted_evidence_report,
    resolve_rate_card,
    settle_usage,
    summarize_ledger,
)


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], value)


def _json_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(cast(dict[str, Any], value))
        return records
    payload = _json_object(path)
    if isinstance(payload.get("records"), list):
        return [cast(dict[str, Any], item) for item in payload["records"] if isinstance(item, dict)]
    raise ValueError("expected JSONL or an object with a records array")


def _print(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_validate_rate_card(args: argparse.Namespace) -> int:
    cards = load_rate_cards(Path(args.config_root))
    if args.rate_card_id:
        cards = [card for card in cards if card.rate_card_id == args.rate_card_id]
        if not cards:
            raise SystemExit(f"rate card not found: {args.rate_card_id}")
    return _print(
        {
            "status": "validated",
            "config_root": str(Path(args.config_root)),
            "rate_card_ids": [card.rate_card_id for card in cards],
            "count": len(cards),
        }
    )


def command_validate_budget(args: argparse.Namespace) -> int:
    payload = load_budget_envelope(Path(args.path))
    return _print({"status": "validated", "budget": payload})


def command_resolve_rate_card(args: argparse.Namespace) -> int:
    return _print(resolve_rate_card(_json_object(Path(args.lookup)), config_root=Path(args.config_root)))


def command_estimate(args: argparse.Namespace) -> int:
    payload = _json_object(Path(args.path))
    return _print(
        estimate_usage_cost(
            cast(dict[str, Any], payload["usage"]) if isinstance(payload.get("usage"), dict) else payload,
            rate_card_id=args.rate_card_id,
            config_root=Path(args.config_root),
            ancillary_fees=cast(dict[str, Any], payload.get("ancillary_fees", {})),
        )
    )


def command_normalize(args: argparse.Namespace) -> int:
    payload = _json_object(Path(args.path))
    usage = cast(dict[str, Any], payload["usage"]) if isinstance(payload.get("usage"), dict) else payload
    provider_native_fields = (
        cast(dict[str, Any], payload["provider_native_fields"])
        if isinstance(payload.get("provider_native_fields"), dict)
        else None
    )
    return _print(
        normalize_usage(
            usage,
            provider_response_id=payload.get("provider_response_id"),
            provider_turn_id=payload.get("provider_turn_id"),
            provider_request_id=payload.get("provider_request_id"),
            provider_native_fields=provider_native_fields,
        )
    )


def command_settle(args: argparse.Namespace) -> int:
    payload = _json_object(Path(args.path))
    return _print(
        settle_usage(
            payload,
            rate_card_id=args.rate_card_id,
            config_root=Path(args.config_root),
            ancillary_fees=cast(dict[str, Any], payload.get("ancillary_fees", {})),
        )
    )


def command_authorize(args: argparse.Namespace) -> int:
    payload = _json_object(Path(args.path))
    envelope = load_budget_envelope(Path(args.budget))
    return _print(
        authorize_budget(
            envelope,
            reserved_amount=payload.get("reserved_amount", "0"),
            prior_spend_amount=payload.get("prior_spend_amount", "0"),
            observed_raw_input_tokens=payload.get("observed_raw_input_tokens"),
            observed_output_tokens=payload.get("observed_output_tokens"),
            wall_clock_seconds=payload.get("wall_clock_seconds"),
            tool_actions=payload.get("tool_actions"),
            tool_bytes=payload.get("tool_bytes"),
            model_turns=payload.get("model_turns"),
            repair_cycles=payload.get("repair_cycles"),
            review_cycles=payload.get("review_cycles"),
            handoffs=payload.get("handoffs"),
            mutation_paths=cast(list[str] | None, payload.get("mutation_paths")),
            mutation_diff_bytes=payload.get("mutation_diff_bytes"),
        )
    )


def command_aggregate(args: argparse.Namespace) -> int:
    return _print(summarize_ledger(_json_records(Path(args.path))))


def command_reconcile(args: argparse.Namespace) -> int:
    return _print(reconcile_records(_json_object(Path(args.path))))


def command_compact_report(args: argparse.Namespace) -> int:
    return _print(redacted_evidence_report(_json_records(Path(args.path))))


def command_append_ledger(args: argparse.Namespace) -> int:
    payload = _json_object(Path(args.record))
    written = LedgerStore(Path(args.ledger)).append(payload)
    return _print({"status": "appended", "ledger": str(Path(args.ledger)), "record": written})


def command_summary(args: argparse.Namespace) -> int:
    return _print(build_token_economics_summary(Path(args.project_root)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline governed token-economics operations.")
    parser.set_defaults(config_root=str(default_config_root(PROJECT_ROOT)))
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_rate = subparsers.add_parser("validate-rate-card")
    validate_rate.add_argument("--config-root", default=str(default_config_root(PROJECT_ROOT)))
    validate_rate.add_argument("--rate-card-id")
    validate_rate.set_defaults(func=command_validate_rate_card)

    validate_budget = subparsers.add_parser("validate-budget")
    validate_budget.add_argument("path")
    validate_budget.set_defaults(func=command_validate_budget)

    resolve_card = subparsers.add_parser("resolve-rate-card")
    resolve_card.add_argument("lookup")
    resolve_card.add_argument("--config-root", default=str(default_config_root(PROJECT_ROOT)))
    resolve_card.set_defaults(func=command_resolve_rate_card)

    estimate = subparsers.add_parser("estimate")
    estimate.add_argument("path")
    estimate.add_argument("--rate-card-id", required=True)
    estimate.add_argument("--config-root", default=str(default_config_root(PROJECT_ROOT)))
    estimate.set_defaults(func=command_estimate)

    normalize = subparsers.add_parser("normalize")
    normalize.add_argument("path")
    normalize.set_defaults(func=command_normalize)

    settle = subparsers.add_parser("settle")
    settle.add_argument("path")
    settle.add_argument("--rate-card-id", required=True)
    settle.add_argument("--config-root", default=str(default_config_root(PROJECT_ROOT)))
    settle.set_defaults(func=command_settle)

    authorize = subparsers.add_parser("authorize")
    authorize.add_argument("path")
    authorize.add_argument("--budget", required=True)
    authorize.set_defaults(func=command_authorize)

    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("path")
    aggregate.set_defaults(func=command_aggregate)

    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("path")
    reconcile.set_defaults(func=command_reconcile)

    compact = subparsers.add_parser("compact-report")
    compact.add_argument("path")
    compact.set_defaults(func=command_compact_report)

    append = subparsers.add_parser("append-ledger")
    append.add_argument("ledger")
    append.add_argument("record")
    append.set_defaults(func=command_append_ledger)

    summary = subparsers.add_parser("summary")
    summary.add_argument("--project-root", default=str(PROJECT_ROOT))
    summary.set_defaults(func=command_summary)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
