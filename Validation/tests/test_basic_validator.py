"""
test_basic_validator.py — Regression tests for basic_validator functions.

Run with:
    cd Validation
    pytest tests/test_basic_validator.py -v

Purpose: capture current output so any optimization that changes behavior
         is caught immediately.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/BasicValidator"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import pytest
import pandas as pd
from basic_validator import (
    validate_primary_keys,
    validate_fixed_values,
    validate_prohibited_newlines,
    validate_non_blank_optional,
    validate_non_blank_optional_any,
    validate_same_sheet_reference,
    validate_cross_sheet_reference,
    validate_kds_reference,
    validate_kds_mapping,
    validate_kds_prohibited,
    validate_kds_completeness,
    validate_mandatory_and_length,
    PASS,
    FAIL,
)

LABEL = {}  # label_map not used in output assertions


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def col(df, name):
    """Return list of values from a result column."""
    return df[name].tolist()


# ─────────────────────────────────────────────────────────────────────────────
# validate_primary_keys
# ─────────────────────────────────────────────────────────────────────────────

class TestValidatePrimaryKeys:

    def _run(self, data, pk_sets):
        df = pd.DataFrame(data)
        result = validate_primary_keys(df, pk_sets, LABEL)
        return result

    def test_single_col_unique(self):
        df = self._run({"A": ["1", "2", "3"]}, [["A"]])
        assert col(df, "Check PK Validation Result (A)") == [PASS, PASS, PASS]

    def test_single_col_duplicate(self):
        df = self._run({"A": ["1", "1", "3"]}, [["A"]])
        results = col(df, "Check PK Validation Result (A)")
        assert results[0].startswith(FAIL)
        assert results[1].startswith(FAIL)
        assert results[2] == PASS

    def test_all_blank(self):
        df = self._run({"A": ["", "", ""]}, [["A"]])
        results = col(df, "Check PK Validation Result (A)")
        assert all(r.startswith(FAIL) for r in results)

    def test_composite_key_unique(self):
        df = self._run({"A": ["1", "1"], "B": ["X", "Y"]}, [["A", "B"]])
        assert col(df, "Check PK Validation Result (A + B)") == [PASS, PASS]

    def test_composite_key_duplicate(self):
        df = self._run({"A": ["1", "1"], "B": ["X", "X"]}, [["A", "B"]])
        results = col(df, "Check PK Validation Result (A + B)")
        assert all(r.startswith(FAIL) for r in results)

    def test_multiple_pk_sets(self):
        df = self._run({"A": ["1", "1"], "B": ["X", "Y"]}, [["A"], ["A", "B"]])
        assert col(df, "Check PK Validation Result (A)")[0].startswith(FAIL)
        assert col(df, "Check PK Validation Result (A + B)") == [PASS, PASS]


# ─────────────────────────────────────────────────────────────────────────────
# validate_fixed_values
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateFixedValues:

    def _run(self, data, rules):
        df = pd.DataFrame(data)
        return validate_fixed_values(df, rules, LABEL)

    def test_value_in_allowed(self):
        df = self._run({"COL": ["A", "B"]}, [{"column": "COL", "allowed_values": ["A", "B"]}])
        assert col(df, "Check value fix field on COL") == [PASS, PASS]

    def test_value_not_in_allowed(self):
        df = self._run({"COL": ["A", "C"]}, [{"column": "COL", "allowed_values": ["A", "B"]}])
        results = col(df, "Check value fix field on COL")
        assert results[0] == PASS
        assert results[1].startswith(FAIL)

    def test_blank_value_passes(self):
        df = self._run({"COL": ["", "A"]}, [{"column": "COL", "allowed_values": ["A"]}])
        assert col(df, "Check value fix field on COL") == [PASS, PASS]

    def test_condition_skip(self):
        df = self._run(
            {"COL": ["X", "X"], "SRC": ["ECC", "PE1"]},
            [{"column": "COL", "allowed_values": ["A"], "condition": {"column": "SRC", "values": ["ECC"]}}],
        )
        results = col(df, "Check value fix field on COL")
        assert results[0].startswith(FAIL)  # SRC=ECC → checked
        assert results[1] == PASS           # SRC=PE1 → skipped

    def test_condition_and_logic(self):
        df = self._run(
            {"COL": ["X", "X", "X"], "S1": ["ECC", "ECC", "PE1"], "S2": ["Y", "Z", "Y"]},
            [{"column": "COL", "allowed_values": ["A"],
              "condition": [{"column": "S1", "values": ["ECC"]}, {"column": "S2", "values": ["Y"]}]}],
        )
        results = col(df, "Check value fix field on COL")
        assert results[0].startswith(FAIL)  # both conditions met
        assert results[1] == PASS           # S2=Z → skip
        assert results[2] == PASS           # S1=PE1 → skip

    def test_whitespace_trimmed(self):
        df = self._run({"COL": [" A "]}, [{"column": "COL", "allowed_values": ["A"]}])
        assert col(df, "Check value fix field on COL") == [PASS]


# ─────────────────────────────────────────────────────────────────────────────
# validate_prohibited_newlines
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateProhibitedNewlines:

    def _run(self, data, fields):
        df = pd.DataFrame(data)
        return validate_prohibited_newlines(df, fields, LABEL)

    def test_no_newline(self):
        df = self._run({"A": ["hello", "world"]}, ["A"])
        assert col(df, "Check Newline Prohibited Field Result") == [PASS, PASS]

    def test_newline_n(self):
        df = self._run({"A": ["hel\nlo"]}, ["A"])
        assert col(df, "Check Newline Prohibited Field Result")[0].startswith(FAIL)

    def test_newline_r(self):
        df = self._run({"A": ["hel\rlo"]}, ["A"])
        assert col(df, "Check Newline Prohibited Field Result")[0].startswith(FAIL)

    def test_multiple_cols_one_fail(self):
        df = self._run({"A": ["ok"], "B": ["bad\nval"]}, ["A", "B"])
        assert col(df, "Check Newline Prohibited Field Result")[0].startswith(FAIL)

    def test_multiple_cols_all_ok(self):
        df = self._run({"A": ["ok"], "B": ["fine"]}, ["A", "B"])
        assert col(df, "Check Newline Prohibited Field Result") == [PASS]


# ─────────────────────────────────────────────────────────────────────────────
# validate_non_blank_optional
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateNonBlankOptional:

    def _run(self, data, fields):
        df = pd.DataFrame(data)
        return validate_non_blank_optional(df, fields, LABEL)

    def test_all_filled(self):
        df = self._run({"A": ["x"], "B": ["y"]}, ["A", "B"])
        assert col(df, "Check To-Be Optional Field Missing Value") == [PASS]

    def test_one_missing(self):
        df = self._run({"A": ["x"], "B": [""]}, ["A", "B"])
        assert col(df, "Check To-Be Optional Field Missing Value")[0].startswith(FAIL)

    def test_plain_string_format(self):
        df = self._run({"A": [""]}, ["A"])
        assert col(df, "Check To-Be Optional Field Missing Value")[0].startswith(FAIL)

    def test_dict_format_no_condition(self):
        df = self._run({"A": [""]}, [{"column": "A"}])
        assert col(df, "Check To-Be Optional Field Missing Value")[0].startswith(FAIL)

    def test_condition_skip(self):
        df = self._run(
            {"A": ["", ""], "SRC": ["ECC", "PE1"]},
            [{"column": "A", "condition": {"column": "SRC", "values": ["ECC"]}}],
        )
        results = col(df, "Check To-Be Optional Field Missing Value")
        assert results[0].startswith(FAIL)  # ECC → checked
        assert results[1] == PASS           # PE1 → skipped

    def test_mixed_plain_and_dict(self):
        df = self._run(
            {"A": ["x"], "B": [""], "SRC": ["PE1"]},
            ["A", {"column": "B", "condition": {"column": "SRC", "values": ["ECC"]}}],
        )
        # A filled → ok; B skipped (PE1 ≠ ECC)
        assert col(df, "Check To-Be Optional Field Missing Value") == [PASS]


# ─────────────────────────────────────────────────────────────────────────────
# validate_non_blank_optional_any
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateNonBlankOptionalAny:

    def _run(self, data, groups):
        df = pd.DataFrame(data)
        return validate_non_blank_optional_any(df, groups, LABEL)

    def test_one_filled_in_group(self):
        df = self._run({"A": ["x"], "B": [""]}, [["A", "B"]])
        assert col(df, "Check To-Be Optional Any Field Missing Value") == [PASS]

    def test_all_blank_in_group(self):
        df = self._run({"A": [""], "B": [""]}, [["A", "B"]])
        assert col(df, "Check To-Be Optional Any Field Missing Value")[0].startswith(FAIL)

    def test_dict_format_condition_skip(self):
        df = self._run(
            {"A": [""], "B": [""], "SRC": ["PE1"]},
            [{"columns": ["A", "B"], "condition": {"column": "SRC", "values": ["ECC"]}}],
        )
        assert col(df, "Check To-Be Optional Any Field Missing Value") == [PASS]

    def test_dict_format_condition_check(self):
        df = self._run(
            {"A": [""], "B": [""], "SRC": ["ECC"]},
            [{"columns": ["A", "B"], "condition": {"column": "SRC", "values": ["ECC"]}}],
        )
        assert col(df, "Check To-Be Optional Any Field Missing Value")[0].startswith(FAIL)

    def test_plain_list_format(self):
        df = self._run({"A": ["v"], "B": [""]}, [["A", "B"]])
        assert col(df, "Check To-Be Optional Any Field Missing Value") == [PASS]


# ─────────────────────────────────────────────────────────────────────────────
# validate_same_sheet_reference
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateSameSheetReference:

    def _run(self, data, rules):
        df = pd.DataFrame(data)
        return validate_same_sheet_reference(df, rules, LABEL)

    def test_value_found(self):
        # A values ["1","2"] both exist in B values ["1","2","3"] — same-length DF required
        df = self._run({"A": ["1", "2", "3"], "B": ["1", "2", "3"]}, [{"source_column": "A", "target_column": "B"}])
        assert col(df, "Check A in B") == [PASS, PASS, PASS]

    def test_value_not_found(self):
        # A[0]="9" not in B; A[1]="1" in B
        df = self._run({"A": ["9", "1"], "B": ["1", "2"]}, [{"source_column": "A", "target_column": "B"}])
        results = col(df, "Check A in B")
        assert results[0].startswith(FAIL)
        assert results[1] == PASS

    def test_blank_passes(self):
        df = self._run({"A": ["", "1"], "B": ["1", "2"]}, [{"source_column": "A", "target_column": "B"}])
        assert col(df, "Check A in B")[0] == PASS

    def test_whitespace_trimmed(self):
        df = self._run({"A": [" 1 ", "2"], "B": ["1", "2"]}, [{"source_column": "A", "target_column": "B"}])
        assert col(df, "Check A in B") == [PASS, PASS]


# ─────────────────────────────────────────────────────────────────────────────
# validate_cross_sheet_reference
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateCrossSheetReference:

    def _run(self, src_data, tgt_data, src_cols, tgt_cols):
        src = pd.DataFrame(src_data)
        tgt = pd.DataFrame(tgt_data)
        col_name, results = validate_cross_sheet_reference(src, tgt, src_cols, tgt_cols, LABEL, "TargetSheet")
        src[col_name] = results
        return src, col_name

    def test_single_col_found(self):
        df, c = self._run({"A": ["1"]}, {"B": ["1", "2"]}, ["A"], ["B"])
        assert col(df, c) == [PASS]

    def test_single_col_not_found(self):
        df, c = self._run({"A": ["9"]}, {"B": ["1", "2"]}, ["A"], ["B"])
        assert col(df, c)[0].startswith(FAIL)

    def test_all_blank_passes(self):
        df, c = self._run({"A": [""]}, {"B": ["1"]}, ["A"], ["B"])
        assert col(df, c) == [PASS]

    def test_composite_key_found(self):
        df, c = self._run(
            {"A": ["1"], "B": ["X"]},
            {"C": ["1"], "D": ["X"]},
            ["A", "B"], ["C", "D"],
        )
        assert col(df, c) == [PASS]

    def test_composite_key_not_found(self):
        df, c = self._run(
            {"A": ["1"], "B": ["Z"]},
            {"C": ["1"], "D": ["X"]},
            ["A", "B"], ["C", "D"],
        )
        assert col(df, c)[0].startswith(FAIL)

    def test_whitespace_trimmed(self):
        df, c = self._run({"A": [" 1 "]}, {"B": ["1"]}, ["A"], ["B"])
        assert col(df, c) == [PASS]


# ─────────────────────────────────────────────────────────────────────────────
# validate_kds_reference
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateKdsReference:

    def _kds(self, data):
        return pd.DataFrame(data)

    def _run(self, template_data, kds_data, src_cols, kds_field_name, condition=None):
        df = pd.DataFrame(template_data)
        kds = self._kds(kds_data)
        col_name, results = validate_kds_reference(
            df, kds, src_cols, LABEL, "KDS_TEST",
            kds_field_name=kds_field_name, condition=condition,
        )
        df[col_name] = results
        return df, col_name

    def test_single_col_found(self):
        df, c = self._run({"A": ["X"]}, {"K": ["X", "Y"]}, ["A"], "K")
        assert col(df, c) == [PASS]

    def test_single_col_not_found(self):
        df, c = self._run({"A": ["Z"]}, {"K": ["X", "Y"]}, ["A"], "K")
        assert col(df, c)[0].startswith(FAIL)

    def test_all_blank_passes(self):
        df, c = self._run({"A": [""]}, {"K": ["X"]}, ["A"], "K")
        assert col(df, c) == [PASS]

    def test_condition_skip(self):
        df, c = self._run(
            {"A": ["Z", "Z"], "SRC": ["ECC", "PE1"]},
            {"K": ["X"]},
            ["A"], "K",
            condition={"column": "SRC", "values": ["ECC"]},
        )
        results = col(df, c)
        assert results[0].startswith(FAIL)  # ECC → checked, Z not in KDS
        assert results[1] == PASS           # PE1 → skipped

    def test_composite_key_found(self):
        df, c = self._run(
            {"A": ["1"], "B": ["X"]},
            {"KA": ["1"], "KB": ["X"]},
            ["A", "B"], ["KA", "KB"],
        )
        assert col(df, c) == [PASS]

    def test_composite_key_not_found(self):
        df, c = self._run(
            {"A": ["1"], "B": ["Z"]},
            {"KA": ["1"], "KB": ["X"]},
            ["A", "B"], ["KA", "KB"],
        )
        assert col(df, c)[0].startswith(FAIL)

    def test_whitespace_trimmed(self):
        df, c = self._run({"A": [" X "]}, {"K": ["X"]}, ["A"], "K")
        assert col(df, c) == [PASS]

    def test_kds_whitespace_trimmed(self):
        df, c = self._run({"A": ["X"]}, {"K": [" X "]}, ["A"], "K")
        assert col(df, c) == [PASS]

    def test_multiple_rows(self):
        df, c = self._run(
            {"A": ["X", "Y", "Z"]},
            {"K": ["X", "Y"]},
            ["A"], "K",
        )
        results = col(df, c)
        assert results[0] == PASS
        assert results[1] == PASS
        assert results[2].startswith(FAIL)


# ─────────────────────────────────────────────────────────────────────────────
# validate_kds_prohibited
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateKdsProhibited:

    def _run(self, template_data, kds_data, src_cols, kds_field_name):
        df = pd.DataFrame(template_data)
        kds = pd.DataFrame(kds_data)
        col_name, results = validate_kds_prohibited(
            df, kds, src_cols, LABEL, "KDS_PROHIBIT",
            kds_field_name=kds_field_name,
        )
        df[col_name] = results
        return df, col_name

    def test_not_in_kds_passes(self):
        df, c = self._run({"A": ["Z"]}, {"K": ["X", "Y"]}, ["A"], "K")
        assert col(df, c) == [PASS]

    def test_found_in_kds_fails(self):
        df, c = self._run({"A": ["X"]}, {"K": ["X", "Y"]}, ["A"], "K")
        assert col(df, c)[0].startswith(FAIL)

    def test_blank_passes(self):
        df, c = self._run({"A": [""]}, {"K": ["X"]}, ["A"], "K")
        assert col(df, c) == [PASS]

    def test_composite_key_found_fails(self):
        df, c = self._run(
            {"A": ["1"], "B": ["X"]},
            {"KA": ["1"], "KB": ["X"]},
            ["A", "B"], ["KA", "KB"],
        )
        assert col(df, c)[0].startswith(FAIL)

    def test_composite_key_not_found_passes(self):
        df, c = self._run(
            {"A": ["1"], "B": ["Z"]},
            {"KA": ["1"], "KB": ["X"]},
            ["A", "B"], ["KA", "KB"],
        )
        assert col(df, c) == [PASS]

    def test_whitespace_trimmed(self):
        df, c = self._run({"A": [" X "]}, {"K": ["X"]}, ["A"], "K")
        assert col(df, c)[0].startswith(FAIL)


# ─────────────────────────────────────────────────────────────────────────────
# validate_kds_mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateKdsMapping:

    def _run(self, template_data, kds_data,
             kds_src_cols, tmpl_src_cols,
             kds_tgt_cols, tmpl_tgt_cols,
             condition=None):
        df  = pd.DataFrame(template_data)
        kds = pd.DataFrame(kds_data)
        col_name, results = validate_kds_mapping(
            df, kds,
            kds_src_cols, tmpl_src_cols,
            kds_tgt_cols, tmpl_tgt_cols,
            LABEL, "KDS_MAP",
            condition=condition,
        )
        df[col_name] = results
        return df, col_name

    def test_case1_both_blank_pass(self):
        df, c = self._run(
            {"S": [""], "T": [""]},
            {"KS": ["A"], "KT": ["X"]},
            ["KS"], ["S"], ["KT"], ["T"],
        )
        assert col(df, c) == [PASS]

    def test_case6_src_found_tgt_match_pass(self):
        df, c = self._run(
            {"S": ["A"], "T": ["X"]},
            {"KS": ["A"], "KT": ["X"]},
            ["KS"], ["S"], ["KT"], ["T"],
        )
        assert col(df, c) == [PASS]

    def test_case5_src_found_tgt_mismatch_fail(self):
        df, c = self._run(
            {"S": ["A"], "T": ["Z"]},
            {"KS": ["A"], "KT": ["X"]},
            ["KS"], ["S"], ["KT"], ["T"],
        )
        assert col(df, c)[0].startswith(FAIL)

    def test_case4_src_not_found_fail(self):
        df, c = self._run(
            {"S": ["B"], "T": ["X"]},
            {"KS": ["A"], "KT": ["X"]},
            ["KS"], ["S"], ["KT"], ["T"],
        )
        assert col(df, c)[0].startswith(FAIL)

    def test_case3_src_partial_blank_fail(self):
        df, c = self._run(
            {"S1": ["A"], "S2": [""], "T": ["X"]},
            {"KS1": ["A"], "KS2": ["B"], "KT": ["X"]},
            ["KS1", "KS2"], ["S1", "S2"], ["KT"], ["T"],
        )
        assert col(df, c)[0].startswith(FAIL)

    def test_case2a_src_blank_tgt_matches_blank_asis_pass(self):
        df, c = self._run(
            {"S": [""], "T": ["X"]},
            {"KS": ["", "A"], "KT": ["X", "Y"]},
            ["KS"], ["S"], ["KT"], ["T"],
        )
        assert col(df, c) == [PASS]

    def test_case2b_src_blank_tgt_no_match_fail(self):
        df, c = self._run(
            {"S": [""], "T": ["Z"]},
            {"KS": ["", "A"], "KT": ["X", "Y"]},
            ["KS"], ["S"], ["KT"], ["T"],
        )
        assert col(df, c)[0].startswith(FAIL)

    def test_case2c_src_blank_no_blank_asis_warn(self):
        df, c = self._run(
            {"S": [""], "T": ["X"]},
            {"KS": ["A"], "KT": ["X"]},
            ["KS"], ["S"], ["KT"], ["T"],
        )
        result = col(df, c)[0]
        assert "⚠️" in result or result == PASS  # warning case

    def test_condition_skip(self):
        df, c = self._run(
            {"S": ["B"], "T": ["X"], "SRC": ["PE1"]},
            {"KS": ["A"], "KT": ["X"]},
            ["KS"], ["S"], ["KT"], ["T"],
            condition={"column": "SRC", "values": ["ECC"]},
        )
        assert col(df, c) == [PASS]  # PE1 → skipped

    def test_whitespace_trimmed(self):
        df, c = self._run(
            {"S": [" A "], "T": [" X "]},
            {"KS": ["A"], "KT": ["X"]},
            ["KS"], ["S"], ["KT"], ["T"],
        )
        assert col(df, c) == [PASS]


# ─────────────────────────────────────────────────────────────────────────────
# validate_kds_completeness
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateKdsCompleteness:

    def _run(self, template_data, kds_data, src_col, kds_field, condition=None):
        df  = pd.DataFrame(template_data)
        kds = pd.DataFrame(kds_data)
        col_name, results = validate_kds_completeness(
            df, kds, src_col, LABEL, "KDS_COMP", kds_field, condition=condition,
        )
        df[col_name] = results
        return df, col_name

    def test_all_kds_values_present_pass(self):
        df, c = self._run(
            {"A": ["X", "Y", "Z"]},
            {"K": ["X", "Y", "Z"]},
            "A", "K",
        )
        assert col(df, c) == [PASS, PASS, PASS]

    def test_missing_kds_value_fail(self):
        df, c = self._run(
            {"A": ["X", "Y"]},
            {"K": ["X", "Y", "Z"]},
            "A", "K",
        )
        results = col(df, c)
        assert all(r.startswith(FAIL) for r in results)
        assert "Z" in results[0]

    def test_condition_only_active_rows_checked(self):
        # KDS has [X, Y]. ECC rows have A=X only. Y exists only in PE1 (skipped).
        # → template_values from ECC = {X}; KDS = {X, Y}; missing = {Y} → FAIL for ECC row
        # PE1 row → skipped → PASS
        df, c = self._run(
            {"A": ["X", "Y"], "SRC": ["ECC", "PE1"]},
            {"K": ["X", "Y"]},
            "A", "K",
            condition={"column": "SRC", "values": ["ECC"]},
        )
        results = col(df, c)
        assert results[0].startswith(FAIL)  # ECC row: Y missing from active rows
        assert results[1] == PASS           # PE1 → skipped

    def test_condition_all_kds_covered_by_active_rows(self):
        # ECC rows supply both X and Y → KDS fully covered → PASS
        df, c = self._run(
            {"A": ["X", "Y", "Z"], "SRC": ["ECC", "ECC", "PE1"]},
            {"K": ["X", "Y"]},
            "A", "K",
            condition={"column": "SRC", "values": ["ECC"]},
        )
        results = col(df, c)
        assert results[0] == PASS   # ECC, X present, KDS covered
        assert results[1] == PASS   # ECC, Y present, KDS covered
        assert results[2] == PASS   # PE1 → skipped

    def test_condition_missing_value_only_active_fail(self):
        # KDS has [X, Y, Z]. ECC rows have A=[X] only. Z missing from ECC rows → FAIL
        df, c = self._run(
            {"A": ["X", "Y"], "SRC": ["ECC", "PE1"]},
            {"K": ["X", "Y", "Z"]},
            "A", "K",
            condition={"column": "SRC", "values": ["ECC"]},
        )
        results = col(df, c)
        assert results[0].startswith(FAIL)  # ECC → checked, missing Y and Z
        assert results[1] == PASS           # PE1 → skipped


# ─────────────────────────────────────────────────────────────────────────────
# validate_mandatory_and_length
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateMandatoryAndLength:

    def _run(self, data, metadata):
        df = pd.DataFrame(data)
        data_cols = list(data.keys())
        return validate_mandatory_and_length(df, data_cols, metadata, label_map=LABEL)

    def test_mandatory_filled_pass(self):
        df = self._run({"A": ["val"]}, {"A": {"mandatory": True, "length": None, "type": None, "system_generated": False}})
        assert col(df, "Check Mandatory Validation Result") == [PASS]

    def test_mandatory_blank_fail(self):
        df = self._run({"A": [""]}, {"A": {"mandatory": True, "length": None, "type": None, "system_generated": False}})
        assert col(df, "Check Mandatory Validation Result")[0].startswith(FAIL)

    def test_optional_blank_pass(self):
        df = self._run({"A": [""]}, {"A": {"mandatory": False, "length": None, "type": None, "system_generated": False}})
        assert col(df, "Check Mandatory Validation Result") == [PASS]

    def test_length_exceeded_fail(self):
        df = self._run({"A": ["ABCDE"]}, {"A": {"mandatory": False, "length": 3, "type": None, "system_generated": False}})
        assert col(df, "Check Length Validation Result")[0].startswith(FAIL)

    def test_length_ok_pass(self):
        df = self._run({"A": ["AB"]}, {"A": {"mandatory": False, "length": 3, "type": None, "system_generated": False}})
        assert col(df, "Check Length Validation Result") == [PASS]

    def test_system_generated_has_value_fail(self):
        df = self._run({"A": ["val"]}, {"A": {"mandatory": False, "length": None, "type": None, "system_generated": True}})
        assert col(df, "Check System Generated Validation Result")[0].startswith(FAIL)

    def test_system_generated_blank_pass(self):
        df = self._run({"A": [""]}, {"A": {"mandatory": False, "length": None, "type": None, "system_generated": True}})
        assert col(df, "Check System Generated Validation Result") == [PASS]

    def test_multiple_mandatory_errors_joined(self):
        df = self._run(
            {"A": [""], "B": [""]},
            {
                "A": {"mandatory": True, "length": None, "type": None, "system_generated": False},
                "B": {"mandatory": True, "length": None, "type": None, "system_generated": False},
            },
        )
        result = col(df, "Check Mandatory Validation Result")[0]
        assert "A" in result and "B" in result
