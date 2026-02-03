#!/usr/bin/env python3
"""
Parse Nebraska DHHS Hospital Roster PDF into CSV format.

This script extracts hospital data from the Nebraska Department of Health
and Human Services Hospital Roster PDF and outputs a structured CSV file.
"""

import csv
import re
import sys
from pathlib import Path

import pdfplumber


def extract_text_from_pdf(pdf_path: str) -> list[str]:
    """Extract text from all pages of the PDF."""
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return pages_text


def parse_hospital_entries(pages_text: list[str]) -> list[dict]:
    """Parse hospital entries from extracted text."""
    hospitals = []

    # Combine all pages (skip first two pages - title and summary)
    full_text = "\n".join(pages_text[2:])
    lines = full_text.split("\n")

    # Pattern to match town/county/zip - this starts each hospital entry
    # Note: PSYCH must come before PSY to avoid partial match
    # County can have spaces (e.g., BOX BUTTE, RED WILLOW, SCOTTS BLUFF)
    # City can have apostrophes (e.g., O' NEILL)
    # HOSP-REH is alternate format for REH HOSP
    town_pattern = re.compile(
        r'^([A-Z][A-Z\s\.\']+?)\s*\(([A-Z][A-Z\s]+?)\)\s*-\s*(\d{5})\s+'
        r'(HOSP-ACU|HOSP-CAH|HOSP-CHD|HOSP-LT|HOSP-REH|LTCH/LIC|PSYCH|PSY|REH HOSP)\s*'
        r'(.*)$'
    )

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip header lines
        if (not line or
            line.startswith("HOSPITAL ROSTER") or
            line.startswith("TOWN (County)") or
            line.startswith("Name of Facility") or
            line.startswith("Address") or
            line.startswith("Phone Number") or
            line.startswith("Licensee") or
            line.startswith("Administration")):
            i += 1
            continue

        # Check for start of hospital entry
        town_match = town_pattern.match(line)
        if town_match:
            # Normalize facility type (HOSP-REH -> REH HOSP)
            facility_type = town_match.group(4).strip()
            if facility_type == 'HOSP-REH':
                facility_type = 'REH HOSP'

            hospital = {
                'city': town_match.group(1).strip(),
                'county': town_match.group(2).strip(),
                'zip_code': town_match.group(3).strip(),
                'facility_type': facility_type,
                'facility_name': '',
                'license_no': '',
                'address': '',
                'medicare_no': '',
                'phone': '',
                'fax': '',
                'accreditation': '',
                'licensee': '',
                'administrator': '',
                'medicare_beds': '',
                'medicaid_beds': '',
                'medicare_medicaid_beds': '',
                'total_licensed_beds': '',
                'services': '',
                'branch_extension': ''
            }

            # Parse bed/service info from first line
            remainder = town_match.group(5)
            parse_bed_service_info(remainder, hospital)

            i += 1

            # Process subsequent lines until next hospital entry
            while i < len(lines):
                line = lines[i].strip()

                # Check if we've hit the next hospital entry
                if town_pattern.match(line):
                    break

                # Skip headers that repeat on each page
                if (line.startswith("HOSPITAL ROSTER") or
                    line.startswith("TOWN (County)") or
                    line.startswith("Name of Facility") or
                    line.startswith("Address Fac Type") or
                    line.startswith("Phone Number") or
                    line.startswith("Licensee") or
                    line.startswith("Administration")):
                    i += 1
                    continue

                # Skip empty lines
                if not line:
                    i += 1
                    continue

                # Medicaid line
                if line.startswith("Medicaid -"):
                    medicaid_match = re.search(r'Medicaid\s*-\s*(\d+)', line)
                    if medicaid_match:
                        hospital['medicaid_beds'] = medicaid_match.group(1)
                    i += 1
                    continue

                # Medicare/Medicaid combined line
                if line.startswith("Medicare/Medicaid"):
                    combined_match = re.search(r'Medicare/Medicaid\s*-\s*(\d+)', line)
                    if combined_match:
                        hospital['medicare_medicaid_beds'] = combined_match.group(1)
                    i += 1
                    continue

                # Facility name with license number
                # License can be 6 digits or alphanumeric like H000119
                name_license_match = re.match(r'^(.+?)\s+([A-Z]?\d{6})\s*$', line)
                if name_license_match and not hospital['facility_name']:
                    hospital['facility_name'] = name_license_match.group(1).strip()
                    hospital['license_no'] = name_license_match.group(2).strip()
                    i += 1
                    continue

                # Address with Medicare number and total beds
                # Address followed by 6-digit number, then Total Lic Beds
                addr_match = re.match(
                    r'^(.+?)\s+(\d{6})\s+Total\s+Lic\s+Beds\s*-\s*(\d+)\s*$',
                    line
                )
                if addr_match and not hospital['address']:
                    hospital['address'] = addr_match.group(1).strip()
                    hospital['medicare_no'] = addr_match.group(2).strip()
                    hospital['total_licensed_beds'] = addr_match.group(3).strip()
                    i += 1
                    continue

                # Phone/FAX line with accreditation
                phone_match = re.match(
                    r'^\((\d{3})\)\s*(\d{3})-(\d{4})\s+FAX:\((\d{3})\)\s*(\d{3})-(\d{4})\s*(.*?)$',
                    line
                )
                if phone_match:
                    hospital['phone'] = f"({phone_match.group(1)}) {phone_match.group(2)}-{phone_match.group(3)}"
                    hospital['fax'] = f"({phone_match.group(4)}) {phone_match.group(5)}-{phone_match.group(6)}"
                    accred = phone_match.group(7).strip()
                    if accred in ('TJC', 'AOA', 'CARF', 'DNV', 'NONE'):
                        hospital['accreditation'] = accred
                    i += 1
                    continue

                # Branch/Extension line
                if line.startswith("BRANCH/EXTENSION/OFFSITE:"):
                    hospital['branch_extension'] = line.replace("BRANCH/EXTENSION/OFFSITE:", "").strip()
                    i += 1
                    continue

                # Contact line starting with %
                if line.startswith("%"):
                    i += 1
                    continue

                # Administrator line - name followed by title
                admin_match = re.match(
                    r'^([A-Z][A-Za-z\.\s]+?),\s*(ADMINISTRATOR|CEO|INTERIM ADMINIS.*|'
                    r'CHIEF EXECUTIVE.*|PRESIDENT.*|DIRECTOR.*|COO|CFO|CNO)',
                    line,
                    re.IGNORECASE
                )
                if admin_match and not hospital['administrator']:
                    hospital['administrator'] = admin_match.group(1).strip()
                    i += 1
                    continue

                # Licensee line - organization name (usually ALL CAPS)
                # Should be after phone line but before administrator
                if (re.match(r'^[A-Z][A-Z\s,\.&\'\-]+$', line) and
                    not hospital['licensee'] and
                    hospital['phone'] and
                    'ADMINISTRATOR' not in line and
                    'CEO' not in line):
                    hospital['licensee'] = line.strip()
                    i += 1
                    continue

                # Continuation of address on next page
                if line.endswith(', NE') or re.match(r'^[A-Z]+,\s*NE\s+\d{5}', line):
                    i += 1
                    continue

                i += 1

            hospitals.append(hospital)
        else:
            i += 1

    return hospitals


