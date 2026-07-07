# Creation/deletion of intermediate CSV files and tolerant ECG CSV loading.

from __future__ import annotations

import csv
import os


ECG_VALUE_FIELDS = ("ecg", "ecg_value", "value", "signal", "sample")


def create_csv(filename="intermediate_results.csv", header=("timestamp", "ecg_value")):
    with open(filename, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)


def read_ecg_csv(filename, row_index: int = 0):
    """Read ECG samples from named columns or from a window-style numeric CSV row.

    Supported forms:
    - timestamp,ecg_value streaming CSVs
    - ecg/value/signal single-column CSVs
    - headerless ECG windows like the repo's ecg.csv; the last column is ignored
      when it looks like a class label.
    """
    with open(filename, "r", newline="") as csv_file:
        sample = csv_file.read(2048)
        csv_file.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
        except csv.Error:
            has_header = False

        if has_header:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
            if not rows:
                raise ValueError(f"No ECG rows found in {filename}")

            field = next((name for name in ECG_VALUE_FIELDS if name in rows[0]), None)
            if field is not None:
                return [float(row[field]) for row in rows if row.get(field) not in ("", None)]

            numeric_fields = [
                name for name in reader.fieldnames or []
                if all(_is_float(row.get(name)) for row in rows if row.get(name) not in ("", None))
            ]
            if not numeric_fields:
                raise ValueError(f"No numeric ECG columns found in {filename}")
            return [float(rows[row_index][field_name]) for field_name in _strip_label_field(rows[row_index], numeric_fields)]

        reader = csv.reader(csv_file)
        rows = [row for row in reader if row]
        if not rows:
            raise ValueError(f"No ECG rows found in {filename}")
        selected = rows[min(row_index, len(rows) - 1)]
        values = [float(value) for value in selected if value.strip()]
        return _strip_label_value(values)


def write_ecg_csv(filename, samples, header=("idx", "ecg")):
    with open(filename, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        for idx, value in enumerate(samples):
            writer.writerow([idx, value])


def delete_csv(filename="intermediate_results.csv"):
    if "intermediate" not in os.path.basename(filename).lower():
        raise ValueError("Refusing to delete non-intermediate CSV file")
    if os.path.exists(filename):
        os.remove(filename)


def _is_float(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _strip_label_field(row, fields):
    if len(fields) <= 1:
        return fields
    last_value = float(row[fields[-1]])
    if last_value.is_integer() and abs(last_value) <= 10:
        return fields[:-1]
    return fields


def _strip_label_value(values):
    if len(values) <= 1:
        return values
    last_value = values[-1]
    if float(last_value).is_integer() and abs(last_value) <= 10:
        return values[:-1]
    return values
