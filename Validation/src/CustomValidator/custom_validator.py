"""
custom_validator.py — Custom business-logic validators for Work Order.

Each validator is a pure function:
  - Returns None  when validation PASSES
  - Returns str   (an error message) when validation FAILS

The registry CUSTOM_VALIDATORS maps config method names to functions.

apply_custom_validations() is the main entry point: it reads the CUSTOM_VALIDATIONS
list from the job config and applies each validator, adding Check* columns to the df.
"""

import re
import pandas as pd
from datetime import datetime


PASS = "✅"
FAIL = "❌"


# ─────────────────────────────────────────────────────────────────────────────
# Individual validators
# ─────────────────────────────────────────────────────────────────────────────

def check_ad_date(value: str):
    """
    Validate a date string in YYYYMMDD format with year 1900–2100.
    '00000000' is treated as blank and passes automatically.

    Returns None on pass, error string on fail.
    """
    val = value.strip()
    if not val or val == "00000000":
        return None
    try:
        dt = datetime.strptime(val, "%Y%m%d")
        if not (1900 <= dt.year <= 2100):
            return f"Year in '{val}' must be between 1900–2100"
        return None
    except ValueError:
        return f"Invalid format '{val}': expected YYYYMMDD"


def check_ad_year(value: str):
    """
    Validate a 4-digit year string (YYYY) in range 1900–2100.

    Returns None on pass, error string on fail.
    """
    val = value.strip()
    if not val:
        return None
    if not re.fullmatch(r"\d{4}", val):
        return f"Invalid year '{val}': expected YYYY"
    year = int(val)
    if not (1900 <= year <= 2100):
        return f"Year '{val}' is out of valid range (1900–2100)"
    return None


def check_mm(value: str):
    """
    Validate a 2-digit month string (MM) in range 01–12.

    Returns None on pass, error string on fail.
    """
    val = value.strip()
    if not val:
        return None
    if not re.fullmatch(r"\d{2}", val):
        return f"Invalid format '{val}': expected MM"
    month = int(val)
    if not (1 <= month <= 12):
        return f"Month '{val}' must be between 01 and 12"
    return None


def check_between_time(inputs: dict):
    """
    Validate that a start datetime is not after an end datetime.

    Expected keys in `inputs`:
        start_date  — DD.MM.YYYY
        start_time  — HH:MM:SS
        end_date    — DD.MM.YYYY
        end_time    — HH:MM:SS

    All four must be provided together; if all are blank the check passes.

    Returns None on pass, error string on fail.
    """
    start_date = inputs.get("start_date", "").strip()
    start_time = inputs.get("start_time", "").strip()
    end_date   = inputs.get("end_date",   "").strip()
    end_time   = inputs.get("end_time",   "").strip()

    # Treat '00000000' as blank for date fields
    if start_date == "00000000":
        start_date = ""
    if end_date == "00000000":
        end_date = ""

    # All blank → nothing to check
    if not any([start_date, start_time, end_date, end_time]):
        return None

    missing = [
        k for k, v in {
            "start_date": start_date,
            "start_time": start_time,
            "end_date":   end_date,
            "end_time":   end_time,
        }.items()
        if not v
    ]
    if missing:
        return "Missing field(s): " + ", ".join(f"{{{f}}}" for f in missing)

    try:
        start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y%m%d %H:%M:%S")
        end_dt   = datetime.strptime(f"{end_date} {end_time}",     "%Y%m%d %H:%M:%S")
    except ValueError:
        return (
            f"Invalid datetime: start='{start_date} {start_time}', "
            f"end='{end_date} {end_time}' (expect YYYYMMDD HH:MM:SS)"
        )

    if start_dt > end_dt:
        return (
            f"Start datetime '{start_date} {start_time}' is after "
            f"end datetime '{end_date} {end_time}'"
        )
    return None


def check_uppercase(value: str):
    """
    Validate that every ASCII English letter (A-Z) in the value is uppercase.
    Non-ASCII characters (Thai, accented, numbers, symbols) are ignored.

    Returns None on pass, error string on fail.
    """
    val = value.strip()
    if not val:
        return None
    english_letters = "".join(c for c in val if c.isalpha() and ord(c) < 128)
    if english_letters and not english_letters.isupper():
        return f"Invalid format '{val}': English letters must be uppercase only (A-Z)"
    if not re.fullmatch(r"[A-Z]*", english_letters):
        return f"Invalid characters in English part of '{val}': only A-Z allowed"
    return None


