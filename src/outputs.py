# -*- coding: utf-8 -*-
"""
outputs.py — CSV writers (spec §18). Schema-driven and provenance-safe.

Every record-derived CSV carries data_source, last_updated,
data_freshness_status, confidence via the column lists in schema.py.
"""

import os
import csv


def fmt(v):
    """Format a value for CSV output."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        # tidy floats; keep small numbers readable
        if abs(v) >= 1000:
            return f"{v:.2f}"
        return f"{round(v, 4)}"
    if isinstance(v, (list, tuple)):
        return ";".join(str(x) for x in v)
    if isinstance(v, dict):
        return ";".join(f"{k}={x}" for k, x in v.items())
    return str(v)


def write_csv(path, columns, rows, append=False):
    mode = "a" if (append and os.path.exists(path)) else "w"
    write_header = not (append and os.path.exists(path))
    with open(path, mode, newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(columns)
        for row in rows:
            w.writerow([fmt(row.get(c)) for c in columns])
    return path


def rows_from_records(records, columns):
    """Project records onto the given columns (records are dicts)."""
    return [{c: rec.get(c) for c in columns} for rec in records]
