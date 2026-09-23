"""Build a patient-level longitudinal timeline from Chest ImaGenome graphs."""

from __future__ import annotations

import csv
from io import BytesIO
import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
from PIL import Image, ImageOps

SCENE_GRAPH_ARCHIVE = Path("silver_dataset/scene_graph.zip")
RECORD_LIST = Path("utils/cxr-record-list_view.csv")
SAMPLE_IMAGE_ARCHIVE = Path("utils/annotation_utils/bbox_object_annotation/lung_bboxes.zip")
FRONTAL_VIEWS = {"AP", "PA"}


def _patient_records(data_dir: Path) -> dict[str, dict[str, dict[str, set[str]]]]:
    """Return patient -> study -> frontal image IDs, based on the record list."""
    path = data_dir / RECORD_LIST
    if not path.exists():
        raise FileNotFoundError(f"CXR record list not found: {path}")

    patients: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: {"images": set()})
    )
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            view = (row.get("ViewPosition") or "").strip().upper()
            patient_id = (row.get("subject_id") or "").strip()
            study_id = (row.get("study_id") or "").strip()
            image_id = (row.get("dicom_id") or "").strip()
            if view in FRONTAL_VIEWS and patient_id and study_id and image_id:
                patients[patient_id][study_id]["images"].add(image_id)
    return patients


def _choose_patient(
    records: dict[str, dict[str, dict[str, set[str]]]],
    graph_names: set[str],
    image_names: set[str],
) -> str:
    candidates: list[tuple[int, int, int, str]] = []
    for patient_id, studies in records.items():
        image_ids = {image_id for study in studies.values() for image_id in study["images"]}
        graph_images = {image_id for image_id in image_ids if f"{image_id}_SceneGraph.json" in graph_names}
        visual_images = graph_images & image_names
        visual_studies = sum(bool(study["images"] & visual_images) for study in studies.values())
        if 3 <= len(studies) <= 15 and len(graph_images) >= 3 and visual_studies >= 3:
            candidates.append((visual_studies, len(visual_images), len(studies), patient_id))
    if not candidates:
        # If the optional PNG archive is absent, still allow a scene-graph-only timeline.
        for patient_id, studies in records.items():
            image_ids = {image_id for study in studies.values() for image_id in study["images"]}
            graph_images = sum(f"{image_id}_SceneGraph.json" in graph_names for image_id in image_ids)
            if 3 <= len(studies) <= 15 and graph_images >= 3:
                candidates.append((0, graph_images, len(studies), patient_id))
    if not candidates:
        raise ValueError("No patient with at least three frontal studies and matching scene graphs was found")
    return max(candidates)[3]


def _positive_findings(graph: dict) -> set[str]:
    labels: set[str] = set()
    for object_attributes in graph.get("attributes", []):
        for phrase_labels in object_attributes.get("attributes", []):
            for value in phrase_labels:
                parts = str(value).split("|", 2)
                if len(parts) == 3 and parts[0] == "anatomicalfinding" and parts[1] == "yes":
                    labels.add(parts[2])
    return labels


def _image_from_object_id(value: str) -> str:
    # Scene-graph object IDs are `<image UUID>_<anatomical region>`.
    return value.split("_", 1)[0]


