"""
basic_validator.py — Core validation functions.

Covers:
  - Mandatory field check
  - Max-length check
  - Date/Time format check (DATS: DD.MM.YYYY, TIMS: HH:MM:SS)
  - Primary key uniqueness
  - Fixed-value (allowed-values list) check
  - Prohibited newline characters
  - Non-blank optional fields
  - Same-sheet reference check
  - Cross-sheet reference check
  - KDS mapping reference check
  - Overall result rollup

All functions are pure (no side-effects) — they receive DataFrames and
return new DataFrames (or result tuples) without mutating their inputs.
"""

import re
import pandas as pd
from collections import defaultdict

PASS   = "✅"
FAIL   = "❌"


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────

def has_value(val) -> bool:
    """True when a cell contains a meaningful (non-blank, non-NaN) value."""
    if val is None:
        return False
    if isinstance(val, float) and pd.isna(val):
        return False
    s = str(val).strip()
    return s != "" and s.upper() not in ("NAN", "NONE", "NAT")


def _join_errors(errors: list) -> str:
    """Combine a list of error strings into one cell value."""
    return ",\n".join(errors)


def _format_errors(errors: list) -> str:
    return PASS if not errors else _join_errors(errors)


# ─────────────────────────────────────────────────────────────────────────────
# Date / Time format helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate_dats(val: str, length: int, label: str) -> list:
    """Validate DATS type: DD.MM.YYYY."""
    errors = []
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", val):
        errors.append(f"{FAIL} {label}: Invalid date format (expected DD.MM.YYYY, got '{val}')")
    if length:
        digits = len(re.sub(r"\D", "", val))
        if digits != length:
            errors.append(f"{FAIL} {label}: Date digit count {digits} ≠ expected {length}")
    return errors


