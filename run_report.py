#!/usr/bin/env python3
"""Collect or replay a dated report, render HTML, and optionally capture PNG."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
TIMEZONE = ZoneInfo("Asia/Shanghai")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="today", help="today 或 YYYY-MM-DD")
    parser.add_argument("--mode", choices=("auto", "live", "replay"), default="auto")
    parser.add_argument("--no-capture", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="保留为兼容参数；当天默认实时刷新")
    args = parser.parse_args()

    today = dt.datetime.now(TIMEZONE).date()
    target_date = today if args.date == "today" else dt.date.fromisoformat(args.date)
    mode = args.mode
    if mode == "auto":
        mode = "live" if target_date == today else "replay"
    update_latest = target_date == today and mode == "live"

    json_path = ROOT / f"{target_date.isoformat()}.json"
    collect = [
        sys.executable,
        str(ROOT / "collect_report.py"),
        "--date",
        target_date.isoformat(),
        "--mode",
        mode,
        "--output",
        str(json_path),
    ]
    subprocess.run(collect, cwd=ROOT, check=True)

    render = [
        sys.executable,
        str(ROOT / "render_report.py"),
        "--input",
        str(json_path),
    ]
    if not update_latest:
        render.append("--no-latest")
    subprocess.run(render, cwd=ROOT, check=True)

    if update_latest:
        for archive_json in sorted(ROOT.glob("????-??-??.json")):
            if archive_json.resolve() == json_path.resolve():
                continue
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "render_report.py"),
                    "--input",
                    str(archive_json),
                    "--no-latest",
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
            )

    png_path = ROOT / f"{target_date.isoformat()}.png"
    if not args.no_capture:
        capture = [
            "node",
            str(ROOT / "capture-report.mjs"),
            "--html",
            str(ROOT / f"{target_date.isoformat()}.html"),
            "--png",
            str(png_path),
        ]
        if not update_latest:
            capture.extend(["--no-latest", "true"])
        subprocess.run(capture, cwd=ROOT, check=True)

    print(
        json.dumps(
            {
                "date": target_date.isoformat(),
                "mode": mode,
                "json": str(json_path),
                "html": str(ROOT / f"{target_date.isoformat()}.html"),
                "png": None if args.no_capture else str(png_path),
                "latestUpdated": update_latest,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode or 1) from None
