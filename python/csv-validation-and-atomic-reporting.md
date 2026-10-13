# Reliable CSV ingestion and atomic report publishing in Python

CSV looks simple until a scheduled job receives a missing column, a partially written export, an unexpected encoding, or a duplicate record. A robust pipeline separates **reading**, **validation**, **calculation**, and **publication**. This chapter builds a small command-line program that validates a semicolon-delimited source file and publishes a summary only after all checks succeed.

## When to use this pattern

Use it for scheduled exports, inventory snapshots, attendance aggregates, billing input validation, and other jobs where a reader must never see a half-written report. It is particularly valuable when an existing report should remain intact after a failed run. Do **not** use this implementation as a substitute for a database transaction when multiple writers modify the same dataset concurrently; the final rename is atomic for one file on a local filesystem, not a distributed transaction. For millions of rows, stream aggregates instead of keeping all accepted records in memory.

The example input contains three columns: item_id, group, and amount. Amount is a nonnegative decimal with two fractional digits. Identifiers must be unique. All records must pass validation before the report is replaced.

Sample file named input.csv:

~~~csv
item_id;group;amount
A01;books;12.50
A02;devices;100.00
A03;books;7.25
~~~

Expected summary: 3 accepted rows, total 119.75; books 19.75 and devices 100.00.

## Complete implementation

Save the following as csv_report.py. It uses only the Python standard library and works with Python 3.10+.

~~~python
#!/usr/bin/env python3
"""Validate a semicolon-delimited CSV and atomically publish a JSON summary."""
import argparse
import csv
import json
import os
import tempfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED = ("item_id", "group", "amount")
CENT = Decimal("0.01")


class InputError(Exception):
    """Expected invalid input; the previous report must be preserved."""


def load_and_validate(source: Path):
    seen = set()
    totals = defaultdict(lambda: Decimal("0.00"))
    count = 0

    try:
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";", strict=True)
            if reader.fieldnames is None:
                raise InputError("empty CSV")
            if tuple(reader.fieldnames) != REQUIRED:
                raise InputError(
                    f"headers must be {REQUIRED}, got {reader.fieldnames!r}"
                )
            for line_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise InputError(f"line {line_number}: wrong number of fields")
                identifier = row["item_id"].strip()
                group = row["group"].strip()
                raw_amount = row["amount"].strip()
                if not identifier or not group:
                    raise InputError(f"line {line_number}: empty identifier/group")
                if identifier in seen:
                    raise InputError(f"line {line_number}: duplicate {identifier}")
                try:
                    amount = Decimal(raw_amount)
                except InvalidOperation as exc:
                    raise InputError(
                        f"line {line_number}: invalid amount {raw_amount!r}"
                    ) from exc
                if not amount.is_finite() or amount < 0:
                    raise InputError(f"line {line_number}: invalid amount range")
                if amount != amount.quantize(CENT):
                    raise InputError(f"line {line_number}: more than two decimals")
                seen.add(identifier)
                totals[group] += amount
                count += 1
    except (UnicodeError, csv.Error) as exc:
        raise InputError(f"CSV decoding/parsing failed: {exc}") from exc
    except OSError as exc:
        raise InputError(f"cannot read input: {exc}") from exc

    if count == 0:
        raise InputError("no data rows")

    grand_total = sum(totals.values(), Decimal("0.00"))
    return {
        "record_count": count,
        "total": f"{grand_total:.2f}",
        "groups": {
            group: f"{totals[group]:.2f}" for group in sorted(totals)
        },
    }


