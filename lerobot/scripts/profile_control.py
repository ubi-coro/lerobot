#!/usr/bin/env python3
"""
Run control_robot.py under py-spy to generate a flame graph.

Usage examples:

- Teleoperate (no FPS cap), profile to default SVG:
  python lerobot/scripts/profile_control.py -- --robot.type=aloha --control.type=teleoperate --robot.cameras={}

- Record mode, custom output file and sample rate:
  python lerobot/scripts/profile_control.py \
    --output outputs/pyspy/record_aloha.svg --rate 200 \
    -- --robot.type=aloha --control.type=record --control.fps=30 --control.repo_id=$USER/test --control.single_task="Test"

Notes:
- Keep the double-dash (--) to separate wrapper args from control_robot.py args.
- py-spy must be installed and on PATH.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
# Repository root: .../lerobot
REPO_ROOT = THIS_DIR.parents[1]
# Target script lives alongside this wrapper in the same folder
CONTROL_SCRIPT = THIS_DIR / "control_robot.py"
DEFAULT_OUT_DIR = REPO_ROOT / "outputs" / "pyspy"


def main():
    parser = argparse.ArgumentParser(description="Profile control_robot.py with py-spy")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output SVG path (default: outputs/pyspy/<timestamp>.svg)")
    parser.add_argument("--rate", type=int, default=100, help="Sampling rate in Hz (default: 100)")
    parser.add_argument("--duration", type=float, default=None, help="Optional duration in seconds (if omitted, runs until script ends)")
    parser.add_argument("--no-native", action="store_true", help="Disable native stack sampling (default: enabled)")
    parser.add_argument("--pyspy-extra", type=str, default=None, help="Extra py-spy args as a single string (advanced)")

    # Everything after '--' is forwarded to control_robot.py
    args, forward = parser.parse_known_args()

    if shutil.which("py-spy") is None:
        print("Error: py-spy is not installed or not on PATH. Try: pip install py-spy")
        sys.exit(1)

    out_dir = DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = out_dir / f"control_profile_{ts}.svg"
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "py-spy",
        "record",
        "-o",
        str(output),
        "--rate",
        str(args.rate),
    ]

    if not args.no_native:
        cmd.append("--native")

    if args.duration is not None:
        cmd += ["--duration", str(args.duration)]

    if args.pyspy_extra:
        # Split on whitespace to extend args (advanced usage)
        cmd += args.pyspy_extra.split()

    # The script to run under py-spy
    cmd += ["--", sys.executable, str(CONTROL_SCRIPT)]

    # Forward any remaining args to control_robot.py
    cmd += forward

    print("Running:")
    print(" ", " ".join(cmd))
    print(f"Output SVG: {output}")

    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print(f"py-spy failed with exit code {proc.returncode}")
        sys.exit(proc.returncode)

    print(f"Profile written to: {output}")


if __name__ == "__main__":
    main()
