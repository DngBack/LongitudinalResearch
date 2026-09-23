"""Streaming numeric summaries and categorical frequencies."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .common import csv_files, iter_csv_rows, relative_path


@dataclass
class ColumnStats:
    count: int = 0
    missing: int = 0
    numeric_count: int = 0
    numeric_invalid: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    frequencies: Counter[str] = field(default_factory=Counter)
    too_many_categories: bool = False

    def add(self, value: str, category_limit: int) -> None:
        self.count += 1
        value = value.strip()
        if not value:
            self.missing += 1
            return
        try:
            number = float(value)
            self.numeric_count += 1
            self.total += number
            self.minimum = number if self.minimum is None else min(self.minimum, number)
            self.maximum = number if self.maximum is None else max(self.maximum, number)
        except ValueError:
            self.numeric_invalid += 1

        if not self.too_many_categories:
            self.frequencies[value] += 1
            if len(self.frequencies) > category_limit:
                self.frequencies.clear()
                self.too_many_categories = True

    @property
    def kind(self) -> str:
        return "numeric" if self.numeric_count and self.numeric_invalid == 0 else "categorical"


def analyse_distributions(data_dir: Path, output_dir: Path, category_limit: int = 5000) -> Path:
    """Write per-column summaries and category counts, with bounded memory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "column_distributions.csv"

    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "file", "column", "type", "non_missing", "missing", "unique_categories",
            "mean", "min", "max", "top_values",
        ])
        for path in csv_files(data_dir):
            table = iter_csv_rows(path)
            stats = [ColumnStats() for _ in table.headers]
            for row in table.rows:
                for index, column in enumerate(stats):
                    column.add(row[index] if index < len(row) else "", category_limit)
            for header, column in zip(table.headers, stats):
                numeric = column.kind == "numeric"
                top_values = ""
                unique = ""
                if not numeric:
                    unique = "more_than_limit" if column.too_many_categories else len(column.frequencies)
                    if not column.too_many_categories:
                        top_values = " | ".join(
                            f"{value} ({count})" for value, count in column.frequencies.most_common(10)
                        )
                writer.writerow([
                    relative_path(path, data_dir),
                    header,
                    column.kind,
                    column.count - column.missing,
                    column.missing,
                    unique,
                    round(column.total / column.numeric_count, 6) if numeric and column.numeric_count else "",
                    column.minimum if numeric else "",
                    column.maximum if numeric else "",
                    top_values,
                ])
    return summary_path
