"""
main.py — Core validation pipeline.

Contains the full pipeline logic (_run_job, _run_cross_sheet_validations, run_validation).
Module-specific files (e.g. Validate_Work_Order.py) just call run_validation(config_path).
"""

import os
import sys
import traceback

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Project root = parent of src/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "Utils"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "BasicValidator"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "CustomValidator"))

from utils import (
    load_config,
    resolve_path,
    read_template_sheet,
    get_sheet_names,
    get_ignore_fields_from_template,
    get_effective_ignore_fields,
    load_data_standard,
    load_kds_mapping,
    get_data_columns,
    build_field_metadata,
    save_results_to_excel,
)

from basic_validator import (
    validate_mandatory_and_length,
    validate_primary_keys,
    validate_fixed_values,
    validate_prohibited_newlines,
    validate_non_blank_optional,
    validate_non_blank_optional_any,
    validate_same_sheet_reference,
    validate_start_with,
    validate_kds_reference,
    validate_kds_mapping,
    validate_kds_prohibited,
    validate_kds_completeness,
    validate_cross_sheet_reference,
    add_overall_result,
)

from custom_validator import apply_custom_validations


# ─────────────────────────────────────────────────────────────────────────────
# Per-job pipeline
# ─────────────────────────────────────────────────────────────────────────────

