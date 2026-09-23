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
- Matching CSV files contain the plotted values and sample annotations.

Choose sections with `--include` and optionally remove sections with
`--exclude`:

```bash
uv run python src/scripts/eda.py --include quality distributions
uv run python src/scripts/eda.py --include overview quality distributions --exclude distributions
uv run python src/scripts/eda.py --data-dir /path/to/dataset --output-dir /path/to/eda-reports
```

Available sections are `overview`, `quality`, `distributions`, and
`visualizations`. Label charts use positive `anatomicalfinding` attributes by
default; use `--label-category all` to include all positive scene-graph
categories. Set `--top-labels` and `--sample-count` to change chart/sample
sizes. The scene-graph archive is streamed entry-by-entry. Sample images come
from the supplied bbox PNG archive; the full original DICOM images are not
included in this repository. The default
dataset directory is `physionet.org/files/chest-imagenome/1.0.0/`. The
categorical frequency tracker is bounded per column; adjust its limit with
`--category-limit` (default `5000`).