def publish_json_atomic(destination: Path, report: dict):
    """Write a temporary file beside the destination, then replace it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            dir=destination.parent, prefix=f".{destination.name}.",
            suffix=".tmp", delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, destination)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.source.resolve() == args.destination.resolve():
            raise InputError("source and destination must be different files")
        report = load_and_validate(args.source)
        publish_json_atomic(args.destination, report)
    except (InputError, OSError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(f"Published {report['record_count']} rows to {args.destination}")


if __name__ == "__main__":
    main()
~~~

Run:

~~~bash
python csv_report.py input.csv summary.json
python -m json.tool summary.json
~~~

Expected report:

~~~json
{
  "record_count": 3,
  "total": "119.75",
  "groups": {
    "books": "19.75",
    "devices": "100.00"
  }
}
~~~

## Why the details matter

**Decimal instead of float.** Binary floating-point arithmetic cannot represent many decimal fractions exactly. Decimal preserves the monetary-style precision in the input, and the output is serialized as a string so downstream JSON readers do not silently convert it back to a binary float.

**UTF-8 with BOM support.** Some spreadsheet exporters prepend a UTF-8 byte-order mark. Encoding utf-8-sig accepts files with or without that marker. A genuine invalid byte sequence still raises an error rather than being silently discarded.

**Strict schema.** The exact column order is intentional here: this is a controlled export contract. For a looser contract, compare header sets and normalize ordering explicitly, but reject duplicate header names. DictReader can otherwise hide ambiguous columns.

**Duplicate detection.** A set of identifiers prevents double counting. If the business rules allow multiple rows per identifier, replace this policy with a documented composite key rather than removing the check without analysis.

**Atomic replacement.** NamedTemporaryFile writes into the same directory as the target. os.replace publishes the finished file in one rename operation on typical local filesystems. fsync flushes the temporary file's content before replacement. For crash durability of the directory entry on Unix-like systems, additional directory fsync may be appropriate. Network shares and cloud-sync folders can have different guarantees; test the actual storage layer.

**Failure isolation.** Validation completes before the output directory is created. Invalid input never overwrites the prior report. An exception during the write cleans up the temporary file when possible. The program returns exit code 2 for expected input or filesystem failures, allowing a scheduler to flag the run.

## Verification with an executable test suite

Save as test_csv_report.py in the same directory:

~~~python
import json
import tempfile
import unittest
from pathlib import Path
from csv_report import InputError, load_and_validate, publish_json_atomic


class CsvReportTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.source = self.root / "input.csv"
        self.target = self.root / "summary.json"

    def write(self, body):
        self.source.write_text(
            "item_id;group;amount\n" + body, encoding="utf-8"
        )

    def test_valid_aggregate(self):
        self.write("A01;books;12.50\nA02;devices;100.00\n"
                   "A03;books;7.25\n")
        result = load_and_validate(self.source)
        self.assertEqual(result["record_count"], 3)
        self.assertEqual(result["total"], "119.75")
        self.assertEqual(result["groups"]["books"], "19.75")

    def test_duplicate_is_rejected_and_old_report_survives(self):
        self.target.write_text('{"previous":true}', encoding="utf-8")
        self.write("A01;books;1.00\nA01;books;2.00\n")
        with self.assertRaises(InputError):
            report = load_and_validate(self.source)
            publish_json_atomic(self.target, report)
        self.assertEqual(
            self.target.read_text(encoding="utf-8"),
            '{"previous":true}',
        )

    def test_invalid_decimal_and_negative(self):
        for body in ("A01;books;bad\n", "A01;books;-1.00\n",
                     "A01;books;1.001\n", "A01;books;NaN\n"):
            with self.subTest(body=body):
                self.write(body)
                with self.assertRaises(InputError):
                    load_and_validate(self.source)

    def test_wrong_fields_and_empty_input(self):
        for body in ("A01;books\n", "A01;books;1.00;extra\n", ""):
            with self.subTest(body=body):
                self.write(body)
                with self.assertRaises(InputError):
                    load_and_validate(self.source)

    def test_publish_creates_valid_json_and_no_temps(self):
        self.write("A01;books;1.25\n")
        publish_json_atomic(self.target, load_and_validate(self.source))
        result = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(result["total"], "1.25")
        self.assertEqual(list(self.root.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
~~~

Run with python -m unittest -v. The tests cover the happy path, duplicates, invalid numbers, malformed field counts, empty input, preservation of a previous report, and the absence of leftover temporary files. For a scheduled deployment, also test read-only destinations, permission errors, and a simulated process crash on the actual filesystem.

## Operational scenarios

1. **Nightly inventory export:** reject duplicated asset IDs; leave yesterday's summary intact and alert the operator when an export is incomplete.
2. **Finance-like totals:** preserve two-decimal arithmetic and prohibit NaN, negative values, and excessive precision before publishing any aggregate.
3. **Data synchronization:** write a complete snapshot to a temporary file and publish only after the source passes schema and integrity checks.
4. **Student exercise datasets:** show line-specific validation errors so learners can correct data rather than manually editing computed results.

A real pipeline should log a run ID, input checksum, source timestamp, number of accepted/rejected records, and final destination. Do not log confidential row values. For strict all-or-nothing input, as implemented here, any rejected row fails the entire run; a permissive workflow can instead quarantine bad rows into a separate protected file with explicit acceptance criteria.

## Common mistakes and acceptance criteria

Avoid opening the destination in write mode before validation; that truncates the old report. Do not treat every exception as success with an empty report. Do not assume an Excel CSV uses a comma delimiter, a dot decimal separator, or UTF-8. Never convert currency-style input through float before Decimal. Do not silently ignore duplicate IDs, missing headers, or extra fields. Check that the scheduler examines the exit code and that the output directory has appropriate permissions.

**Acceptance:** all unit tests pass; a valid source yields the documented totals; invalid input exits nonzero and leaves the previous destination unchanged; no personal data or machine-specific paths appear in the repository; the generated report is parseable JSON. The central rule is simple: **validate first, publish once, and preserve the last good artifact on failure.**
