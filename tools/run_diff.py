from __future__ import annotations

import argparse
import json

from backend.diagnostics import write_job_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DEPO-PRO transcript diff harness.")
    parser.add_argument("job_id")
    parser.add_argument("--output-root", default=None)
    args = parser.parse_args()

    result = write_job_artifacts(args.job_id, output_root=args.output_root)
    print(json.dumps(result["diff"]["metrics"], indent=2, sort_keys=True))
    print(result["paths"]["report_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
