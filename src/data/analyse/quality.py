"""Streaming completeness and CSV-shape checks."""

from __future__ import annotations

import csv
from pathlib import Path

from .common import csv_files, iter_csv_rows, relative_path


def analyse_quality(data_dir: Path, output_dir: Path) -> Path:
    """Write missing-value and malformed-row summaries for every CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "data_quality.csv"

    with report_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "file", "column", "rows", "missing", "missing_pct", "duplicate_header",
            "rows_with_wrong_width",
        ])
        for path in csv_files(data_dir):
            table = iter_csv_rows(path)
            width = len(table.headers)
            missing = [0] * width
            wrong_width = 0
            row_count = 0
            for row in table.rows:
                row_count += 1
                if len(row) != width:
                    wrong_width += 1
                for index in range(width):
                    if index >= len(row) or not row[index].strip():
                        missing[index] += 1
            duplicate_headers = {name for name in table.headers if table.headers.count(name) > 1}
            for index, name in enumerate(table.headers):
                count = missing[index]
                writer.writerow([
                    relative_path(path, data_dir),
                    name,
                    row_count,
                    count,
                    round(count * 100 / row_count, 4) if row_count else 0,
                    name in duplicate_headers,
                    wrong_width,
                ])
            if not table.headers:
                writer.writerow([relative_path(path, data_dir), "", 0, 0, 0, False, 0])
    return report_path
