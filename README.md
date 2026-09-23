# LongitudinalResearch
Research about Longitudinal Dataset

## Exploratory data analysis (EDA)

The EDA code is in `src/data/analyse/`; it scans CSV files as streams, so the
large JSON and ZIP files in the downloaded dataset are inventoried but not
loaded into memory. Run the script from the repository root:

```bash
python src/scripts/eda.py
```

By default, it runs all sections and writes reports to `reports/eda/`:

- `overview.md` and `file_inventory.csv`: dataset files and CSV dimensions.
- `data_quality.csv`: blank/missing cells, duplicate column names, and rows
  whose field count differs from the header.
- `column_distributions.csv`: numeric min/mean/max and categorical top values.

Choose sections with `--include` and optionally remove sections with
`--exclude`:

```bash
python src/scripts/eda.py --include quality distributions
python src/scripts/eda.py --include overview quality distributions --exclude distributions
python src/scripts/eda.py --data-dir /path/to/dataset --output-dir /path/to/eda-reports
```

Available sections are `overview`, `quality`, and `distributions`. The default
dataset directory is `physionet.org/files/chest-imagenome/1.0.0/`. The
categorical frequency tracker is bounded per column; adjust its limit with
`--category-limit` (default `5000`).