def _run_job(
    job_config: dict,
    all_sheet_dfs: dict,
    all_label_maps: dict,
    ds_df,
    kds_mappings: dict,
    ignore_fields: list,
    ignore_suffixes: list,
) -> tuple:
    """
    Execute all validations for one job (one worksheet).

    Returns:
        (matched_sheet_name: str, validated_df: DataFrame)

    Raises:
        ValueError — if no sheet matching SHEET_KEYWORD is found.
    """
    job_name      = job_config.get("NAME", "")
    sheet_keyword = job_config.get("SHEET_KEYWORD", job_name)

    matched = next(
        (s for s in all_sheet_dfs if s.lower() == sheet_keyword.lower()),
        None,
    )
    if matched is None:
        print(f"  ❌  Not found worksheet name: '{sheet_keyword}'")
        print(f"      Available sheets: {list(all_sheet_dfs.keys())}")
        raise ValueError(f"Job '{job_name}': worksheet '{sheet_keyword}' not found.")

    df        = all_sheet_dfs[matched].copy()
    label_map = all_label_maps[matched]

    print(f"\n  Sheet : '{matched}'  |  Rows: {len(df)}  |  Cols: {len(df.columns)}")

    data_cols = get_data_columns(df, ignore_fields, ignore_suffixes)
    skipped   = len(df.columns) - len(data_cols) - 1
    print(f"  Validating {len(data_cols)} columns  ({skipped} ignored)")

    ds_table       = job_config.get("DS_TABLE")
    field_metadata = build_field_metadata(ds_df, data_cols, ds_table=ds_table)

    # ── 1. Mandatory + Length ─────────────────────────────────────────────────
    validations = job_config.get("VALIDATIONS", ["mandatory", "length"])
    if "mandatory" in validations or "length" in validations:
        df = validate_mandatory_and_length(df, data_cols, field_metadata, label_map=label_map)
        print("  ✅  Mandatory & Length")

    # ── 2. Primary keys ───────────────────────────────────────────────────────
    pk_sets = job_config.get("PRIMARY_KEYS", [])
    if pk_sets:
        df = validate_primary_keys(df, pk_sets, label_map)
        print("  ✅  Primary Keys")

    # ── 3. Fixed values ───────────────────────────────────────────────────────
    fixed_fields = job_config.get("FIXED_VALUE_FIELDS", [])
    if fixed_fields:
        df = validate_fixed_values(df, fixed_fields, label_map)
        print("  ✅  Fixed Values")

    # ── 4. Prohibited newlines ────────────────────────────────────────────────
    newline_fields = job_config.get("PROHIBITED_NEWLINE_FIELDS", [])
    if newline_fields:
        df = validate_prohibited_newlines(df, newline_fields, label_map)
        print("  ✅  Prohibited Newlines")

    # ── 5. Non-blank optionals (all must be filled) ───────────────────────────
    non_blank_fields = job_config.get("NON_BLANK_OPTIONAL_FIELDS", [])
    if non_blank_fields:
        df = validate_non_blank_optional(df, non_blank_fields, label_map)
        print("  ✅  Non-Blank Optional")

    # ── 6. Non-blank optionals (at least one per group) ───────────────────────
    non_blank_any_groups = job_config.get("NON_BLANK_OPTIONAL_ANY_FIELDS", [])
    if non_blank_any_groups:
        df = validate_non_blank_optional_any(df, non_blank_any_groups, label_map)
        print("  ✅  Non-Blank Optional Any")

    # ── 7. Same-sheet references ──────────────────────────────────────────────
    same_refs = job_config.get("SAME_SHEET_REFERENCES", [])
    if same_refs:
        df = validate_same_sheet_reference(df, same_refs, label_map)
        print("  ✅  Same-Sheet References")

    # ── 7b. Start-with validation ─────────────────────────────────────────────
    start_with_fields = job_config.get("START_WITH_FIELDS", [])
    if start_with_fields:
        df = validate_start_with(df, start_with_fields, label_map)
        print("  ✅  Start-With")

    # ── 8. Custom validators ──────────────────────────────────────────────────
    custom_configs = job_config.get("CUSTOM_VALIDATIONS", [])
    if custom_configs:
        df = apply_custom_validations(df, custom_configs, label_map)
        print("  ✅  Custom Validations")

    # ── 9. KDS mapping references ─────────────────────────────────────────────
    kds_refs = job_config.get("KDS_REFERENCES", [])
    for kds_ref in kds_refs:
        kds_sheet      = kds_ref.get("kds_sheet")
        # kds_field_name (str)  → single-column match
        # kds_columns    (list) → composite/tuple match
        kds_field_name = kds_ref.get("kds_field_name") or kds_ref.get("kds_columns")
        source_cols    = kds_ref.get("source_columns", [])
        kds_condition  = kds_ref.get("condition")

        if not kds_sheet or not source_cols or not kds_field_name:
            print("  ⚠️   KDS reference missing required keys (kds_sheet, kds_field_name/kds_columns, source_columns) — skipped.")
            continue

        if kds_sheet not in kds_mappings:
            print(f"  ⚠️   KDS sheet '{kds_sheet}' not found in mapping file — skipped.")
            continue

        try:
            col_name, results = validate_kds_reference(
                df, kds_mappings[kds_sheet], source_cols, label_map, kds_sheet,
                kds_field_name=kds_field_name,
                condition=kds_condition,
            )
            df[col_name] = results
            print(f"  ✅  KDS Reference: '{kds_sheet}' / '{kds_field_name}'")
        except (ValueError, KeyError) as exc:
            print(f"  ⚠️   KDS '{kds_sheet}': {exc} — skipped.")

        # ── Optional: SRC→TGT mapping check ──────────────────────────────────
        mapping_cfg = kds_ref.get("check_mapping")
        if mapping_cfg:
            kds_src_cols  = mapping_cfg.get("kds_src_columns", [])
            tmpl_src_cols = mapping_cfg.get("template_src_columns", [])
            kds_tgt_cols  = kds_field_name if isinstance(kds_field_name, list) else [kds_field_name]

            if not kds_src_cols or not tmpl_src_cols:
                print(f"  ⚠️   check_mapping '{kds_sheet}': missing kds_src_columns or template_src_columns — skipped.")
            else:
                try:
                    map_col, map_results = validate_kds_mapping(
                        df, kds_mappings[kds_sheet],
                        kds_src_cols, tmpl_src_cols,
                        kds_tgt_cols, source_cols,
                        label_map, kds_sheet,
                        condition=kds_condition,
                    )
                    df[map_col] = map_results
                    print(f"  ✅  KDS Mapping (SRC→TGT): '{kds_sheet}'")
                except (ValueError, KeyError) as exc:
                    print(f"  ⚠️   KDS Mapping '{kds_sheet}': {exc} — skipped.")

    # ── KDS Completeness References (all KDS values must exist in template) ──
    completeness_refs = job_config.get("KDS_COMPLETENESS_REFERENCES", [])
    for comp_ref in completeness_refs:
        kds_sheet      = comp_ref.get("kds_sheet")
        kds_field_name = comp_ref.get("kds_field_name")
        source_col     = comp_ref.get("source_column")

        condition      = comp_ref.get("condition")

        if not kds_sheet or not kds_field_name or not source_col:
            print("  ⚠️   KDS completeness missing required keys (kds_sheet, kds_field_name, source_column) — skipped.")
            continue

        if kds_sheet not in kds_mappings:
            print(f"  ⚠️   KDS sheet '{kds_sheet}' not found in mapping file — skipped.")
            continue

        try:
            col_name, results = validate_kds_completeness(
                df, kds_mappings[kds_sheet], source_col, label_map, kds_sheet, kds_field_name,
                condition=condition,
            )
            df[col_name] = results
            print(f"  ✅  KDS Completeness: '{kds_sheet}' / '{kds_field_name}'")
        except (ValueError, KeyError) as exc:
            print(f"  ⚠️   KDS Completeness '{kds_sheet}': {exc} — skipped.")

    # ── KDS Prohibited References (blacklist — value must NOT exist in KDS) ──
    prohibited_refs = job_config.get("KDS_PROHIBITED_REFERENCES", [])
    for proh_ref in prohibited_refs:
        kds_sheet      = proh_ref.get("kds_sheet")
        kds_field_name = proh_ref.get("kds_field_name") or proh_ref.get("kds_columns")
        source_cols    = proh_ref.get("source_columns", [])

        if not kds_sheet or not source_cols or not kds_field_name:
            print("  ⚠️   KDS prohibited reference missing required keys (kds_sheet, kds_field_name/kds_columns, source_columns) — skipped.")
            continue

        if kds_sheet not in kds_mappings:
            print(f"  ⚠️   KDS sheet '{kds_sheet}' not found in mapping file — skipped.")
            continue

        try:
            col_name, results = validate_kds_prohibited(
                df, kds_mappings[kds_sheet], source_cols, label_map, kds_sheet,
                kds_field_name=kds_field_name,
            )
            df[col_name] = results
            print(f"  ✅  KDS Prohibited: '{kds_sheet}' / '{kds_field_name}'")
        except (ValueError, KeyError) as exc:
            print(f"  ⚠️   KDS Prohibited '{kds_sheet}': {exc} — skipped.")

    return matched, df


