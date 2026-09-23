"""Create label, image-count, and annotated sample visualizations."""

from __future__ import annotations

import csv
import json
import math
import textwrap
import zipfile
from collections import Counter, defaultdict
from itertools import combinations
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

SCENE_GRAPH_ARCHIVE = Path("silver_dataset/scene_graph.zip")
RECORD_LIST = Path("utils/cxr-record-list_view.csv")
SPLIT_FILES = {
    "Train split": Path("silver_dataset/splits/train.csv"),
    "Validation split": Path("silver_dataset/splits/valid.csv"),
    "Test split": Path("silver_dataset/splits/test.csv"),
}
SAMPLE_IMAGE_ARCHIVE = Path(
    "utils/annotation_utils/bbox_object_annotation/lung_bboxes.zip"
)
SAMPLE_ANNOTATIONS = Path("gold_dataset/gold_bbox_coordinate_annotations_1000images.csv")


def _positive_labels(graph: dict, category: str) -> set[str]:
    labels: set[str] = set()
    for object_attributes in graph.get("attributes", []):
        for phrase_labels in object_attributes.get("attributes", []):
            for label in phrase_labels:
                parts = label.split("|", 2)
                if len(parts) == 3 and parts[1] == "yes":
                    if category == "all" or parts[0] == category:
                        labels.add(label)
    return labels


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        next(reader, None)
        return sum(1 for _ in reader)


def _image_count_data(data_dir: Path, graph_count: int) -> list[tuple[str, int, str]]:
    counts: list[tuple[str, int, str]] = []
    record_path = data_dir / RECORD_LIST
    if record_path.exists():
        counts.append(("CXR record list", _count_csv_rows(record_path), "record rows"))
    counts.append(("Scene graph", graph_count, "unique image graphs"))
    for split, relative in SPLIT_FILES.items():
        path = data_dir / relative
        if path.exists():
            counts.append((split, _count_csv_rows(path), "split rows"))
    return counts


