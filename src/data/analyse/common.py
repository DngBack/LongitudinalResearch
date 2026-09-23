"""Shared paths and CSV iteration helpers for EDA modules."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


DEFAULT_DATA_DIR = (
    Path(__file__).resolve().parents[3]
    / "physionet.org"
    / "files"
    / "chest-imagenome"
    / "1.0.0"
)


@dataclass
class CsvTable:
    path: Path
    headers: list[str]
    rows: Iterator[list[str]]


def csv_files(data_dir: Path) -> list[Path]:
    """Return CSV files in stable order."""
    return sorted(path for path in data_dir.rglob("*.csv") if path.is_file())


def iter_csv_rows(path: Path) -> CsvTable:
    """Open a CSV as a stream; the returned iterator closes its file at EOF."""
    handle = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.reader(handle)
    try:
        headers = next(reader)
    except StopIteration:
        handle.close()
        return CsvTable(path, [], iter(()))

    def rows() -> Iterator[list[str]]:
        try:
            yield from reader
        finally:
            handle.close()

    return CsvTable(path, headers, rows())


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
