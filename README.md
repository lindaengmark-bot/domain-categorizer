# Domain Categorizer

CLI utility to classify unique domains from the `parent domain` column in the `citation` sheet of an uploaded Excel file.

## Features
- Reads only `citation` sheet and `parent domain` column.
- Ignores empty rows.
- Deduplicates domains.
- Normalizes subdomains to base domain unless it looks like a separate service (`forum.`, `community.`, etc.).
- Classifies each unique domain into one of the requested categories when possible.
- Suggests a new category if no predefined category clearly fits.
- Outputs results in table-compatible CSV format with confidence and reasoning.
- Prints summary:
  - Category distribution
  - Newly suggested categories
  - Low-confidence domains

## Usage

```bash
python3 domain_classifier.py <input.xlsx> --output classification_results.csv
```

Disable live inspection (faster/offline):

```bash
python3 domain_classifier.py <input.xlsx> --no-inspect
```

## Output columns
- `Parent Domain`
- `Category`
- `Suggested Subcategory`
- `Confidence`
- `Reasoning`

## Optional dependencies for domain inspection
Install these to improve uncertain classifications by inspecting page title/metadata:

```bash
pip install requests beautifulsoup4
```

Core file reading requires:

```bash
pip install pandas openpyxl tabulate
```
