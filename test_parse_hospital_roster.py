#!/usr/bin/env python3
"""
Tests for the Nebraska DHHS Hospital Roster parser.

These tests ensure consistency across quarterly parsing jobs by validating:
- Total hospital count
- Facility type distributions
- Required field presence
- Data format validation
- Known hospital entries
"""

import csv
import os
import re
from pathlib import Path

import pytest

from parse_hospital_roster import (
    extract_text_from_pdf,
    parse_hospital_entries,
    parse_hospital_roster,
)


# Expected minimum counts by facility type (may increase over time)
EXPECTED_FACILITY_COUNTS = {
    'HOSP-ACU': 25,   # General Acute Hospital (expected ~27)
    'HOSP-CAH': 55,   # Critical Access Hospital (expected ~62)
    'HOSP-CHD': 2,    # Children's Hospital (expected ~3)
    'HOSP-LT': 2,     # Long Term Care Hospital (expected ~3)
    'PSY': 1,         # Psychiatric - Licensed Only
    'PSYCH': 2,       # Psychiatric Hospital (expected ~3)
    'REH HOSP': 1,    # Rehabilitation Hospital
}

# Required fields that must be present for every hospital
REQUIRED_FIELDS = [
    'city',
    'county',
    'zip_code',
    'facility_type',
]

# Fields that should be present for most hospitals (allow some missing)
EXPECTED_FIELDS = [
    'facility_name',
    'license_no',
    'address',
    'phone',
    'fax',
    'total_licensed_beds',
]

# Known hospitals that should always be present (spot check)
KNOWN_HOSPITALS = [
    {'city': 'OMAHA', 'facility_type': 'HOSP-ACU', 'partial_name': 'Nebraska Medical Center'},
    {'city': 'LINCOLN', 'facility_type': 'HOSP-ACU', 'partial_name': 'Bryan'},
    {'city': 'AINSWORTH', 'facility_type': 'HOSP-CAH', 'partial_name': 'Brown County'},
    {'city': 'BOYS TOWN', 'facility_type': 'HOSP-CHD', 'partial_name': 'Boys Town'},
]


@pytest.fixture
def pdf_path():
    """Path to the hospital roster PDF."""
    return Path(__file__).parent / 'hospital_roster.pdf'


@pytest.fixture
def csv_path(tmp_path):
    """Temporary path for CSV output."""
    return tmp_path / 'hospital_roster.csv'


@pytest.fixture
def hospitals(pdf_path, csv_path):
    """Parse hospitals from PDF."""
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")
    return parse_hospital_roster(str(pdf_path), str(csv_path))


class TestTotalCount:
    """Tests for total hospital count."""

    def test_minimum_hospital_count(self, hospitals):
        """Ensure we parse at least a minimum number of hospitals."""
        assert len(hospitals) >= 95, (
            f"Expected at least 95 hospitals, got {len(hospitals)}. "
            "This may indicate a parsing failure."
        )

    def test_maximum_hospital_count(self, hospitals):
        """Ensure we don't parse too many (duplicate detection)."""
        assert len(hospitals) <= 120, (
            f"Expected at most 120 hospitals, got {len(hospitals)}. "
            "This may indicate duplicate parsing."
        )


class TestFacilityTypes:
    """Tests for facility type distribution."""

    def test_has_all_facility_types(self, hospitals):
        """Ensure all expected facility types are present."""
        parsed_types = {h['facility_type'] for h in hospitals}
        for expected_type in EXPECTED_FACILITY_COUNTS.keys():
            assert expected_type in parsed_types, (
                f"Missing facility type: {expected_type}"
            )

    def test_facility_type_counts(self, hospitals):
        """Ensure minimum counts for each facility type."""
        from collections import Counter
        type_counts = Counter(h['facility_type'] for h in hospitals)

        for ftype, min_count in EXPECTED_FACILITY_COUNTS.items():
            actual = type_counts.get(ftype, 0)
            assert actual >= min_count, (
                f"Expected at least {min_count} {ftype} facilities, got {actual}"
            )

    def test_no_unknown_facility_types(self, hospitals):
        """Ensure no unexpected facility types appear."""
        valid_types = set(EXPECTED_FACILITY_COUNTS.keys())
        for h in hospitals:
            assert h['facility_type'] in valid_types, (
                f"Unknown facility type: {h['facility_type']} for {h['city']}"
            )


class TestRequiredFields:
    """Tests for required field presence."""

    def test_required_fields_present(self, hospitals):
        """Ensure all required fields are present for every hospital."""
        for i, h in enumerate(hospitals):
            for field in REQUIRED_FIELDS:
                assert h.get(field), (
                    f"Hospital {i} ({h.get('city', 'unknown')}) "
                    f"missing required field: {field}"
                )

    def test_expected_fields_mostly_present(self, hospitals):
        """Ensure expected fields are present for most hospitals (90%)."""
        for field in EXPECTED_FIELDS:
            count_with_field = sum(1 for h in hospitals if h.get(field))
            percentage = count_with_field / len(hospitals) * 100
            assert percentage >= 90, (
                f"Field '{field}' only present in {percentage:.1f}% of hospitals "
                "(expected >= 90%)"
            )


