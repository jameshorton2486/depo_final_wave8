from __future__ import annotations

import argparse
import sys

from backend.db import repository as l1_repo
from backend.transcript import repository as trepo


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind an existing transcript job to a case without mutating raw transcript content."
    )
    parser.add_argument("job_id", help="Transcript job id to bind")
    parser.add_argument("case_id", help="Target case id")
    args = parser.parse_args()

    job = trepo.get_job(args.job_id)
    if job is None:
        print(f"Transcript job not found: {args.job_id}", file=sys.stderr)
        return 1

    case_row = l1_repo.get_case(args.case_id)
    if case_row is None:
        print(f"Case not found: {args.case_id}", file=sys.stderr)
        return 1

    if job.get("session_id"):
        session_row = l1_repo.get_session(job["session_id"])
        if session_row and session_row.get("case_id") != args.case_id:
            print(
                "Refusing to rebind job because its existing session belongs to a different case.",
                file=sys.stderr,
            )
            return 1

    updated = trepo.update_job(args.job_id, {"case_id": args.case_id})
    if updated is None:
        print(f"Transcript job not found after update: {args.job_id}", file=sys.stderr)
        return 1

    print(f"Bound transcript job {args.job_id} to case {args.case_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