def _validate_tims(val: str, length: int, label: str) -> list:
    """Validate TIMS type: HH:MM:SS."""
    errors = []
    if not re.match(r"^\d{2}:\d{2}:\d{2}$", val):
        errors.append(f"{FAIL} {label}: Invalid time format (expected HH:MM:SS, got '{val}')")
    else:
        try:
            h, m, s = map(int, val.split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                errors.append(f"{FAIL} {label}: Time values out of range in '{val}'")
        except ValueError:
            errors.append(f"{FAIL} {label}: Non-numeric time values in '{val}'")
    if length:
        digits = len(re.sub(r"\D", "", val))
        if digits != length:
            errors.append(f"{FAIL} {label}: Time digit count {digits} ≠ expected {length}")
    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Mandatory + Length validation (combined for efficiency)
# ─────────────────────────────────────────────────────────────────────────────

def validate_mandatory_and_length(
    df: pd.DataFrame,
    data_columns: list,
    field_metadata: dict,
    label_map: dict = None,
) -> pd.DataFrame:
    """
    Add 'Check Mandatory Validation Result' and 'Check Length Validation Result'.

    Error message format: (TECHNICAL_NAME) Description: <reason>
    e.g. (PRIOK_TGT) Priority_TGT: Missing mandatory value

    Args:
        df            : DataFrame with data rows (no metadata rows).
        data_columns  : Columns to validate (pre-filtered, no ignore cols).
        field_metadata: {col_name: {mandatory: bool, length: int|None, type: str|None}}
        label_map     : {col_name: friendly_description} — used for display label.

    Returns a new DataFrame with two added columns.
    """
    mandatory_results = []
    length_results    = []

    for _, row in df.iterrows():
        mandatory_errors = []
        length_errors    = []

        for col in data_columns:
            if col not in df.columns:
                continue
            val   = str(row.get(col, "")).strip()
            meta  = field_metadata.get(col, {})

            field_type   = meta.get("type")
            field_length = meta.get("length")

            # ── Mandatory ──────────────────────────────────────────
            if meta.get("mandatory") and not has_value(val):
                mandatory_errors.append(f"{FAIL} {col}: Missing mandatory value")

            # ── Length / format ────────────────────────────────────
            if has_value(val):
                if field_type == "DATS":
                    length_errors.extend(_validate_dats(val, field_length, col))
                elif field_type == "TIMS":
                    length_errors.extend(_validate_tims(val, field_length, col))
                elif field_length and len(val) > field_length:
                    length_errors.append(
                        f"{FAIL} {col}: length {len(val)} exceeds max {field_length} (value='{val}')"
                    )

        mandatory_results.append(_format_errors(mandatory_errors))
        length_results.append(_format_errors(length_errors))

    df = df.copy()
    df["Check Mandatory Validation Result"] = mandatory_results
    df["Check Length Validation Result"]    = length_results
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Primary key validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_primary_keys(
    df: pd.DataFrame,
    pk_sets: list,
    label_map: dict,
) -> pd.DataFrame:
    """
    Add one 'Check PK Validation Result (...)' column per primary-key set.

    Args:
        pk_sets: e.g. [["AUFNR_TGT"], ["AUFNR_TGT", "VORNR_TGT"]]
    """
    df = df.copy()

    for key_set in pk_sets:
        valid_cols = [c for c in key_set if c in df.columns]
        if not valid_cols:
            print(f"  ⚠️  PK set {key_set} — no matching columns found, skipped.")
            continue

        key_counts   = defaultdict(int)
        keys_per_row = []

        for _, row in df.iterrows():
            key = " | ".join(str(row.get(c, "")).strip() for c in valid_cols)
            keys_per_row.append(key)
            key_counts[key] += 1

        results = []
        for key in keys_per_row:
            parts = key.split(" | ")
            if all(not p for p in parts):
                results.append(f"{FAIL} Missing PK value(s)")
            elif key_counts[key] > 1:
                results.append(f"{FAIL} Duplicate PK: {key}")
            else:
                results.append(PASS)

        col_name = f"Check PK Validation Result ({' + '.join(valid_cols)})"
        df[col_name] = results

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Fixed-value validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_fixed_values(
    df: pd.DataFrame,
    fixed_fields: list,
    label_map: dict,
) -> pd.DataFrame:
    """
    Add 'Check value fix field on {label}' columns.

    Args:
        fixed_fields: [{"column": "COL_TGT", "allowed_values": ["A", "B"]}]
    """
    df = df.copy()

    for rule in fixed_fields:
        col     = rule.get("column")
        allowed = [str(v).strip() for v in rule.get("allowed_values", [])]

        if not col or col not in df.columns:
            continue

        label      = label_map.get(col, col)
        result_col = f"Check value fix field on {label}"
        results    = []

        for _, row in df.iterrows():
            val = str(row.get(col, "")).strip()
            if not val or val in allowed:
                results.append(PASS)
            else:
                results.append(f"{FAIL} {label}: value '{val}' not in allowed list {allowed}")

        df[result_col] = results

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Prohibited newline validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_prohibited_newlines(
    df: pd.DataFrame,
    newline_fields: list,
    label_map: dict,
) -> pd.DataFrame:
    """Add 'Check Newline Prohibited Field Result'."""
    df      = df.copy()
    results = []

    for _, row in df.iterrows():
        errors = []
        for col in newline_fields:
            if col not in df.columns:
                continue
            val = str(row.get(col, ""))
            if re.search(r"[\r\n]", val):
                errors.append(f"{FAIL} {col}: Newline character not allowed")
        results.append(_format_errors(errors))

    df["Check Newline Prohibited Field Result"] = results
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Non-blank optional validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_non_blank_optional(
    df: pd.DataFrame,
    non_blank_fields: list,
    label_map: dict,
) -> pd.DataFrame:
    """
    Check that every field in non_blank_fields is filled.

    Config key: NON_BLANK_OPTIONAL_FIELDS (list of column names)

    Example config:
        NON_BLANK_OPTIONAL_FIELDS:
          - "KOSTL_TGT"
          - "IWERK_TGT"

    Behaviour: each column is checked independently — ALL must have a value.
    """
    df      = df.copy()
    results = []

    for _, row in df.iterrows():
        errors = []
        for col in non_blank_fields:
            if col not in df.columns:
                continue
            val = str(row.get(col, "")).strip()
            if not val:
                errors.append(f"{FAIL} {col}: missing value")
        results.append(_format_errors(errors))

    df["Check To-Be Optional Field Missing Value"] = results
    return df


def validate_non_blank_optional_any(
    df: pd.DataFrame,
    non_blank_any_groups: list,
    label_map: dict,
) -> pd.DataFrame:
    """
    Check that at least one field in each group is filled.

    Config key: NON_BLANK_OPTIONAL_ANY_FIELDS (list of groups, each group is a list)

    Example config:
        NON_BLANK_OPTIONAL_ANY_FIELDS:
          - ["KOSTL_TGT", "IWERK_TGT"]    # at least one of these must be filled
          - ["ADDAT_TGT", "DATAN_TGT"]    # at least one of these must be filled

    Behaviour: within each group, if ALL columns are blank → fail.
    """
    df      = df.copy()
    results = []

    for _, row in df.iterrows():
        errors = []
        for group in non_blank_any_groups:
            valid_cols = [c for c in group if c in df.columns]
            if not valid_cols:
                continue
            values = [str(row.get(c, "")).strip() for c in valid_cols]
            if all(v == "" for v in values):
                joined = " and ".join(valid_cols)
                errors.append(f"{FAIL} {joined}: must be filled at least 1 column")
        results.append(_format_errors(errors))

    df["Check To-Be Optional Any Field Missing Value"] = results
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Same-sheet reference validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_same_sheet_reference(
    df: pd.DataFrame,
    same_sheet_rules: list,
    label_map: dict,
) -> pd.DataFrame:
    """
    Add 'Check {source_label} in {target_label}' columns.

    Rule format: {"source_column": "COL_A", "target_column": "COL_B"}
    """
    df = df.copy()

    for rule in same_sheet_rules:
        src_col = rule.get("source_column")
        tgt_col = rule.get("target_column")

        if not src_col or not tgt_col:
            continue
        if src_col not in df.columns or tgt_col not in df.columns:
            print(f"  ⚠️  Same-sheet ref: column '{src_col}' or '{tgt_col}' not found — skipped.")
            continue

        tgt_values = set(df[tgt_col].str.strip())
        result_col = f"Check {src_col} in {tgt_col}"
        results    = []

        for _, row in df.iterrows():
            val = str(row.get(src_col, "")).strip()
            if not val or val in tgt_values:
                results.append(PASS)
            else:
                results.append(f"{FAIL} {src_col} '{val}' not found in {tgt_col}")

        df[result_col] = results

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Cross-sheet reference validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_cross_sheet_reference(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    source_columns: list,
    target_columns: list,
    label_map: dict,
    target_sheet_name: str,
) -> tuple:
    """
    Check that (source_col values) all exist as rows in target_df.

    Returns:
        (result_column_name: str, results: list[str])

    Raises:
        KeyError — if required columns are missing from either DataFrame.
    """
    missing_src = [c for c in source_columns if c not in source_df.columns]
    missing_tgt = [c for c in target_columns if c not in target_df.columns]
    if missing_src or missing_tgt:
        raise KeyError(
            f"Cross-sheet ref missing columns — Source: {missing_src}, Target: {missing_tgt}"
        )

    target_keys = set(
        tuple(str(v).strip() for v in row)
        for _, row in target_df[target_columns].iterrows()
    )

    results = []
    for _, row in source_df.iterrows():
        key = tuple(str(row.get(c, "")).strip() for c in source_columns)
        if all(v == "" for v in key) or key in target_keys:
            results.append(PASS)
        else:
            results.append(f"{FAIL} {key} not found in sheet '{target_sheet_name}'")

    readable   = [label_map.get(c, c) for c in source_columns]
    col_name   = f"Check Cross-Sheet: {' + '.join(readable)} in {target_sheet_name}"
    return col_name, results


# ─────────────────────────────────────────────────────────────────────────────
# KDS mapping reference validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_kds_reference(
    df: pd.DataFrame,
    kds_df: pd.DataFrame,
    source_columns: list,
    label_map: dict,
    kds_name: str,
    kds_field_name: str = None,
) -> tuple:
    """
    Validate field values against a KDS reference table.

    KDS sheet layout:
        Row 1  — field names (become pandas column headers after load)
        Row 2+ — allowed values

    Column matching (explicit via config):
        kds_field_name specifies the exact column name in the KDS sheet to validate against.
        e.g. kds_field_name="ARTPR_TOBE", source_columns=["ARTPR_TGT"]
        → checks that ARTPR_TGT value exists in column "ARTPR_TOBE" of the KDS sheet.

    When source_columns has multiple entries and kds_field_name is a single string,
    each source column is matched to the same kds_field_name column.
    To map each source column to a different KDS column, pass kds_field_name as a list.

    Returns:
        (result_column_name: str, results: list[str])

    Raises:
        ValueError — if kds_field_name column not found in KDS sheet.
    """
    # Build col_map: {source_col → kds_column_name}
    if kds_field_name is None:
        raise ValueError(
            f"KDS reference '{kds_name}': 'kds_field_name' is required in config."
        )

    kds_field_names = (
        kds_field_name if isinstance(kds_field_name, list)
        else [kds_field_name] * len(source_columns)
    )

    if len(kds_field_names) != len(source_columns):
        raise ValueError(
            f"KDS reference '{kds_name}': kds_field_name count ({len(kds_field_names)}) "
            f"must match source_columns count ({len(source_columns)})."
        )

    col_map = {}
    for src_col, kds_col in zip(source_columns, kds_field_names):
        if kds_col not in kds_df.columns:
            raise ValueError(
                f"KDS sheet '{kds_name}': column '{kds_col}' not found. "
                f"Available columns: {list(kds_df.columns)}"
            )
        col_map[src_col] = kds_col

    results = []
    for _, row in df.iterrows():
        all_blank = all(str(row.get(c, "")).strip() == "" for c in source_columns)
        if all_blank:
            results.append(PASS)
            continue

        condition = pd.Series([True] * len(kds_df))
        for src_col, kds_col in col_map.items():
            condition &= kds_df[kds_col].str.strip() == str(row.get(src_col, "")).strip()

        if condition.any():
            results.append(PASS)
        else:
            desc_parts = [
                f"{src_col}: '{str(row.get(src_col, '')).strip()}'"
                for src_col in source_columns
            ]
            results.append(f"{FAIL} {', '.join(desc_parts)} not found in KDS '{kds_name}'")

    col_name = f"Check KDS Mapping: {' + '.join(source_columns)} in '{kds_name}'"
    return col_name, results


