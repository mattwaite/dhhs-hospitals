# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository parses the Nebraska DHHS Hospital Roster PDF into structured CSV data. A GitHub Actions workflow runs quarterly (Jan/Apr/Jul/Oct 15th) to automatically download, parse, and commit updated data.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Parse PDF to CSV (basic)
python parse_hospital_roster.py hospital_roster.pdf hospital_roster.csv

# Parse with date column (used by automation)
python parse_hospital_roster.py input.pdf output.csv --date 2025-01-15

# Run all tests
python -m pytest test_parse_hospital_roster.py test_snapshot.py -v

# Run a single test class
python -m pytest test_parse_hospital_roster.py::TestFacilityTypes -v

# Update snapshot baseline after PDF changes
python test_snapshot.py

# Trigger workflow manually
gh workflow run quarterly_update.yml
```

## Architecture

**parse_hospital_roster.py** - Main parser that extracts hospital data from PDF using pdfplumber. Key functions:
- `extract_text_from_pdf()` - Gets text from all PDF pages
- `parse_hospital_entries()` - Regex-based parsing of the multi-line hospital entry format
- `write_csv()` - Outputs CSV with optional `date_parsed` column

**test_parse_hospital_roster.py** - Validation tests ensuring data quality:
- Facility type counts match expected ranges
- Required fields present (city, county, zip, facility_type)
- Format validation (phone numbers, zip codes, license numbers)
- Known hospital spot checks

**test_snapshot.py** - Detects changes between quarterly runs by comparing against `snapshot_baseline.json`. Reports added/removed hospitals.

## Data Flow

1. PDF downloaded from `https://dhhs.ne.gov/licensure/Documents/Hospital%20Roster.pdf`
2. Stored in `pdfs/hospital_roster_YYYY-MM-DD.pdf`
3. Parsed to `data/hospital_roster_YYYY-MM-DD.csv`
4. Tests validate before commit

## PDF Format Notes

The parser handles several edge cases in the DHHS PDF format:
- Multi-word county names (BOX BUTTE, RED WILLOW, SCOTTS BLUFF)
- City names with apostrophes (O' NEILL)
- Facility type variations (HOSP-REH normalized to REH HOSP)
- PSYCH vs PSY distinction (longer pattern matched first)
