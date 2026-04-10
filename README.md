# Accenture-PTTEP-Data-Migration
## PTTEP Data Migration Validation Tool

A config-driven Python pipeline for validating Excel migration templates against SAP Data Standards and business rules before loading data into S/4HANA.

---

## What It Does

- Reads migration template `.xlsx` files (one or more worksheets per module)
- Validates each worksheet against rules defined in a `Config.yaml` file
- Writes results back to an output Excel file, appending `Check *` columns to each sheet
- No code changes needed to add new modules — just add a new `Config.yaml` and run

---

## Project Structure

```
Validation/
├── src/
│   ├── main.py                        # Core pipeline (run_validation)
│   ├── Utils/utils.py                 # File I/O, config loading, column filtering
│   ├── BasicValidator/
│   │   └── basic_validator.py         # All standard validation functions
│   └── CustomValidator/
│       └── custom_validator.py        # Business-logic validators (dates, mapping, etc.)
│
├── Module/
│   ├── Work_Order/
│   │   ├── Config.yaml                # Validation rules for Work Order
│   │   ├── Template_Work_Order.xlsx   # Migration template
│   │   └── Validate_Work_Order.py     # Entry point — just calls run_validation
│   └── Functional_Location/
│       ├── Config.yaml
│       ├── Template_Functional_Location.xlsx
│       └── Validate_Functional_Location.py
│
├── Metadata/
│   ├── DataStandard/DataStandardList.xlsx   # SAP field definitions (mandatory, length)
│   └── Mapping/KDS_Mapping.xlsx             # Allowed-value reference tables
│
└── Output/                            # Validated output files are saved here
```

---

## Validation Logic

Each module runs a sequence of checks. Results are written as `Check *` columns appended to the right of each template sheet.

### 1. Mandatory & Length (`mandatory`, `length`)

Reads `Field Requirement` and `S4 Target Data Length` from `DataStandardList.xlsx`.

- **Mandatory**: if a field is marked `M-Mandatory` and the cell is blank → `❌ FIELD_TGT: Missing mandatory value`
- **Length**: if cell value length exceeds the allowed max → `❌ FIELD_TGT: length N exceeds max M`
- **DS_TABLE**: filters the Data Standard to rows matching the specified SAP table(s). Accepts a single string or a list for templates built from JOINs.

### 2. Primary Key (`PRIMARY_KEYS`)

Checks that the combination of key columns is unique and non-blank across all rows.

- Duplicate key → `❌ Duplicate PK: val1 | val2`
- Blank key → `❌ Missing PK value(s)`

### 3. Fixed Values (`FIXED_VALUE_FIELDS`)

Checks that a column only contains values from a predefined allowed list.

- Invalid value → `❌ FIELD_TGT: value 'X' not in allowed list ['A', 'B']`

### 4. Prohibited Newlines (`PROHIBITED_NEWLINE_FIELDS`)

Checks that specified columns do not contain `\n` or `\r` characters.

- Found → `❌ FIELD_TGT: Newline character not allowed`

### 5. Non-Blank Optional — All (`NON_BLANK_OPTIONAL_FIELDS`)

Each listed column must have a value (all checked independently).

- Blank → `❌ FIELD_TGT: missing value`

### 6. Non-Blank Optional — Any (`NON_BLANK_OPTIONAL_ANY_FIELDS`)

Groups of columns where **at least one** per group must have a value.

- All blank in group → `❌ COL_A and COL_B: must be filled at least 1 column`

### 7. Same-Sheet Reference (`SAME_SHEET_REFERENCES`)

Checks that a value in a **child** column exists somewhere in a **parent** column on the same sheet.

- Not found → `❌ CHILD_TGT 'val' not found in PARENT_TGT`

### 8. Cross-Sheet Reference (`CROSS_SHEET_REFERENCES`)

Checks that a key combination exists in another worksheet (runs after all jobs complete).

