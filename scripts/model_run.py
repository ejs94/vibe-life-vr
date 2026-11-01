#!/usr/bin/env python3
"""Record and report LLM run efficiency for project tasks.

A run is one model/session attempt at one task. The script reads the OpenCode
session database for model, tokens, cost and wall time, combines that with the
blind judge quality score and gate results, and writes a stable JSON record
under ``out/qa/models``.

The important metric is not price per token. It is ``cost_to_advance``: the
total cost of every attempt needed before a human records ``ADVANCE``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_ROOT = REPO_ROOT / "out" / "qa" / "models"
RUNS_ROOT = MODELS_ROOT / "runs"


def opencode_db() -> Path:
    return Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def session_row(session_id: str) -> dict:
    db = opencode_db()
    if not db.is_file():
        raise SystemExit(f"OpenCode database not found: {db}")
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """
            SELECT id, title, model, agent, cost,
                   tokens_input, tokens_output, tokens_reasoning,
                   tokens_cache_read, tokens_cache_write,
                   time_created, time_updated
            FROM session_v2
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise SystemExit(f"session not found: {session_id}")
    return dict(row)


def parse_model(raw: str | None) -> dict:
    if not raw:
        return {"id": "unknown", "providerID": "unknown", "variant": "unknown"}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"id": raw, "providerID": "unknown", "variant": "unknown"}
    return {
        "id": parsed.get("id", "unknown"),
        "providerID": parsed.get("providerID", "unknown"),
        "variant": parsed.get("variant", "default"),
    }


def finish(args: argparse.Namespace) -> int:
    row = session_row(args.session)
    model = parse_model(row.get("model"))
    quality = read_json(Path(args.quality_json)) if args.quality_json else None
    gates = read_json(Path(args.gates_json)) if args.gates_json else {}

    judge = None
    judge_cost = 0.0
    if args.judge_session:
        judge_row = session_row(args.judge_session)
        judge = {
            "session": args.judge_session,
            "model": parse_model(judge_row.get("model")),
            "tokens": {
                "input": judge_row["tokens_input"],
                "output": judge_row["tokens_output"],
                "reasoning": judge_row["tokens_reasoning"],
                "cache_read": judge_row["tokens_cache_read"],
                "cache_write": judge_row["tokens_cache_write"],
            },
            "cost_usd": judge_row["cost"],
        }
        judge_cost = float(judge_row["cost"] or 0.0)

    tokens = {
        "input": row["tokens_input"],
        "output": row["tokens_output"],
        "reasoning": row["tokens_reasoning"],
        "cache_read": row["tokens_cache_read"],
        "cache_write": row["tokens_cache_write"],
    }
    tokens["billable"] = tokens["input"] + tokens["output"] + tokens["reasoning"]
    tokens["total"] = tokens["billable"] + tokens["cache_read"] + tokens["cache_write"]

    started_ms = row["time_created"]
    ended_ms = row["time_updated"]
    wall_seconds = max(0.0, (ended_ms - started_ms) / 1000.0)

    record = {
        "task": args.task,
        "entry": args.entry,
        "attempt": args.attempt,
        "weapon": args.weapon,
        "session": args.session,
        "model": model,
        "agent": row.get("agent"),
        "tokens": tokens,
        "cost_usd": float(row["cost"] or 0.0),
        "wall_seconds": round(wall_seconds, 1),
        "started_at": datetime.fromtimestamp(started_ms / 1000.0, tz=timezone.utc).isoformat(),
        "ended_at": datetime.fromtimestamp(ended_ms / 1000.0, tz=timezone.utc).isoformat(),
        "quality": quality,
        "quality_total": (quality or {}).get("total"),
        "gates": gates,
        "decision": args.decision,
        "artifacts": args.artifacts,
        "notes": args.notes or "",
        "judge": judge,
        "judge_cost_usd": judge_cost,
        "cost_with_judge_usd": float(row["cost"] or 0.0) + judge_cost,
    }
    record["cost_per_quality"] = (
        round(record["cost_with_judge_usd"] / record["quality_total"], 4)
        if record["quality_total"]
        else None
    )
    record["tokens_per_quality"] = (
        round(tokens["billable"] / record["quality_total"], 2)
        if record["quality_total"]
        else None
    )

    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = f"{args.task}_{args.entry}_{args.attempt:02d}"
    run_path = RUNS_ROOT / f"{run_id}.json"
    run_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    write_leaderboard()
    print(f"wrote {run_path.relative_to(REPO_ROOT)}")
    return 0


def load_runs() -> list[dict]:
    runs = []
    if not RUNS_ROOT.is_dir():
        return runs
    for path in sorted(RUNS_ROOT.glob("*.json")):
        try:
            runs.append(read_json(path))
        except (OSError, json.JSONDecodeError):
            continue
    return runs


