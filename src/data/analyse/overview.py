"""Dataset inventory and table shape overview."""

from __future__ import annotations

import csv
from pathlib import Path

from .common import csv_files, iter_csv_rows, relative_path


def analyse_overview(data_dir: Path, output_dir: Path) -> Path:
    """Write file inventory and CSV row/column counts; returns the report path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "file_inventory.csv"
    table_rows: list[tuple[str, int, int, str]] = []

    with inventory_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path", "extension", "size_bytes"])
        for path in sorted(p for p in data_dir.rglob("*") if p.is_file()):
            writer.writerow([relative_path(path, data_dir), path.suffix.lower(), path.stat().st_size])

    for path in csv_files(data_dir):
        table = iter_csv_rows(path)
        row_count = sum(1 for _ in table.rows)
        table_rows.append((relative_path(path, data_dir), row_count, len(table.headers), ", ".join(table.headers)))

    report_path = output_dir / "overview.md"
    with report_path.open("w", encoding="utf-8") as stream:
        stream.write("# Dataset overview\n\n")
        stream.write(f"- Data directory: `{data_dir}`\n")
        stream.write(f"- Files: {sum(1 for p in data_dir.rglob('*') if p.is_file())}\n")
        stream.write(f"- CSV tables: {len(table_rows)}\n\n")
        stream.write("| CSV | Rows | Columns | Column names |\n|---|---:|---:|---|\n")
        for path, rows, columns, names in table_rows:
            stream.write(f"| `{path}` | {rows} | {columns} | {names.replace('|', '\\|')} |\n")
        stream.write("\nSee `file_inventory.csv` for file sizes and formats.\n")
    return report_path
