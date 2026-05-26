from __future__ import annotations

import subprocess
from pathlib import Path


def test_stage5_frontend_contract_script():
    script = Path(__file__).with_name("stage5_frontend_contract.js")
    result = subprocess.run(
        ["node", str(script)],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stderr or result.stdout