def parse_bed_service_info(text: str, hospital: dict) -> None:
    """Parse bed count and service information from text."""
    # Medicare beds
    medicare_match = re.search(r'Medicare\s*-\s*(\d+)', text)
    if medicare_match:
        hospital['medicare_beds'] = medicare_match.group(1)

    # Services (like SWING BEDS)
    if 'SWING BEDS' in text:
        hospital['services'] = 'SWING BEDS'


def write_csv(hospitals: list[dict], output_path: str, date_parsed: str = None) -> None:
    """Write hospital data to CSV file.

    Args:
        hospitals: List of hospital dictionaries
        output_path: Path to output CSV file
        date_parsed: Optional date string to add to each row (YYYY-MM-DD format)
    """
    fieldnames = [
        'city',
        'county',
        'zip_code',
        'facility_type',
        'facility_name',
        'license_no',
        'address',
        'medicare_no',
        'phone',
        'fax',
        'accreditation',
        'licensee',
        'administrator',
        'medicare_beds',
        'medicaid_beds',
        'medicare_medicaid_beds',
        'total_licensed_beds',
        'services',
        'branch_extension'
    ]

    # Add date_parsed field if provided
    if date_parsed:
        fieldnames.append('date_parsed')
        for hospital in hospitals:
            hospital['date_parsed'] = date_parsed

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(hospitals)


def parse_hospital_roster(pdf_path: str, output_path: str, date_parsed: str = None) -> list[dict]:
    """Main function to parse hospital roster PDF and write to CSV.

    Args:
        pdf_path: Path to input PDF file
        output_path: Path to output CSV file
        date_parsed: Optional date string to add to each row (YYYY-MM-DD format)

    Returns:
        List of parsed hospital dictionaries
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pages_text = extract_text_from_pdf(pdf_path)
    hospitals = parse_hospital_entries(pages_text)
    write_csv(hospitals, output_path, date_parsed)

    return hospitals


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Parse Nebraska DHHS Hospital Roster PDF')
    parser.add_argument('pdf_path', nargs='?', default='hospital_roster.pdf',
                        help='Path to input PDF file')
    parser.add_argument('output_path', nargs='?', default='hospital_roster.csv',
                        help='Path to output CSV file')
    parser.add_argument('--date', '-d', dest='date_parsed',
                        help='Date parsed in YYYY-MM-DD format (added to each row)')

    args = parser.parse_args()

    hospitals = parse_hospital_roster(args.pdf_path, args.output_path, args.date_parsed)
    print(f"Parsed {len(hospitals)} hospitals to {args.output_path}")