# ─────────────────────────────────────────────────────────────────────────────
# Cross-sheet validation (runs after all jobs)
# ─────────────────────────────────────────────────────────────────────────────

def _run_cross_sheet_validations(
    job_configs: list,
    df_results: dict,
    all_label_maps: dict,
) -> dict:
    """Apply cross-sheet reference rules declared in CROSS_SHEET_REFERENCES."""
    for job_config in job_configs:
        job_name      = job_config.get("NAME", "")
        sheet_keyword = job_config.get("SHEET_KEYWORD", job_name)
        cross_refs    = job_config.get("CROSS_SHEET_REFERENCES", [])

        if not cross_refs:
            continue

        source_sheet = next(
            (s for s in df_results if s.lower() == sheet_keyword.lower()),
            None,
        )
        if source_sheet is None:
            print(f"  ⚠️   Cross-sheet: not found worksheet name: '{sheet_keyword}' — skipped.")
            continue

        source_df = df_results[source_sheet]
        label_map = all_label_maps.get(source_sheet, {})

        for ref in cross_refs:
            tgt_keyword = ref.get("target_sheet_keyword", "")
            src_cols    = ref.get("source_columns", [])
            tgt_cols    = ref.get("target_columns", [])

            target_sheet = next(
                (s for s in df_results if s.lower() == tgt_keyword.lower()),
                None,
            )
            if target_sheet is None:
                print(f"  ⚠️   Cross-sheet: target '{tgt_keyword}' not found — skipped.")
                continue

            try:
                col_name, results = validate_cross_sheet_reference(
                    source_df,
                    df_results[target_sheet],
                    src_cols,
                    tgt_cols,
                    label_map,
                    target_sheet,
                )
                df_results[source_sheet][col_name] = results
                print(f"  ✅  Cross-Sheet: '{source_sheet}' → '{target_sheet}'")
            except KeyError as exc:
                print(f"  ⚠️   Cross-sheet error: {exc} — skipped.")

    return df_results


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline — called by each module's Validate_*.py
# ─────────────────────────────────────────────────────────────────────────────