def check_startup_date(field_data: dict):
    """
    Business rule: Plants 2300, 2304, 4000, 1201 must have startup_date = '01.10.2025'.

    Expected keys in `field_data`:
        planning_plant — e.g. "2300"
        startup_date   — DD.MM.YYYY

    Returns None on pass, error string on fail.
    """
    planning_plant = field_data.get("planning_plant", "").strip()
    startup_date   = field_data.get("startup_date",   "").strip()
    required_plants = {"2300", "2304", "4000", "1201"}
    expected_date   = "20251001"

    # Treat '00000000' as blank
    if startup_date == "00000000":
        startup_date = ""

    if planning_plant in required_plants and startup_date != expected_date:
        return (
            f"Invalid Start-up Date '{startup_date}' for Planning Plant '{planning_plant}': "
            f"expected date is {expected_date}"
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Registry — maps config method names → validator functions
# ─────────────────────────────────────────────────────────────────────────────

CUSTOM_VALIDATORS = {
    "check_ad_date":     check_ad_date,
    "check_ad_year":     check_ad_year,
    "check_mm":          check_mm,
    "check_between_time": check_between_time,
    "check_uppercase":   check_uppercase,
    "check_startup_date": check_startup_date,
}


# ─────────────────────────────────────────────────────────────────────────────
# Main dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def apply_custom_validations(
    df: pd.DataFrame,
    custom_configs: list,
    label_map: dict,
) -> pd.DataFrame:
    """
    Apply all custom validators declared in CUSTOM_VALIDATIONS from the job config.

    Config format examples:

    Single-column validators (the function receives one string value):
        - check_ad_date:
            - ADDAT_TGT
            - DATAN_TGT

    Multi-column validators (the function receives a dict of named inputs):
        - check_between_time:
            - start_date: ANLBD_TGT
              start_time: ANLBZ_TGT
              end_date:   ANLVD_TGT
              end_time:   ANLVZ_TGT

    Args:
        df             : DataFrame with data rows (no metadata rows).
        custom_configs : List of {method_name: rule_items} dicts from config.
        label_map      : {col_name: friendly_label}

    Returns a new DataFrame with added Check* columns.
    """
    df = df.copy()

    for rule_dict in custom_configs:
        if not isinstance(rule_dict, dict):
            continue

        for method_name, rule_items in rule_dict.items():
            validate_fn = CUSTOM_VALIDATORS.get(method_name)
            if validate_fn is None:
                print(f"  ⚠️  Unknown custom validator: '{method_name}' — skipped.")
                continue

            if rule_items is None:
                rule_items = []

            # ── Multi-column validator ────────────────────────────────────
            # rule_items is a list of dicts: [{param_key: column_name, ...}]
            if (
                isinstance(rule_items, list)
                and rule_items
                and isinstance(rule_items[0], dict)
            ):
                for rule in rule_items:
                    col_labels = [col for col in rule.values() if col in df.columns]
                    result_col = f"Check {' + '.join(col_labels)} ({method_name}) Format"
                    results    = []

                    for _, row in df.iterrows():
                        args = {
                            key: str(row.get(col, "")).strip()
                            for key, col in rule.items()
                            if col in df.columns
                        }
                        error = validate_fn(args)
                        if error is None:
                            results.append(PASS)
                        else:
                            # Replace {param_name} placeholders with technical column names
                            for key, col in rule.items():
                                error = error.replace(f"{{{key}}}", col)
                            results.append(f"{FAIL} {error}")

                    df[result_col] = results

            # ── Single-column validator ───────────────────────────────────
            # rule_items is a list of column-name strings
            elif isinstance(rule_items, list):
                for col in rule_items:
                    if col not in df.columns:
                        print(f"  ⚠️  Custom validator '{method_name}': column '{col}' not found — skipped.")
                        continue

                    result_col = f"Check {col} ({method_name}) Format"
                    results    = []

                    for _, row in df.iterrows():
                        val   = str(row.get(col, "")).strip()
                        error = validate_fn(val)
                        results.append(
                            PASS if error is None else f"{FAIL} {col}: {error}"
                        )

                    df[result_col] = results

            else:
                print(
                    f"  ⚠️  Custom validator '{method_name}': unexpected rule_items "
                    f"type {type(rule_items)} — skipped."
                )

    return df
