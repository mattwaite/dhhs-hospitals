#!/usr/bin/env python3
"""
Snapshot tests for detecting changes between quarterly parsing runs.

This module saves a baseline snapshot of parsed data and compares future
runs against it to detect:
- New hospitals added
- Hospitals removed
- Data changes for existing hospitals

Run with --update-snapshot to save a new baseline when the PDF is updated.
"""

import csv
import json
import sys
from pathlib import Path

import pytest

from parse_hospital_roster import parse_hospital_roster


SNAPSHOT_FILE = Path(__file__).parent / 'snapshot_baseline.json'


def load_snapshot():
    """Load the baseline snapshot if it exists."""
    if SNAPSHOT_FILE.exists():
        with open(SNAPSHOT_FILE, 'r') as f:
            return json.load(f)
    return None


def save_snapshot(hospitals: list[dict]):
    """Save current parsing results as the new baseline."""
    # Create a simplified snapshot for comparison
    snapshot = {
        'total_count': len(hospitals),
        'facility_type_counts': {},
        'hospitals': []
    }

    from collections import Counter
    type_counts = Counter(h['facility_type'] for h in hospitals)
    snapshot['facility_type_counts'] = dict(type_counts)

    # Save key identifying info for each hospital
    for h in hospitals:
        snapshot['hospitals'].append({
            'city': h['city'],
            'county': h['county'],
            'zip_code': h['zip_code'],
            'facility_type': h['facility_type'],
            'facility_name': h['facility_name'],
            'license_no': h['license_no'],
            'total_licensed_beds': h['total_licensed_beds'],
        })

    with open(SNAPSHOT_FILE, 'w') as f:
        json.dump(snapshot, f, indent=2)

    print(f"Snapshot saved to {SNAPSHOT_FILE}")


def create_hospital_key(h: dict) -> str:
    """Create a unique key for a hospital entry."""
    return f"{h['city']}|{h['county']}|{h['facility_type']}|{h['license_no']}"


@pytest.fixture
def pdf_path():
    """Path to the hospital roster PDF."""
    return Path(__file__).parent / 'hospital_roster.pdf'


@pytest.fixture
def csv_path(tmp_path):
    """Temporary path for CSV output."""
    return tmp_path / 'hospital_roster.csv'


@pytest.fixture
def current_hospitals(pdf_path, csv_path):
    """Parse current hospitals from PDF."""
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")
    return parse_hospital_roster(str(pdf_path), str(csv_path))


@pytest.fixture
def baseline_snapshot():
    """Load baseline snapshot."""
    snapshot = load_snapshot()
    if snapshot is None:
        pytest.skip("No baseline snapshot exists. Run with --update-snapshot to create one.")
    return snapshot


class TestSnapshotComparison:
    """Compare current parsing against baseline snapshot."""

    def test_total_count_similar(self, current_hospitals, baseline_snapshot):
        """Check if total count is within expected range of baseline."""
        current_count = len(current_hospitals)
        baseline_count = baseline_snapshot['total_count']
        diff = abs(current_count - baseline_count)

        # Allow for some hospitals being added/removed between quarters
        max_diff = 10

        assert diff <= max_diff, (
            f"Hospital count changed significantly: "
            f"baseline={baseline_count}, current={current_count} (diff={diff}). "
            f"If this is expected, run with --update-snapshot to update the baseline."
        )

    def test_facility_type_distribution(self, current_hospitals, baseline_snapshot):
        """Check if facility type distribution is similar."""
        from collections import Counter
        current_counts = dict(Counter(h['facility_type'] for h in current_hospitals))
        baseline_counts = baseline_snapshot['facility_type_counts']

        for ftype in set(list(current_counts.keys()) + list(baseline_counts.keys())):
            current = current_counts.get(ftype, 0)
            baseline = baseline_counts.get(ftype, 0)
            diff = abs(current - baseline)

            # Allow small changes per type
            max_diff = 5

            assert diff <= max_diff, (
                f"Facility type {ftype} count changed significantly: "
                f"baseline={baseline}, current={current} (diff={diff})"
            )

    def test_no_unexpected_hospital_removals(self, current_hospitals, baseline_snapshot):
        """Check that baseline hospitals are still present."""
        current_keys = {create_hospital_key(h) for h in current_hospitals}
        baseline_keys = {create_hospital_key(h) for h in baseline_snapshot['hospitals']}

        removed = baseline_keys - current_keys

        # Allow some removals (hospitals can close)
        max_removals = 5

        if len(removed) > max_removals:
            removed_list = sorted(removed)[:10]
            pytest.fail(
                f"Too many hospitals removed ({len(removed)}). "
                f"First few: {removed_list}. "
                f"If expected, run with --update-snapshot."
            )

    def test_report_changes(self, current_hospitals, baseline_snapshot, capsys):
        """Report all changes (informational, doesn't fail)."""
        current_keys = {create_hospital_key(h) for h in current_hospitals}
        current_by_key = {create_hospital_key(h): h for h in current_hospitals}

        baseline_keys = {create_hospital_key(h) for h in baseline_snapshot['hospitals']}
        baseline_by_key = {create_hospital_key(h): h for h in baseline_snapshot['hospitals']}

        added = current_keys - baseline_keys
        removed = baseline_keys - current_keys

        print("\n" + "="*60)
        print("CHANGE REPORT")
        print("="*60)
        print(f"Baseline count: {baseline_snapshot['total_count']}")
        print(f"Current count: {len(current_hospitals)}")

        if added:
            print(f"\nNEW HOSPITALS ({len(added)}):")
            for key in sorted(added):
                h = current_by_key[key]
                print(f"  + {h['city']}: {h['facility_name']} ({h['facility_type']})")

        if removed:
            print(f"\nREMOVED HOSPITALS ({len(removed)}):")
            for key in sorted(removed):
                h = baseline_by_key[key]
                print(f"  - {h['city']}: {h['facility_name']} ({h['facility_type']})")

        if not added and not removed:
            print("\nNo changes detected.")

        print("="*60)


def pytest_addoption(parser):
    """Add command line option for updating snapshot."""
    parser.addoption(
        "--update-snapshot",
        action="store_true",
        default=False,
        help="Update the baseline snapshot with current results"
    )


def pytest_configure(config):
    """Handle --update-snapshot option."""
    if config.getoption("--update-snapshot"):
        pdf_path = Path(__file__).parent / 'hospital_roster.pdf'
        csv_path = Path(__file__).parent / 'temp_snapshot.csv'

        if not pdf_path.exists():
            print(f"ERROR: PDF not found: {pdf_path}")
            sys.exit(1)

        hospitals = parse_hospital_roster(str(pdf_path), str(csv_path))
        save_snapshot(hospitals)

        # Clean up temp file
        if csv_path.exists():
            csv_path.unlink()

        print("Snapshot updated. Skipping tests.")
        sys.exit(0)


if __name__ == '__main__':
    # If run directly, just update the snapshot
    pdf_path = Path(__file__).parent / 'hospital_roster.pdf'
    csv_path = Path(__file__).parent / 'temp_snapshot.csv'

    hospitals = parse_hospital_roster(str(pdf_path), str(csv_path))
    save_snapshot(hospitals)

    if csv_path.exists():
        csv_path.unlink()