def run_validation(config_path: str) -> None:
    """
    Execute the full validation pipeline for any module.

    Args:
        config_path: Absolute path to the module's Config.yaml
    """
    config_dir = os.path.dirname(os.path.abspath(config_path))
    # Derive project root from config location (Module/<ModuleName>/Config.yaml → 2 levels up)
    project_root = os.path.abspath(os.path.join(config_dir, "..", ".."))

    sep = "=" * 60
    print(f"\n{sep}")

    config      = load_config(config_path)
    module_name = config.get("MODULE", "Unknown Module")
    print(f" {module_name} Validation")
    print(sep)
    print(f"\n[Config]  Module           : {module_name}")

    template_path   = resolve_path(project_root, config["TEMPLATE_PATH"])
    ds_path         = resolve_path(project_root, config["DATA_STANDARD_PATH"])
    ds_sheet        = config["DATA_STANDARD_SHEET"]
    mapping_path    = resolve_path(project_root, config["MAPPING_PATH"])
    output_dir      = resolve_path(project_root, config["OUTPUT_PATH"])
    output_filename = config.get("OUTPUT_FILE_NAME", f"validated_{module_name.lower().replace(' ', '_')}.xlsx")
    output_path     = os.path.join(output_dir, output_filename)

    ignore_field_sheet = config.get("CONFIG_IGNORE_FIELD_SHEET", "Config_Ignore_Field")
    ignore_suffixes    = config.get("IGNORE_COLUMN_SUFFIXES", ["_SRC", "_DESC", "SOURCE", "REMARK"])
    jobs               = config.get("JOBS", [])

    print(f"[Config]  Template            : {template_path}")
    print(f"[Config]  Data Standard       : {ds_path}  /  sheet: '{ds_sheet}'")
    print(f"[Config]  KDS Mapping         : {mapping_path}")
    print(f"[Config]  Output              : {output_path}")
    print(f"[Config]  Ignore Field Sheet  : {ignore_field_sheet}")
    print(f"[Config]  Ignore Suffixes     : {ignore_suffixes}")
    print(f"[Config]  Jobs                : {[j.get('NAME') for j in jobs]}")

    # ── 1. Ignore fields ──────────────────────────────────────────────────────
    ignore_fields_map = get_ignore_fields_from_template(template_path, ignore_field_sheet)
    print(f"\n[Setup]   Ignore fields map : {ignore_fields_map}")
    print(f"[Setup]   Ignore suffixes   : {ignore_suffixes}")

    # ── 2. Load template sheets ───────────────────────────────────────────────
    sheet_names    = get_sheet_names(template_path, exclude=[ignore_field_sheet])
    all_sheet_dfs  = {}
    all_label_maps = {}

    print(f"\n[Load]    Sheets found: {sheet_names}")
    for sheet_name in sheet_names:
        try:
            df, label_map = read_template_sheet(template_path, sheet_name)
            all_sheet_dfs[sheet_name]  = df
            all_label_maps[sheet_name] = label_map
            print(f"[Load]    '{sheet_name}'  →  {len(df)} rows, {len(df.columns)} cols")
        except Exception as exc:
            print(f"[Load]    ⚠️  Error reading '{sheet_name}': {exc}")

    if not all_sheet_dfs:
        print("\n❌  No sheets loaded from template — aborting.")
        return

    # ── 3. Data Standard ──────────────────────────────────────────────────────
    ds_df = load_data_standard(ds_path, ds_sheet)
    print(f"\n[Load]    Data Standard    : {len(ds_df)} rows")

    # ── 4. KDS Mapping ────────────────────────────────────────────────────────
    kds_mappings = load_kds_mapping(mapping_path)
    print(f"[Load]    KDS Mapping      : {list(kds_mappings.keys())}")

    # ── 5. Run jobs ───────────────────────────────────────────────────────────
    df_results = {}
    for job_config in jobs:
        job_name = job_config.get("NAME", "?")
        print(f"\n{'─'*60}")
        print(f"[Job]  {job_name}")

        effective_ignore = get_effective_ignore_fields(ignore_fields_map, job_name)
        print(f"  Ignore fields : {effective_ignore}")

        try:
            sheet_name, validated_df = _run_job(
                job_config      = job_config,
                all_sheet_dfs   = all_sheet_dfs,
                all_label_maps  = all_label_maps,
                ds_df           = ds_df,
                kds_mappings    = kds_mappings,
                ignore_fields   = effective_ignore,
                ignore_suffixes = ignore_suffixes,
            )
            df_results[sheet_name] = validated_df
        except Exception as exc:
            print(f"  ❌  Job '{job_name}' failed: {exc}")
            traceback.print_exc()

    if not df_results:
        print("\n❌  No jobs completed successfully — aborting.")
        return

    # ── 6. Cross-sheet validations ────────────────────────────────────────────
    if any(j.get("CROSS_SHEET_REFERENCES") for j in jobs):
        print(f"\n{'─'*60}")
        print("[Cross-Sheet]  Running cross-sheet validations …")
        df_results = _run_cross_sheet_validations(jobs, df_results, all_label_maps)

    # ── 7. Overall result ─────────────────────────────────────────────────────
    for sheet_name in list(df_results.keys()):
        df_results[sheet_name] = add_overall_result(df_results[sheet_name])

    # ── 8. Save output ────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"[Output]  Saving to: {output_path}")
    try:
        saved = save_results_to_excel(template_path, df_results, output_path)
        print(f"\n✅  Validation complete!  Results saved to:\n    {saved}")
    except Exception as exc:
        print(f"\n❌  Failed to save results: {exc}")
        traceback.print_exc()
