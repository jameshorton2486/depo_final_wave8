"""Report rendering for transcript layer diffs."""
from __future__ import annotations

import json
from pathlib import Path


def render_report(diff: dict) -> str:
    lines = [
        f"DEPO-PRO transcript diff: {diff['left_label']} -> {diff['right_label']}",
        f"job_id: {diff.get('job_id') or '(ad hoc)'}",
        "",
        "Metrics:",
    ]
    metrics = diff["metrics"]
    for key in (
        "left_utterance_count",
        "right_utterance_count",
        "left_word_count",
        "right_word_count",
        "gross_word_delta",
        "logged_word_delta",
        "net_word_delta",
        "changed_utterances",
        "speaker_reassignments",
        "timestamp_drifts",
        "insertions",
        "deletions",
        "substitutions",
        "unexplained_changes",
    ):
        lines.append(f"  {key}: {metrics[key]}")
    lines.append("")
    lines.append("Per-utterance diff:")
    for item in diff["per_utterance"]:
        marker = "!" if not item.get("explained") else "~"
        lines.append(
            f"{marker} {item.get('utterance_id') or '(unmatched)'} "
            f"[{', '.join(item.get('change_types') or ['changed'])}] "
            f"rules={','.join(item.get('rule_ids') or []) or '(none)'}"
        )
        lines.append(f"  left : {item.get('left_text') or ''}")
        lines.append(f"  right: {item.get('right_text') or ''}")
    return "\n".join(lines) + "\n"


def write_artifacts(diff: dict, output_dir: str | Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "diff_report.txt"
    metrics_path = output_dir / "diff_metrics.json"
    correction_log_path = output_dir / "correction_log.json"
    pipeline_snapshot_path = output_dir / "pipeline_snapshot.json"

    report_path.write_text(render_report(diff), encoding="utf-8")
    metrics_path.write_text(
        json.dumps(diff["metrics"], indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    correction_log_path.write_text(
        json.dumps(diff.get("change_log") or [], indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    pipeline_snapshot_path.write_text(
        json.dumps(diff.get("pipeline_snapshot") or {}, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "report_path": str(report_path),
        "metrics_path": str(metrics_path),
        "correction_log_path": str(correction_log_path),
        "pipeline_snapshot_path": str(pipeline_snapshot_path),
    }
