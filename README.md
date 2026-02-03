# Nebraska DHHS Hospital Roster Data

This repository tracks licensed hospitals and hospital capacity in Nebraska by parsing the official Hospital Roster PDF published by the Nebraska Department of Health and Human Services (DHHS).

## Data

The `data/` folder contains CSV files with parsed hospital information, updated quarterly. Each file is named with its parse date: `hospital_roster_YYYY-MM-DD.csv`

### Fields

| Field | Description |
|-------|-------------|
| `city` | City where hospital is located |
| `county` | Nebraska county |
| `zip_code` | 5-digit ZIP code |
| `facility_type` | License type (see below) |
| `facility_name` | Official facility name |
| `license_no` | State license number |
| `address` | Street address |
| `medicare_no` | Medicare provider number |
| `phone` | Main phone number |
| `fax` | Fax number |
| `accreditation` | Accrediting body (TJC, AOA, CARF, DNV, or NONE) |
| `licensee` | Licensed organization name |
| `administrator` | Administrator name |
| `medicare_beds` | Medicare-certified beds |
| `medicaid_beds` | Medicaid-certified beds |
| `medicare_medicaid_beds` | Dual-certified beds |
| `total_licensed_beds` | Total licensed bed count |
| `services` | Special services (e.g., SWING BEDS) |
| `branch_extension` | Branch/extension locations |
| `date_parsed` | Date the PDF was parsed |

### Facility Types

| Code | Description |
|------|-------------|
| HOSP-ACU | General Acute Hospital |
| HOSP-CAH | Critical Access Hospital |
| HOSP-CHD | Children's Hospital |
| HOSP-LT | Long Term Care Hospital |
| PSY | Psychiatric - Licensed Only |
| PSYCH | Psychiatric Hospital |
| REH HOSP | Rehabilitation Hospital |

## Automation

A GitHub Actions workflow runs quarterly on the 15th of January, April, July, and October to:

1. Download the latest PDF from DHHS
2. Parse it to CSV with the current date
3. Run validation tests
4. Commit the new data files

The workflow can also be triggered manually from the Actions tab.

## Source

**PDF URL:** https://dhhs.ne.gov/licensure/Documents/Hospital%20Roster.pdf

**Publisher:** Nebraska DHHS Division of Public Health, Licensure Unit

## Local Usage

### Requirements

- Python 3.9+
- pdfplumber

### Installation

```bash
pip install -r requirements.txt
```

### Parse a PDF

```bash
# Basic usage
python parse_hospital_roster.py hospital_roster.pdf output.csv

# With date column
python parse_hospital_roster.py hospital_roster.pdf output.csv --date 2025-01-15
```

### Run Tests

```bash
python -m pytest test_parse_hospital_roster.py test_snapshot.py -v
```

## License

See [LICENSE](LICENSE) file.