def _write_image_counts(counts: list[tuple[str, int, str]], output_dir: Path) -> None:
    with (output_dir / "image_counts.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["source", "image_count", "count_unit"])
        writer.writerows(counts)

    names = [item[0] for item in counts]
    values = [item[1] for item in counts]
    fig, ax = plt.subplots(figsize=(10, max(4, 0.55 * len(counts))))
    bars = ax.barh(names, values, color="#3978a8")
    ax.invert_yaxis()
    ax.set_xlabel("Number of image records")
    ax.set_title("Image counts by source (sources may overlap)")
    ax.set_xlim(0, max(values, default=0) * 1.18)
    ax.grid(axis="x", alpha=0.2)
    ax.bar_label(bars, labels=[f"{value:,}" for value in values], padding=4, fontsize=9)
    fig.tight_layout()
    fig.savefig(output_dir / "image_counts.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_label_counts(
    counts: Counter[str], image_count: int, output_dir: Path, top_n: int
) -> list[str]:
    ordered = counts.most_common()
    with (output_dir / "label_counts.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["label", "images_with_label", "prevalence_pct"])
        for label, count in ordered:
            writer.writerow([label, count, round(100 * count / image_count, 4) if image_count else 0])

    top = ordered[:top_n]
    labels = [label for label, _ in reversed(top)]
    values = [count for _, count in reversed(top)]
    display_labels = [textwrap.fill(label.split("|", 2)[-1], width=34) for label in labels]
    fig, ax = plt.subplots(figsize=(11, max(5, 0.42 * len(top))))
    bars = ax.barh(display_labels, values, color="#cc7253")
    ax.set_xlabel("Images containing the positive label")
    ax.set_title(f"Most frequent positive labels (top {len(top)})")
    ax.set_xlim(0, max(values, default=0) * 1.18)
    ax.grid(axis="x", alpha=0.2)
    ax.bar_label(bars, labels=[f"{value:,}" for value in values], padding=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "label_distribution.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return [label for label, _ in top]


def _write_multilabel_distribution(
    label_count_by_image: Counter[int], image_count: int, output_dir: Path
) -> None:
    with (output_dir / "labels_per_image.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["positive_labels_per_image", "image_count", "image_pct"])
        for label_count in sorted(label_count_by_image):
            count = label_count_by_image[label_count]
            writer.writerow([label_count, count, round(100 * count / image_count, 4) if image_count else 0])

    x_values = sorted(label_count_by_image)
    y_values = [label_count_by_image[value] for value in x_values]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(x_values, y_values, color="#5b9b7b", width=0.85)
    ax.set_xlabel("Distinct positive labels per image")
    ax.set_ylabel("Number of images")
    ax.set_title("Multi-label count per image")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_dir / "labels_per_image.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _phi_correlation(image_count: int, count_a: int, count_b: int, joint: int) -> float:
    if not image_count:
        return 0.0
    numerator = image_count * joint - count_a * count_b
    denominator = math.sqrt(count_a * (image_count - count_a) * count_b * (image_count - count_b))
    return numerator / denominator if denominator else 0.0


def _write_label_correlations(
    top_labels: list[str],
    label_counts: Counter[str],
    pair_counts: Counter[tuple[str, str]],
    image_count: int,
    output_dir: Path,
) -> None:
    correlations = [[0.0 for _ in top_labels] for _ in top_labels]
    for i, label_a in enumerate(top_labels):
        correlations[i][i] = 1.0
        for j in range(i + 1, len(top_labels)):
            label_b = top_labels[j]
            pair = tuple(sorted((label_a, label_b)))
            phi = _phi_correlation(image_count, label_counts[label_a], label_counts[label_b], pair_counts[pair])
            correlations[i][j] = correlations[j][i] = phi

    with (output_dir / "label_correlations.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["label_a", "label_b", "joint_images", "phi_correlation"])
        for i, label_a in enumerate(top_labels):
            for j in range(i + 1, len(top_labels)):
                label_b = top_labels[j]
                pair = tuple(sorted((label_a, label_b)))
                writer.writerow([
                    label_a,
                    label_b,
                    pair_counts[pair],
                    round(correlations[i][j], 6),
                ])

    if not top_labels:
        return
    display_labels = [textwrap.fill(label.split("|", 2)[-1], width=19) for label in top_labels]
    size = max(8, min(15, 0.62 * len(top_labels) + 5))
    fig, ax = plt.subplots(figsize=(size, size))
    image = ax.imshow(correlations, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(top_labels)), display_labels, rotation=55, ha="right", fontsize=8)
    ax.set_yticks(range(len(top_labels)), display_labels, fontsize=8)
    ax.set_title("Phi correlation between the most frequent labels")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Phi coefficient")
    fig.tight_layout()
    fig.savefig(output_dir / "label_correlation.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _sample_annotations(data_dir: Path) -> dict[str, list[dict[str, str]]]:
    annotations: dict[str, list[dict[str, str]]] = defaultdict(list)
    path = data_dir / SAMPLE_ANNOTATIONS
    if not path.exists():
        return annotations
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            annotations[row["image_id"]].append(row)
    return annotations


def _write_sample_images(data_dir: Path, output_dir: Path, sample_count: int) -> int:
    archive_path = data_dir / SAMPLE_IMAGE_ARCHIVE
    annotations = _sample_annotations(data_dir)
    if not archive_path.exists() or not annotations:
        return 0

    with zipfile.ZipFile(archive_path) as archive:
        candidates: list[tuple[str, str, list[dict[str, str]]]] = []
        for member in archive.namelist():
            if not member.lower().endswith(".png"):
                continue
            image_id = Path(member).name.removesuffix(".png")
            if image_id in annotations:
                candidates.append((image_id, member, annotations[image_id]))
        if not candidates:
            return 0

        candidates.sort(key=lambda item: (len(item[2]), item[0]))
        effective_count = min(sample_count, len(candidates))
        selected_indices = {
            round(index * (len(candidates) - 1) / max(1, effective_count - 1))
            for index in range(effective_count)
        }
        selected = [candidates[index] for index in sorted(selected_indices)]
        fig = plt.figure(figsize=(14, 4.3 * len(selected)))
        grid = fig.add_gridspec(len(selected), 2, width_ratios=[1.05, 0.95], hspace=0.38, wspace=0.18)
        palette = ("#00d4ff", "#ffcf33", "#ff4f81", "#79e381", "#c49bff", "#ff8c42")

        with (output_dir / "sample_image_labels.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["image_id", "bbox_label", "x1", "y1", "x2", "y2"])
            for row_index, (image_id, member, rows) in enumerate(selected):
                image = Image.open(BytesIO(archive.read(member))).convert("L")
                image_axis = fig.add_subplot(grid[row_index, 0])
                image_axis.imshow(image, cmap="gray", vmin=0, vmax=255)
                image_axis.set_title(f"Sample {row_index + 1} · {len(rows)} annotated boxes", fontsize=10)
                image_axis.axis("off")
                x_scale, y_scale = image.width / 224, image.height / 224

                unique_labels: dict[str, dict[str, str]] = {}
                for row in rows:
                    label = row["bbox_name"]
                    unique_labels.setdefault(label, row)
                    try:
                        x1, y1, x2, y2 = (float(row[key]) for key in ("x1", "y1", "x2", "y2"))
                    except (KeyError, ValueError):
                        continue
                    image_axis.add_patch(Rectangle(
                        (x1 * x_scale, y1 * y_scale),
                        (x2 - x1) * x_scale,
                        (y2 - y1) * y_scale,
                        linewidth=0.7,
                        edgecolor=palette[len(unique_labels) % len(palette)],
                        facecolor="none",
                        alpha=0.75,
                    ))
                    writer.writerow([image_id, label, row["x1"], row["y1"], row["x2"], row["y2"]])

                text_axis = fig.add_subplot(grid[row_index, 1])
                text_axis.axis("off")
                label_names = list(unique_labels)
                displayed = label_names[:12]
                if len(label_names) > len(displayed):
                    displayed.append(f"… {len(label_names) - len(displayed)} more regions")
                text_axis.text(
                    0,
                    1,
                    "Bounding-box labels\n\n"
                    + "\n".join(f"• {name}" for name in displayed)
                    + f"\n\nImage ID: {image_id}",
                    va="top",
                    fontsize=10,
                    linespacing=1.45,
                    wrap=True,
                )

        fig.suptitle("Sample chest X-rays with annotated anatomy regions", fontsize=14, y=0.995)
        fig.savefig(output_dir / "sample_images_with_labels.png", dpi=180, bbox_inches="tight")
        plt.close(fig)
    return len(selected)


def analyse_visualizations(
    data_dir: Path,
    output_dir: Path,
    label_category: str = "anatomicalfinding",
    top_n: int = 20,
    sample_count: int = 4,
) -> list[Path]:
    """Analyze scene-graph labels and create PNG figures plus CSV summaries."""
    output_dir.mkdir(parents=True, exist_ok=True)
    graph_path = data_dir / SCENE_GRAPH_ARCHIVE
    if not graph_path.exists():
        raise FileNotFoundError(f"Scene-graph archive not found: {graph_path}")

    image_ids: set[str] = set()
    label_counts: Counter[str] = Counter()
    label_count_by_image: Counter[int] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()

    with zipfile.ZipFile(graph_path) as archive:
        scene_graph_members = [item for item in archive.infolist() if item.filename.endswith(".json")]
        for member in scene_graph_members:
            graph = json.loads(archive.read(member))
            image_ids.add(str(graph.get("image_id") or Path(member.filename).stem))
            labels = _positive_labels(graph, label_category)
            label_counts.update(labels)
            label_count_by_image[len(labels)] += 1
            pair_counts.update(combinations(sorted(labels), 2))

    image_count = len(image_ids)
    if not image_count:
        raise ValueError(f"No image graphs found in {graph_path}")

    graph_count = len(scene_graph_members)
    counts = _image_count_data(data_dir, graph_count)
    _write_image_counts(counts, output_dir)
    top_labels = _write_label_counts(label_counts, image_count, output_dir, top_n)
    _write_multilabel_distribution(label_count_by_image, image_count, output_dir)
    _write_label_correlations(top_labels[:15], label_counts, pair_counts, image_count, output_dir)
    sample_images = _write_sample_images(data_dir, output_dir, sample_count)

    summary_path = output_dir / "visualizations.md"
    with summary_path.open("w", encoding="utf-8") as stream:
        stream.write("# Label and image visualizations\n\n")
        stream.write(f"- Scene-graph images: {image_count:,} ({graph_count:,} graph files)\n")
        stream.write(f"- Label category: `{label_category}`; only positive (`yes`) labels are counted.\n")
        stream.write("- Label counts and co-occurrence count each label at most once per image.\n")
        stream.write("- Correlation figure uses the phi coefficient for binary label presence.\n")
        stream.write(f"- Sample images rendered from the supplied bbox PNG archive: {sample_images}\n")
        stream.write("- The repository contains annotated PNG samples rather than the full original DICOM image collection.\n\n")
        stream.write("Generated figures: `label_distribution.png`, `labels_per_image.png`, `label_correlation.png`, ")
        stream.write("`image_counts.png`, and `sample_images_with_labels.png`.\n")

    return [
        output_dir / "label_distribution.png",
        output_dir / "labels_per_image.png",
        output_dir / "label_correlation.png",
        output_dir / "image_counts.png",
        output_dir / "sample_images_with_labels.png",
        output_dir / "label_counts.csv",
        output_dir / "labels_per_image.csv",
        output_dir / "label_correlations.csv",
        output_dir / "image_counts.csv",
        output_dir / "sample_image_labels.csv",
        summary_path,
    ]