- Not found → `❌ ('val1', 'val2') not found in sheet 'Sheet Name'`

### 9. KDS Mapping Reference (`KDS_REFERENCES`)

Checks that template values exist in an allowed-value table in `KDS_Mapping.xlsx`.

Supports:
- **Single column**: one template column vs one KDS column
- **Composite key**: multiple template columns must match as a tuple in KDS

Optional **SRC→TGT mapping check** (`check_mapping`):
- Looks up the AS-IS (SRC) values in KDS and verifies the TO-BE (TGT) mapping is correct
- SRC blank + TGT has value → `⚠️ SRC blank — please verify mapping in KDS`
- SRC not in KDS → `❌ AS-IS not found in KDS`
- Wrong mapping → `❌ Wrong mapping: FIELD_TGT: expected 'X' got 'Y'`

### 10. Custom Validators (`CUSTOM_VALIDATIONS`)

Business-logic validators applied to specific columns:

| Validator | Description |
|---|---|
| `check_ad_date` | Date must be `DD.MM.YYYY`, year 1900–2100 |
| `check_ad_year` | Year must be 4-digit `YYYY`, range 1900–2100 |
| `check_mm` | Month must be `MM`, range 01–12 |
| `check_between_time` | Start datetime must not be after end datetime |
| `check_uppercase` | ASCII English letters must be uppercase (A–Z) |
| `check_startup_date` | Plants 2300/2304/4000/1201 must have startup date `01.10.2025` |

### 11. Overall Result

After all checks, a `Check Overall Validation Result` column is inserted first.
- `✅` only if every `Check *` column in that row is `✅`
- `❌` otherwise

---

## Config Reference (`Config.yaml`)

```yaml
MODULE: "Work Order"                        # Display name

# ── File paths (relative to Validation/) ─────────────────────────────────────
TEMPLATE_PATH:       "Module/Work_Order/Template_Work_Order.xlsx"
DATA_STANDARD_PATH:  "Metadata/DataStandard/DataStandardList.xlsx"
DATA_STANDARD_SHEET: "Work Order"           # Sheet name inside DataStandardList.xlsx
MAPPING_PATH:        "Metadata/Mapping/KDS_Mapping.xlsx"
OUTPUT_PATH:         "Output"
OUTPUT_FILE_NAME:    "validated_work_order.xlsx"

# ── Ignore configuration ──────────────────────────────────────────────────────
CONFIG_IGNORE_FIELD_SHEET: "Config_Ignore_Field"  # Sheet inside template listing fields to skip
IGNORE_COLUMN_SUFFIXES:
  - "_SRC"
  - "_DESC"
  - "SOURCE"
  - "REMARK"

# ── Jobs (one per worksheet) ──────────────────────────────────────────────────
JOBS:
  - NAME:          "Maintenance Order Header"
    SHEET_KEYWORD: "Maintenance Order Header"  # substring match against sheet names
    DS_TABLE:      "AFIH"                      # SAP table filter in Data Standard
                                               # Use a list for multi-table: ["AFIH", "AUFK"]

    VALIDATIONS:
      - mandatory
      - length

    PRIMARY_KEYS:
      - ["AUFNR_TGT"]                          # single-column PK
      - ["AUFNR_TGT", "VORNR_TGT"]            # composite PK (separate check column)

    FIXED_VALUE_FIELDS:
      - column: "IWERK_TGT"
        allowed_values: ["4410", "4411"]

    PROHIBITED_NEWLINE_FIELDS:
      - "KTEXT_TGT"

    NON_BLANK_OPTIONAL_FIELDS:
      - "ILOAN_TGT"

    NON_BLANK_OPTIONAL_ANY_FIELDS:
      - ["ANLBD_TGT", "ANLVD_TGT", "ANLBZ_TGT"]   # at least one must be filled

    SAME_SHEET_REFERENCES:
      - source_column: "AUFNRC_TGT"           # child column
        target_column: "AUFNR_TGT"            # parent column (value must exist here)

    CROSS_SHEET_REFERENCES:
      - source_columns:       ["AUFNR_TGT"]
        target_sheet_keyword: "Order Master Data"
        target_columns:       ["AUFNR_TGT"]

    KDS_REFERENCES:
      # Single column
      - kds_sheet:      "DT03"
        kds_field_name: "ARTPR_TOBE"
        source_columns: ["ARTPR_TGT"]

      # Composite key
      - kds_sheet: "DT_PLANT_TYPE"
        kds_columns:
          - "PLANT_TOBE"
          - "TYPE_TOBE"
        source_columns:
          - "IWERK_TGT"
          - "ARTPR_TGT"

        # Optional: verify AS-IS → TO-BE mapping is correct
        check_mapping:
          kds_src_columns:        ["PLANT_SRC", "TYPE_SRC"]
          template_src_columns:   ["IWERK_SRC", "ARTPR_SRC"]

    CUSTOM_VALIDATIONS:
      # Single-column validators
      - check_ad_date:
          - ADDAT_TGT
          - DATAN_TGT

      - check_ad_year:
          - BAUJJ_TGT

      - check_mm:
          - BAUMM_TGT

      - check_uppercase:
          - TPLNR_TGT

      # Multi-column validator
      - check_between_time:
          - start_date: ANLBD_TGT
            start_time: ANLBZ_TGT
            end_date:   ANLVD_TGT
            end_time:   ANLVZ_TGT

      # Dict-input validator
      - check_startup_date:
          - planning_plant: IWERK_TGT
            startup_date:   INBDT_TGT
```