def _write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _plot_timeline(patient_id: str, studies: list[dict], relations: list[dict], path: Path) -> None:
    position = {study["study_id"]: index for index, study in enumerate(studies)}
    relation_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for relation in relations:
        relation_groups[(relation["from_study"], relation["to_study"])].append(relation)

    fig, ax = plt.subplots(figsize=(max(15, len(studies) * 1.55), 9))
    ax.set_xlim(-0.65, len(studies) - 0.35)
    ax.set_ylim(-2.7, 2.4)
    ax.axhline(0, color="#7f8c8d", linewidth=1.5, zorder=1)

    colors = {"improved": "#27864a", "worsened": "#c53d3d", "no change": "#54748b", "unknown": "#9b7bb5"}
    for (from_study, to_study), group in relation_groups.items():
        left, right = position[from_study], position[to_study]
        labels = {str(label) for row in group for label in row["comparison_labels"].split(";") if label}
        status_set = {label.rsplit("|", 1)[-1] for label in labels}
        color = next(iter(status_set)) if len(status_set) == 1 else "unknown"
        color = colors.get(color, colors["unknown"])
        level = 0.65 + (len(relation_groups) % 4) * 0.34
        arrow = FancyArrowPatch(
            (left, 0.18), (right, 0.18), connectionstyle=f"arc3,rad={min(0.42, level / max(2, right-left))}",
            arrowstyle="-|>", mutation_scale=12, linewidth=1.15, color=color, alpha=0.68, zorder=2,
        )
        ax.add_patch(arrow)
        ax.text((left + right) / 2, level, f"{len(group)} rel.", color=color, ha="center", va="bottom", fontsize=8)

    node_colors = {"improved": "#27864a", "worsened": "#c53d3d", "no change": "#54748b"}
    for index, study in enumerate(studies):
        ax.scatter(index, 0, s=130, color="#286a8e", edgecolor="white", linewidth=1.3, zorder=4)
        labels = study["positive_findings"][:3]
        detail = "\n".join(labels) if labels else "no positive finding"
        if len(study["positive_findings"]) > 3:
            detail += f"\n+{len(study['positive_findings']) - 3} more"
        ax.text(index, -0.32, f"Visit {study['study_order']}\nStudy {study['study_id']}\n{study['study_datetime']}\n{study['image_count']} image(s)\n{detail}",
                ha="center", va="top", fontsize=8, linespacing=1.35,
                bbox={"boxstyle": "round,pad=0.35", "facecolor": "#f2f6f8", "edgecolor": "#d5e0e5"})

    handles = [plt.Line2D([0], [0], color=color, lw=2, label=label)
               for label, color in node_colors.items()]
    handles.append(plt.Line2D([0], [0], color=colors["unknown"], lw=2, label="mixed / unclear"))
    ax.legend(handles=handles, loc="upper left", frameon=False, ncol=4)
    ax.set_title(f"Longitudinal chest X-ray timeline · patient {patient_id}\n"
                 "Each node is a study (visit); arrows show explicit comparison annotations", fontsize=14, pad=18)
    ax.text(0.01, 0.97, "Arrow direction: earlier study → later study", transform=ax.transAxes,
            ha="left", va="top", fontsize=9, color="#444")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_patient_images(
    data_dir: Path, patient_id: str, studies: list[dict], path: Path
) -> int:
    """Render available full-frame X-ray PNGs in study order as a contact sheet."""
    archive_path = data_dir / SAMPLE_IMAGE_ARCHIVE
    if not archive_path.exists():
        _plot_image_unavailable(patient_id, path)
        return 0
    with zipfile.ZipFile(archive_path) as archive:
        members = {
            Path(name).name.removesuffix(".dcm.png"): name
            for name in archive.namelist()
            if name.endswith(".dcm.png")
        }
        selected = []
        for study in studies:
            image_id = next((image_id for image_id in study["image_ids"] if image_id in members), None)
            if image_id:
                selected.append((study, image_id, members[image_id]))
        if not selected:
            _plot_image_unavailable(patient_id, path)
            return 0

        columns = 4
        rows = math.ceil(len(selected) / columns)
        fig, axes = plt.subplots(rows, columns, figsize=(16, rows * 4.2), squeeze=False)
        for axis, (study, image_id, member) in zip(axes.flat, selected):
            image = Image.open(BytesIO(archive.read(member))).convert("L")
            axis.imshow(image, cmap="gray")
            axis.set_title(
                f"Visit {study['study_order']} · {study['study_datetime']}\n"
                f"Study {study['study_id']} · {image_id[:18]}…",
                fontsize=8,
            )
            findings = ", ".join(study["positive_findings"][:3]) or "no positive finding label"
            if len(study["positive_findings"]) > 3:
                findings += f" (+{len(study['positive_findings']) - 3} more)"
            axis.set_xlabel(findings, fontsize=8)
            axis.set_xticks([])
            axis.set_yticks([])
            for spine in axis.spines.values():
                spine.set_color("#d5e0e5")
        for axis in axes.flat[len(selected):]:
            axis.axis("off")
        fig.suptitle(
            f"Actual frontal X-ray PNG samples across visits · patient {patient_id}\n"
            "Same patient; one available image per study. Supplied PNGs include annotation boxes, not raw DICOMs.",
            fontsize=13,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        return len(selected)


def _plot_image_unavailable(patient_id: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.text(0.5, 0.57, f"No local X-ray PNG samples found for patient {patient_id}",
            ha="center", va="center", fontsize=14)
    ax.text(0.5, 0.35, "Timeline annotations are still available; original DICOM images are not included locally.",
            ha="center", va="center", fontsize=10, color="#555")
    ax.axis("off")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _plot_disease_changes(
    data_dir: Path,
    patient_id: str,
    relations: list[dict],
    graphs: dict[str, dict],
    path: Path,
    max_pairs: int = 4,
) -> int:
    """Show paired prior/current PNGs with scene-graph comparison regions highlighted."""
    archive_path = data_dir / SAMPLE_IMAGE_ARCHIVE
    if not archive_path.exists():
        _plot_image_unavailable(patient_id, path)
        return 0

    with zipfile.ZipFile(archive_path) as archive:
        image_members = {
            Path(name).name.removesuffix(".dcm.png"): name
            for name in archive.namelist()
            if name.endswith(".dcm.png")
        }
        by_image: dict[tuple[str, str], dict[tuple[str, str, str], dict]] = {}
        for relation in relations:
            statuses = [
                value.rsplit("|", 1)[-1]
                for value in relation["comparison_labels"].split(";")
                if value.startswith("comparison|yes|")
            ]
            status = statuses[0] if len(set(statuses)) == 1 and statuses else "mixed"
            pair = (relation["from_image"], relation["to_image"])
            if not all(image_id in image_members and image_id in graphs for image_id in pair):
                continue
            key = (relation["region"], status, relation["finding_labels"])
            by_image.setdefault(pair, {}).setdefault(key, relation)

        pairs = []
        # Prefer explicit improved/worsened changes, then stable comparisons if needed.
        for preferred in ({"improved", "worsened", "mixed"}, {"no change", "unknown"}):
            for (from_image, to_image), entries in by_image.items():
                candidates = [row for (region, status, finding), row in entries.items() if status in preferred]
                if candidates:
                    candidates.sort(key=lambda row: (row["to_order"], row["from_order"], row["region"]))
                    pairs.append((from_image, to_image, candidates[0]))
            if pairs:
                break
        # Different regions for the same exam pair are informative only up to one representative.
        unique_pairs = []
        seen_exam_pairs = set()
        for from_image, to_image, relation in pairs:
            exam_pair = (relation["from_study"], relation["to_study"])
            if exam_pair not in seen_exam_pairs:
                seen_exam_pairs.add(exam_pair)
                unique_pairs.append((from_image, to_image, relation))
        unique_pairs = unique_pairs[:max_pairs]
        if not unique_pairs:
            fig, ax = plt.subplots(figsize=(9, 3))
            ax.text(0.5, 0.58, f"No paired change annotations with local images for patient {patient_id}",
                    ha="center", va="center", fontsize=13)
            ax.text(0.5, 0.36, "Use the timeline and findings sheet; this patient has no matched image pair to highlight.",
                    ha="center", va="center", fontsize=9, color="#555")
            ax.axis("off")
            fig.savefig(path, dpi=160, bbox_inches="tight")
            plt.close(fig)
            return 0

        ncols = 4
        nrows = math.ceil(len(unique_pairs) / 2)
        fig, axes = plt.subplots(nrows, ncols, figsize=(16, nrows * 5.4), squeeze=False)
        status_colors = {"improved": "#36c976", "worsened": "#ff5252", "no change": "#f2c94c", "mixed": "#bf80ff"}
        for pair_index, (prior_id, later_id, relation) in enumerate(unique_pairs):
            row_index, pair_column = divmod(pair_index, 2)
            color = status_colors.get(relation["comparison_labels"].split("|")[-1].split(";")[0], "#bf80ff")
            finding = relation["finding_labels"].replace(";", ", ") or "finding not specified"
            status = relation["comparison_labels"].replace("comparison|yes|", "").replace(";", ", ") or "comparison unspecified"
            for side, image_id in enumerate((prior_id, later_id)):
                axis = axes[row_index, pair_column * 2 + side]
                image = ImageOps.autocontrast(Image.open(BytesIO(archive.read(image_members[image_id]))).convert("L"))
                axis.imshow(image, cmap="gray")
                graph = graphs[image_id]
                target = next(
                    (obj for obj in graph.get("objects", []) if obj.get("bbox_name") == relation["region"]),
                    None,
                )
                if target and all(key in target for key in ("x1", "y1", "x2", "y2")):
                    x_scale, y_scale = image.width / 224, image.height / 224
                    x1, y1, x2, y2 = (float(target[key]) for key in ("x1", "y1", "x2", "y2"))
                    axis.add_patch(Rectangle(
                        (x1 * x_scale, y1 * y_scale),
                        (x2 - x1) * x_scale,
                        (y2 - y1) * y_scale,
                        linewidth=3.0,
                        edgecolor=color,
                        facecolor="none",
                    ))
                axis.set_xlim(0, image.width)
                axis.set_ylim(image.height, 0)
                date = str(graph.get("StudyDateTime", ""))
                visit = graph.get("StudyOrder", "?")
                axis.set_title(f"{'Earlier' if side == 0 else 'Later'} · visit {visit}\n{date}", fontsize=9)
                axis.set_xlabel(f"Region: {relation['region']}\n{status}: {finding}", fontsize=8, color=color)
                axis.set_xticks([])
                axis.set_yticks([])
        for axis in axes.flat[len(unique_pairs) * 2:]:
            axis.axis("off")
        fig.suptitle(
            f"Disease/comparison regions · patient {patient_id}\n"
            "Boxes mark labeled anatomy regions, not lesion contours: green improved, red worsened, yellow stable, purple mixed.",
            fontsize=13,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.94), h_pad=2.3)
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        return len(unique_pairs)


def analyse_patient_timeline(data_dir: Path, output_dir: Path, patient_id: str = "auto") -> list[Path]:
    """Create a longitudinal graph and integrity report for one patient.

    `patient_id="auto"` chooses a patient with several frontal studies and
    scene graphs. An explicit ID is useful for reproducing an analysis.
    """
    graph_path = data_dir / SCENE_GRAPH_ARCHIVE
    if not graph_path.exists():
        raise FileNotFoundError(f"Scene-graph archive not found: {graph_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    records = _patient_records(data_dir)
    image_archive_path = data_dir / SAMPLE_IMAGE_ARCHIVE
    if image_archive_path.exists():
        with zipfile.ZipFile(image_archive_path) as image_archive:
            image_names = {
                Path(name).name.removesuffix(".dcm.png")
                for name in image_archive.namelist()
                if name.endswith(".dcm.png")
            }
    else:
        image_names = set()

    with zipfile.ZipFile(graph_path) as archive:
        member_by_basename = {
            Path(name).name: name
            for name in archive.namelist()
            if name.endswith("_SceneGraph.json")
        }
        names = set(member_by_basename)
        selected_id = _choose_patient(records, names, image_names) if patient_id.lower() == "auto" else str(patient_id)
        if selected_id not in records:
            raise ValueError(f"Patient {selected_id} is not present in frontal records in {RECORD_LIST}")

        record_studies = records[selected_id]
        expected_ids = {image_id for study in record_studies.values() for image_id in study["images"]}
        graphs = {}
        for image_id in expected_ids:
            member_name = f"{image_id}_SceneGraph.json"
            if member_name in names:
                graph = json.loads(archive.read(member_by_basename[member_name]))
                graphs[str(graph.get("image_id", image_id))] = graph

    if not graphs:
        raise ValueError(f"No scene graphs found for patient {selected_id}")

    study_data: dict[str, dict] = {}
    for study_id, record in record_studies.items():
        study_data[study_id] = {
            "study_id": study_id,
            "expected_image_ids": set(record["images"]),
            "graph_image_ids": set(),
            "orders": set(),
            "dates": set(),
            "findings": set(),
        }
    for image_id, graph in graphs.items():
        study_id = str(graph.get("study_id", ""))
        if study_id not in study_data:
            continue
        data = study_data[study_id]
        data["graph_image_ids"].add(image_id)
        if graph.get("StudyOrder") is not None:
            data["orders"].add(int(graph["StudyOrder"]))
        if graph.get("StudyDateTime"):
            data["dates"].add(str(graph["StudyDateTime"]))
        data["findings"].update(_positive_findings(graph))

    studies = []
    inconsistent_orders, inconsistent_dates = [], []
    for study_id, data in study_data.items():
        if len(data["orders"]) > 1:
            inconsistent_orders.append(study_id)
        if len(data["dates"]) > 1:
            inconsistent_dates.append(study_id)
        studies.append({
            "study_id": study_id,
            "study_order": min(data["orders"]) if data["orders"] else None,
            "study_datetime": min(data["dates"]) if data["dates"] else "",
            "image_count": len(data["expected_image_ids"]),
            "graph_count": len(data["graph_image_ids"]),
            "positive_findings": sorted(data["findings"]),
            "image_ids": sorted(data["expected_image_ids"]),
        })
    studies.sort(key=lambda item: (item["study_order"] is None, item["study_order"] or math.inf, item["study_datetime"], item["study_id"]))
    for index, study in enumerate(studies):
        study["timeline_position"] = index

    all_known_ids = set(graphs)
    relations = []
    dangling_endpoints = []
    non_longitudinal_relations = []
    for current_image, graph in graphs.items():
        for relation in graph.get("relationships", []):
            subject_image = _image_from_object_id(str(relation.get("subject_id", "")))
            object_image = _image_from_object_id(str(relation.get("object_id", "")))
            if subject_image not in all_known_ids or object_image not in all_known_ids:
                dangling_endpoints.append({"current_image": current_image, "subject_image": subject_image, "object_image": object_image})
                continue
            subject_study = str(graphs[subject_image].get("study_id", ""))
            object_study = str(graphs[object_image].get("study_id", ""))
            if subject_study == object_study:
                non_longitudinal_relations.append(current_image)
                continue
            # The current graph is normally the later exam; orient by StudyOrder for safety.
            subject_order = int(graphs[subject_image].get("StudyOrder") or 0)
            object_order = int(graphs[object_image].get("StudyOrder") or 0)
            if subject_order <= object_order:
                from_image, to_image = subject_image, object_image
            else:
                from_image, to_image = object_image, subject_image
            comparison = sorted(label for label in relation.get("relationship_names", []) if str(label).startswith("comparison|yes|"))
            findings = sorted(label.split("|", 2)[-1] for label in relation.get("attributes", [])
                              if str(label).startswith("anatomicalfinding|yes|"))
            relations.append({
                "from_study": str(graphs[from_image].get("study_id", "")),
                "to_study": str(graphs[to_image].get("study_id", "")),
                "from_order": min(subject_order, object_order),
                "to_order": max(subject_order, object_order),
                "from_image": from_image,
                "to_image": to_image,
                "region": relation.get("bbox_name", ""),
                "comparison_labels": ";".join(comparison),
                "finding_labels": ";".join(findings),
                "phrase": " ".join(str(relation.get("phrase", "")).split()),
            })

    chronological_by_date = sorted(studies, key=lambda item: item["study_datetime"])
    date_order_conflicts = [study["study_id"] for i, study in enumerate(chronological_by_date)
                            if i and study["study_order"] is not None and chronological_by_date[i-1]["study_order"] is not None
                            and study["study_order"] < chronological_by_date[i-1]["study_order"]]
    expected_count = len(expected_ids)
    loaded_count = len(graphs)
    integrity = {
        "patient_id": selected_id,
        "frontal_studies_in_record_list": len(record_studies),
        "frontal_images_in_record_list": expected_count,
        "scene_graphs_loaded": loaded_count,
        "missing_scene_graphs": sorted(expected_ids - set(graphs)),
        "unexpected_patient_graphs": sorted(image_id for image_id, graph in graphs.items() if str(graph.get("patient_id")) != selected_id),
        "studies_with_inconsistent_study_order": inconsistent_orders,
        "studies_with_inconsistent_study_datetime": inconsistent_dates,
        "study_order_date_conflicts": date_order_conflicts,
        "explicit_comparison_relations": len(relations),
        "frontal_studies_with_local_sample_images": sum(
            bool(set(study["image_ids"]) & image_names) for study in studies
        ),
        "relations_with_endpoints_outside_selected_patient_graphs": len(dangling_endpoints),
        "relations_within_same_study": len(non_longitudinal_relations),
        "integrity_note": "This checks metadata and relation endpoints for this patient's frontal images; it does not establish clinical correctness or dataset-wide completeness.",
    }

    prefix = f"patient_{selected_id}"
    timeline_path = output_dir / f"{prefix}_timeline.png"
    images_path = output_dir / f"{prefix}_images.png"
    changes_path = output_dir / f"{prefix}_disease_changes.png"
    studies_path = output_dir / f"{prefix}_studies.csv"
    relations_path = output_dir / f"{prefix}_relations.csv"
    integrity_path = output_dir / f"{prefix}_integrity.json"
    _plot_timeline(selected_id, studies, relations, timeline_path)
    image_count = _plot_patient_images(data_dir, selected_id, studies, images_path)
    integrity["images_in_comparison_figure"] = image_count
    highlighted_pairs = _plot_disease_changes(data_dir, selected_id, relations, graphs, changes_path)
    integrity["disease_change_pairs_highlighted"] = highlighted_pairs
    _write_csv(studies_path, ["study_id", "study_order", "study_datetime", "image_count", "graph_count", "image_ids", "positive_findings"], [
        {key: study[key] for key in ("study_id", "study_order", "study_datetime", "image_count", "graph_count")}
        | {"image_ids": ";".join(study["image_ids"]), "positive_findings": ";".join(study["positive_findings"])}
        for study in studies
    ])
    _write_csv(relations_path, ["from_study", "to_study", "from_order", "to_order", "from_image", "to_image", "region", "comparison_labels", "finding_labels", "phrase"], relations)
    integrity_path.write_text(json.dumps(integrity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    outputs = [timeline_path, images_path, changes_path, studies_path, relations_path, integrity_path]
    return outputs
