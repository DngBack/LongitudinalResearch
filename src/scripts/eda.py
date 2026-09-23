"""Run selected EDA sections on the Chest ImaGenome CSV files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data.analyse import analyse_distributions, analyse_overview, analyse_quality  # noqa: E402
from data.analyse.common import DEFAULT_DATA_DIR  # noqa: E402


SECTIONS = ("overview", "quality", "distributions")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Dataset root directory")
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "reports" / "eda",
        help="Where to write reports (default: reports/eda)",
    )
    parser.add_argument(
        "--include", nargs="+", choices=SECTIONS, default=list(SECTIONS), metavar="SECTION",
        help="Sections to run; default: all",
    )
    parser.add_argument(
        "--exclude", nargs="+", choices=SECTIONS, default=[], metavar="SECTION",
        help="Sections to skip from the selected set",
    )
    parser.add_argument(
        "--category-limit", type=int, default=5000,
        help="Maximum distinct values tracked per column for category summaries",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = args.data_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not data_dir.is_dir():
        print(f"Dataset directory does not exist: {data_dir}", file=sys.stderr)
        return 2
    if args.category_limit < 1:
        print("--category-limit must be at least 1", file=sys.stderr)
        return 2

    selected = [section for section in args.include if section not in args.exclude]
    if not selected:
        print("No EDA sections selected.", file=sys.stderr)
        return 2

    runners = {
        "overview": lambda: analyse_overview(data_dir, output_dir),
        "quality": lambda: analyse_quality(data_dir, output_dir),
        "distributions": lambda: analyse_distributions(data_dir, output_dir, args.category_limit),
    }
    for section in selected:
        print(f"[{section}] {runners[section]()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
