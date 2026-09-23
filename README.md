# LongitudinalResearch
Research about Longitudinal Dataset

## Exploratory data analysis (EDA)

The EDA code is in `src/data/analyse/`; CSV files are scanned as streams and
the scene-graph ZIP is processed one image at a time, so large files are not
loaded into memory all at once. Run the script from the repository root:

```bash
uv run python src/scripts/eda.py
```

By default, it runs all sections and writes reports to `reports/eda/`:

- `overview.md` and `file_inventory.csv`: dataset files and CSV dimensions.
- `data_quality.csv`: blank/missing cells, duplicate column names, and rows
  whose field count differs from the header.
- `column_distributions.csv`: numeric min/mean/max and categorical top values.
- `label_distribution.png`: most frequent positive anatomical findings.
- `labels_per_image.png`: distribution of distinct positive findings per image.
- `label_correlation.png`: phi-correlation heatmap for frequent findings.
- `image_counts.png`: image record counts by metadata source and split.
- `sample_images_with_labels.png`: sample annotation PNGs with bbox regions and labels.
- `patient_<id>_timeline.png`: one patient's ordered studies, positive findings,
  and explicit comparison links between examinations.
- `patient_<id>_images.png`: a chronological contact sheet of available X-ray
  images for that same patient (one image per represented study).
- `patient_<id>_disease_changes.png`: paired earlier/later images for up to four
  comparisons, with the reported anatomical region and finding highlighted.
- `patient_<id>_studies.csv`, `patient_<id>_relations.csv`, and
  `patient_<id>_integrity.json`: the graph's source rows and integrity checks.
- Matching CSV files contain the plotted values and sample annotations.

Choose sections with `--include` and optionally remove sections with
`--exclude`:

```bash
uv run python src/scripts/eda.py --include quality distributions
uv run python src/scripts/eda.py --include overview quality distributions --exclude distributions
uv run python src/scripts/eda.py --data-dir /path/to/dataset --output-dir /path/to/eda-reports
```

Available sections are `overview`, `quality`, `distributions`, `visualizations`,
and `patient_timeline`. The timeline defaults to an automatically selected
patient with multiple frontal studies and local image PNGs; specify
`--patient-id 18969313` to make
the selection reproducible, or run only that section with:

```bash
uv run python src/scripts/eda.py --include patient_timeline --patient-id auto
```

Each timeline node is a `study_id` (an examination/visit), not an individual
image. Multiple frontal images from the same study are grouped together.
Arrows represent explicit scene-graph comparison annotations, not a claim that
all visits have pairwise comparisons. The integrity JSON checks image coverage,
study metadata consistency, chronological order, and relation endpoints for
the selected patient's frontal images. If supplied frontal PNGs exist for the
selected patient, the script also creates an actual-image comparison sheet;
otherwise it reports that images are unavailable locally. This repository
contains a subset of PNG samples, not the complete original DICOM collection.
The colored comparison boxes identify anatomy regions referenced by the labels;
they are not pixel-level outlines of a disease or lesion.
Label charts use positive `anatomicalfinding` attributes by
default; use `--label-category all` to include all positive scene-graph
categories. Set `--top-labels` and `--sample-count` to change chart/sample
sizes. The scene-graph archive is streamed entry-by-entry. Sample images come
from the supplied bbox PNG archive; the full original DICOM images are not
included in this repository. The default
dataset directory is `physionet.org/files/chest-imagenome/1.0.0/`. The
categorical frequency tracker is bounded per column; adjust its limit with
`--category-limit` (default `5000`).