# ─────────────────────────────────────────────────────────────────────────────
# KDS mapping SRC→TGT validation (optional)
# ─────────────────────────────────────────────────────────────────────────────

WARN = "⚠️"

def validate_kds_mapping(
    df: pd.DataFrame,
    kds_df: pd.DataFrame,
    kds_src_columns: list,
    template_src_columns: list,
    kds_tgt_columns: list,
    template_tgt_columns: list,
    label_map: dict,
    kds_name: str,
) -> tuple:
    """
    Validate that the SRC→TGT mapping in the template matches the KDS reference table.

    Logic per row:
        1. SRC + TGT all blank              → PASS  (skip)
        2. SRC all blank, TGT has values    → look for KDS rows where ASIS is also blank
             2a. KDS has blank-ASIS rows + TGT matches one of them → PASS
             2b. KDS has blank-ASIS rows + TGT does not match      → ❌ FAIL (wrong mapping)
             2c. KDS has no blank-ASIS rows                        → ⚠️ WARNING (cannot verify)
        3. SRC partially blank              → ❌ FAIL  (incomplete AS-IS combination)
        4. SRC not found in KDS             → ❌ FAIL  (AS-IS not in KDS)
        5. SRC found, TGT does not match    → ❌ FAIL  (wrong mapping, shows expected vs got)
        6. SRC found, TGT matches           → PASS

    Returns:
        (result_column_name: str, results: list[str])

    Raises:
        ValueError — if any kds_src_columns or kds_tgt_columns not found in KDS sheet.
    """
    for col in kds_src_columns + kds_tgt_columns:
        if col not in kds_df.columns:
            raise ValueError(
                f"KDS sheet '{kds_name}': column '{col}' not found. "
                f"Available: {list(kds_df.columns)}"
            )

    results = []
    for _, row in df.iterrows():
        src_vals = [str(row.get(c, "")).strip() for c in template_src_columns]
        tgt_vals = [str(row.get(c, "")).strip() for c in template_tgt_columns]

        src_all_blank = all(v == "" for v in src_vals)
        tgt_all_blank = all(v == "" for v in tgt_vals)

        # Case 1: both sides blank → skip
        if src_all_blank and tgt_all_blank:
            results.append(PASS)
            continue

        # Case 2: SRC all blank but TGT has value
        #   → try to match against KDS rows where ASIS columns are also blank
        if src_all_blank:
            blank_src_cond = pd.Series([True] * len(kds_df))
            for kds_col in kds_src_columns:
                blank_src_cond &= kds_df[kds_col].str.strip() == ""

            blank_asis_rows = kds_df[blank_src_cond]

            if blank_asis_rows.empty:
                # 2c: KDS has no blank-ASIS rows → cannot verify
                results.append(f"{WARN} SRC blank — please verify mapping in KDS '{kds_name}'")
            else:
                # Check if any blank-ASIS row has TGT matching template TGT (tuple match)
                full_cond = blank_src_cond.copy()
                for kds_col, tgt_val in zip(kds_tgt_columns, tgt_vals):
                    full_cond &= kds_df[kds_col].str.strip() == tgt_val

                if full_cond.any():
                    # 2a: found matching blank-ASIS row → PASS
                    results.append(PASS)
                else:
                    # 2b: blank-ASIS rows exist but TGT doesn't match any → FAIL
                    errors = []
                    for kds_col, tgt_col, tgt_val in zip(kds_tgt_columns, template_tgt_columns, tgt_vals):
                        allowed = blank_asis_rows[kds_col].str.strip().tolist()
                        if tgt_val not in allowed:
                            errors.append(
                                f"{tgt_col}: expected one of {allowed} got '{tgt_val}'"
                            )
                    results.append(f"{FAIL} Wrong mapping: {', '.join(errors)}" if errors else PASS)
            continue

        # Case 3: SRC partially blank → fail
        if any(v == "" for v in src_vals):
            missing = [template_src_columns[i] for i, v in enumerate(src_vals) if v == ""]
            results.append(f"{FAIL} SRC incomplete — {', '.join(missing)} missing")
            continue

        # Case 4: find KDS row matching SRC combination
        condition = pd.Series([True] * len(kds_df))
        for kds_col, src_val in zip(kds_src_columns, src_vals):
            condition &= kds_df[kds_col].str.strip() == src_val

        matched_rows = kds_df[condition]
        if matched_rows.empty:
            src_display = ", ".join(
                f"({c})='{v}'" for c, v in zip(template_src_columns, src_vals)
            )
            results.append(f"{FAIL} AS-IS ({src_display}) not found in KDS '{kds_name}'")
            continue

        # Case 5 & 6: compare TGT against KDS row
        kds_row = matched_rows.iloc[0]
        errors  = []
        for kds_col, tgt_col, tgt_val in zip(kds_tgt_columns, template_tgt_columns, tgt_vals):
            expected = str(kds_row[kds_col]).strip()
            if tgt_val != expected:
                errors.append(f"{tgt_col}: expected '{expected}' got '{tgt_val}'")

        results.append(f"{FAIL} Wrong mapping: {', '.join(errors)}" if errors else PASS)

    col_name = (
        f"Check KDS Mapping (SRC\u2192TGT): "
        f"{' + '.join(template_src_columns)} \u2192 {' + '.join(template_tgt_columns)} in '{kds_name}'"
    )
    return col_name, results