def task_summaries(runs: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for run in runs:
        groups[(run.get("task", "?"), run.get("entry", "?"))].append(run)

    summaries = []
    for (task, entry), attempts in sorted(groups.items()):
        attempts.sort(key=lambda item: item.get("attempt", 0))
        advance_index = next(
            (index for index, item in enumerate(attempts) if item.get("decision") == "ADVANCE"),
            None,
        )
        cost_to_advance = None
        if advance_index is not None:
            cost_to_advance = round(
                sum(item.get("cost_with_judge_usd", 0.0) for item in attempts[: advance_index + 1]),
                4,
            )
        first = attempts[0] if attempts else {}
        summaries.append(
            {
                "task": task,
                "entry": entry,
                "weapon": first.get("weapon"),
                "model": first.get("model"),
                "attempts": len(attempts),
                "quality_total": max(
                    (item.get("quality_total") or 0 for item in attempts), default=0
                ),
                "cost_to_advance_usd": cost_to_advance,
                "total_cost_usd": round(
                    sum(item.get("cost_with_judge_usd", 0.0) for item in attempts), 4
                ),
                "billable_tokens": sum(
                    item.get("tokens", {}).get("billable", 0) for item in attempts
                ),
                "first_pass": bool(first.get("decision") == "ADVANCE"),
                "decision": attempts[-1].get("decision") if attempts else "UNKNOWN",
            }
        )
    return summaries


def write_leaderboard() -> None:
    MODELS_ROOT.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    summaries = task_summaries(runs)

    by_model: dict[str, dict] = {}
    for item in summaries:
        model = item.get("model") or {}
        key = f"{model.get('providerID', '?')}/{model.get('id', '?')}#{model.get('variant', 'default')}"
        bucket = by_model.setdefault(
            key,
            {
                "model": key,
                "tasks": 0,
                "advanced": 0,
                "first_pass": 0,
                "total_cost_usd": 0.0,
                "cost_to_advance_usd": 0.0,
                "billable_tokens": 0,
                "quality_total": 0,
            },
        )
        bucket["tasks"] += 1
        bucket["total_cost_usd"] += item["total_cost_usd"]
        bucket["billable_tokens"] += item["billable_tokens"]
        bucket["quality_total"] += item["quality_total"] or 0
        if item["decision"] == "ADVANCE":
            bucket["advanced"] += 1
            bucket["cost_to_advance_usd"] += item["cost_to_advance_usd"] or 0.0
        if item["first_pass"]:
            bucket["first_pass"] += 1

    leaderboard = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "runs": runs,
        "tasks": summaries,
        "models": sorted(
            by_model.values(),
            key=lambda item: (
                item["cost_to_advance_usd"] if item["advanced"] else float("inf"),
                -item["quality_total"],
            ),
        ),
    }
    (MODELS_ROOT / "leaderboard.json").write_text(
        json.dumps(leaderboard, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Model run leaderboard",
        "",
        "Generated by `scripts/model_run.py`. Do not edit by hand.",
        "",
        "| Model | Tasks | Advanced | First-pass | Quality | Cost to advance | Total cost | Billable tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in leaderboard["models"]:
        cost_to_advance = (
            f"${item['cost_to_advance_usd']:.2f}" if item["advanced"] else "n/a"
        )
        lines.append(
            f"| `{item['model']}` | {item['tasks']} | {item['advanced']} | "
            f"{item['first_pass']}/{item['tasks']} | {item['quality_total']} | "
            f"{cost_to_advance} | ${item['total_cost_usd']:.2f} | "
            f"{item['billable_tokens']:,} |"
        )
    (MODELS_ROOT / "LEADERBOARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def report(_: argparse.Namespace) -> int:
    write_leaderboard()
    path = MODELS_ROOT / "LEADERBOARD.md"
    print(path.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    finish_parser = sub.add_parser("finish", help="record one session attempt")
    finish_parser.add_argument("--session", required=True)
    finish_parser.add_argument("--task", required=True)
    finish_parser.add_argument("--entry", required=True)
    finish_parser.add_argument("--attempt", type=int, required=True)
    finish_parser.add_argument("--weapon", required=True)
    finish_parser.add_argument("--quality-json", default="")
    finish_parser.add_argument("--gates-json", default="")
    finish_parser.add_argument("--judge-session", default="")
    finish_parser.add_argument("--decision", required=True, choices=["ADVANCE", "REWORK", "BLOCK", "PENDING"])
    finish_parser.add_argument("--artifacts", default="")
    finish_parser.add_argument("--notes", default="")
    finish_parser.set_defaults(func=finish)

    report_parser = sub.add_parser("report", help="rebuild and print the leaderboard")
    report_parser.set_defaults(func=report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