class TestDataFormat:
    """Tests for data format validation."""

    def test_zip_code_format(self, hospitals):
        """Validate zip code format (5 digits)."""
        zip_pattern = re.compile(r'^\d{5}$')
        for h in hospitals:
            assert zip_pattern.match(h['zip_code']), (
                f"Invalid zip code format: {h['zip_code']} for {h['city']}"
            )

    def test_phone_format(self, hospitals):
        """Validate phone number format where present."""
        phone_pattern = re.compile(r'^\(\d{3}\)\s*\d{3}-\d{4}$')
        for h in hospitals:
            if h.get('phone'):
                assert phone_pattern.match(h['phone']), (
                    f"Invalid phone format: {h['phone']} for {h['city']}"
                )

    def test_fax_format(self, hospitals):
        """Validate fax number format where present."""
        fax_pattern = re.compile(r'^\(\d{3}\)\s*\d{3}-\d{4}$')
        for h in hospitals:
            if h.get('fax'):
                assert fax_pattern.match(h['fax']), (
                    f"Invalid fax format: {h['fax']} for {h['city']}"
                )

    def test_bed_counts_are_numeric(self, hospitals):
        """Validate bed counts are numeric where present."""
        bed_fields = ['medicare_beds', 'medicaid_beds', 'medicare_medicaid_beds', 'total_licensed_beds']
        for h in hospitals:
            for field in bed_fields:
                if h.get(field):
                    assert h[field].isdigit(), (
                        f"Non-numeric {field}: {h[field]} for {h['city']}"
                    )

    def test_license_number_format(self, hospitals):
        """Validate license number format where present."""
        # License numbers are 6 characters, either digits or starting with H
        license_pattern = re.compile(r'^[A-Z]?\d{6}$')
        for h in hospitals:
            if h.get('license_no'):
                assert license_pattern.match(h['license_no']), (
                    f"Invalid license format: {h['license_no']} for {h['city']}"
                )


class TestKnownHospitals:
    """Tests for known hospital entries (spot checks)."""

    def test_known_hospitals_present(self, hospitals):
        """Ensure known hospitals are present with correct data."""
        for known in KNOWN_HOSPITALS:
            matches = [
                h for h in hospitals
                if h['city'] == known['city']
                and h['facility_type'] == known['facility_type']
                and known['partial_name'].lower() in h['facility_name'].lower()
            ]
            assert len(matches) >= 1, (
                f"Known hospital not found: {known['partial_name']} "
                f"in {known['city']} ({known['facility_type']})"
            )


class TestCSVOutput:
    """Tests for CSV output format."""

    def test_csv_file_created(self, pdf_path, csv_path):
        """Ensure CSV file is created."""
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")
        parse_hospital_roster(str(pdf_path), str(csv_path))
        assert csv_path.exists(), "CSV file was not created"

    def test_csv_has_header(self, pdf_path, csv_path):
        """Ensure CSV has proper header row."""
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")
        parse_hospital_roster(str(pdf_path), str(csv_path))

        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)

        assert 'city' in header
        assert 'facility_type' in header
        assert 'facility_name' in header

    def test_csv_row_count_matches(self, hospitals, csv_path):
        """Ensure CSV row count matches parsed count."""
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            csv_count = sum(1 for _ in reader)

        assert csv_count == len(hospitals), (
            f"CSV has {csv_count} rows but parsed {len(hospitals)} hospitals"
        )


class TestPDFExtraction:
    """Tests for PDF text extraction."""

    def test_extracts_multiple_pages(self, pdf_path):
        """Ensure text is extracted from multiple pages."""
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")
        pages_text = extract_text_from_pdf(str(pdf_path))
        assert len(pages_text) >= 20, (
            f"Expected at least 20 pages, got {len(pages_text)}"
        )

    def test_pages_have_content(self, pdf_path):
        """Ensure extracted pages have meaningful content."""
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")
        pages_text = extract_text_from_pdf(str(pdf_path))
        for i, text in enumerate(pages_text):
            assert len(text) > 100, (
                f"Page {i+1} has insufficient content ({len(text)} chars)"
            )


class TestConsistencyChecks:
    """Tests to catch common parsing errors."""

    def test_no_empty_cities(self, hospitals):
        """Ensure no hospitals have empty city names."""
        for h in hospitals:
            assert h['city'].strip(), f"Empty city for {h.get('facility_name', 'unknown')}"

    def test_cities_are_uppercase(self, hospitals):
        """Ensure city names are uppercase (consistent format)."""
        for h in hospitals:
            assert h['city'] == h['city'].upper(), (
                f"City not uppercase: {h['city']}"
            )

    def test_counties_are_uppercase(self, hospitals):
        """Ensure county names are uppercase (consistent format)."""
        for h in hospitals:
            assert h['county'] == h['county'].upper(), (
                f"County not uppercase: {h['county']}"
            )

    def test_no_header_text_in_data(self, hospitals):
        """Ensure header text wasn't accidentally parsed as data."""
        header_markers = ['TOWN (County)', 'Name of Facility', 'Phone Number', 'Licensee']
        for h in hospitals:
            for marker in header_markers:
                assert marker not in h.get('city', ''), f"Header text in city: {h['city']}"
                assert marker not in h.get('facility_name', ''), f"Header text in name: {h['facility_name']}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