# ─────────────────────────────────────────────────────────────────────────────
# KDS prohibited reference validation (blacklist — reversed logic)
# ─────────────────────────────────────────────────────────────────────────────

def validate_kds_prohibited(
    df: pd.DataFrame,
    kds_df: pd.DataFrame,
    source_columns: list,
    label_map: dict,
    kds_name: str,
    kds_field_name=None,
) -> tuple:
    """
    Validate that template values do NOT exist in a KDS reference table (blacklist).

    Reversed logic vs validate_kds_reference:
        - Value found in KDS     → ❌ FAIL  (prohibited)
        - Value not in KDS       → ✅ PASS
        - All source cols blank  → ✅ PASS  (skip)

    Accepts kds_field_name as str (single column) or list (composite key).

    Returns:
        (result_column_name: str, results: list[str])
    """
    if kds_field_name is None:
        raise ValueError(
            f"KDS prohibited reference '{kds_name}': 'kds_field_name' or 'kds_columns' is required."
        )

    kds_field_names = (
        kds_field_name if isinstance(kds_field_name, list)
        else [kds_field_name] * len(source_columns)
    )

    if len(kds_field_names) != len(source_columns):
        raise ValueError(
            f"KDS prohibited reference '{kds_name}': kds_field_name count ({len(kds_field_names)}) "
            f"must match source_columns count ({len(source_columns)})."
        )

    col_map = {}
    for src_col, kds_col in zip(source_columns, kds_field_names):
        if kds_col not in kds_df.columns:
            raise ValueError(
                f"KDS sheet '{kds_name}': column '{kds_col}' not found. "
                f"Available columns: {list(kds_df.columns)}"
            )
        col_map[src_col] = kds_col

    results = []
    for _, row in df.iterrows():
        all_blank = all(str(row.get(c, "")).strip() == "" for c in source_columns)
        if all_blank:
            results.append(PASS)
            continue

        condition = pd.Series([True] * len(kds_df))
        for src_col, kds_col in col_map.items():
            condition &= kds_df[kds_col].str.strip() == str(row.get(src_col, "")).strip()

        if condition.any():
            desc_parts = [
                f"{src_col}: '{str(row.get(src_col, '')).strip()}'"
                for src_col in source_columns
            ]
            results.append(
                f"{FAIL} {', '.join(desc_parts)} is prohibited (found in KDS '{kds_name}')"
            )
        else:
            results.append(PASS)

    col_name = f"Check KDS Prohibited: {' + '.join(source_columns)} in '{kds_name}'"
    return col_name, results


# ─────────────────────────────────────────────────────────────────────────────
# Overall result rollup
# ─────────────────────────────────────────────────────────────────────────────

def add_overall_result(df: pd.DataFrame) -> pd.DataFrame:
    """
    Insert 'Check Overall Validation Result' as the FIRST Check* column.

    A row passes overall only when every individual Check column shows PASS (✅).
    """
    df = df.copy()
    check_cols = [
        c for c in df.columns
        if c.startswith("Check ") and c != "Check Overall Validation Result"
    ]
    if not check_cols:
        return df

    overall = []
    for _, row in df.iterrows():
        row_checks = [str(row[c]) for c in check_cols if isinstance(row[c], str)]
        overall.append(PASS if all(v == PASS for v in row_checks) else FAIL)

    first_idx = df.columns.get_loc(check_cols[0])
    df.insert(first_idx, "Check Overall Validation Result", overall)
    return df