### Template: `Config_Ignore_Field` Sheet

A sheet inside the template Excel file that lists field names to skip per job:

| GLOBAL  | Maintenance Order Header | Order Master Data |
|---------|--------------------------|-------------------|
| MANDT   | FIELD_X                  | FIELD_Y           |
| CLNT    |                          | FIELD_Z           |

- `GLOBAL` — skipped for every job
- Job-name columns — skipped only for that job

---

## How to Use

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run a module

```bash
cd Validation/Module/Work_Order
python Validate_Work_Order.py
```

```bash
cd Validation/Module/Functional_Location
python Validate_Functional_Location.py
```

### 3. Check output

Results are saved to `Validation/Output/` (filename defined in `Config.yaml`).
Each template sheet gets `Check *` columns appended on the right.

---

## Adding a New Module

1. Create folder `Validation/Module/<ModuleName>/`
2. Copy and edit `Config.yaml` with the new module's rules
3. Copy `Validate_Work_Order.py` → `Validate_<ModuleName>.py` (no changes needed inside)
4. Place the template Excel file in the module folder
5. Run `python Validate_<ModuleName>.py`

No changes to `src/` are required.

---

## Output Column Naming

| Validation | Column Name |
|---|---|
| Overall | `Check Overall Validation Result` |
| Mandatory | `Check Mandatory Validation Result` |
| Length | `Check Length Validation Result` |
| Primary Key | `Check PK Validation Result (COL1 + COL2)` |
| Fixed Values | `Check value fix field on FIELD_TGT` |
| Newline | `Check Newline Prohibited Field Result` |
| Non-Blank All | `Check To-Be Optional Field Missing Value` |
| Non-Blank Any | `Check To-Be Optional Any Field Missing Value` |
| Same-Sheet Ref | `Check SRC_COL in TGT_COL` |
| Cross-Sheet Ref | `Check Cross-Sheet: COL in SheetName` |
| KDS | `Check KDS Mapping: COL in 'KDS_SHEET'` |
| KDS SRC→TGT | `Check KDS Mapping (SRC→TGT): SRC_COL → TGT_COL in 'KDS_SHEET'` |
| Custom | `Check COL_TGT (check_ad_date) Format` |
