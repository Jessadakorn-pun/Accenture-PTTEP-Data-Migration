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

## Validation Logic & Test Cases

Each module runs a sequence of checks. Results are written as `Check *` columns appended to the right of each template sheet.

Cell results use these symbols:
- `✅` — passed
- `❌` — failed
- `⚠️` — warning (cannot verify, manual review required)

> **Note:** `⚠️` is treated as non-pass — the `Check Overall Validation Result` will be `❌` if any column shows `⚠️`.

---

### 1. Mandatory & Length (`mandatory`, `length`)

Reads `Field Requirement` and `S4 Target Data Length` from `DataStandardList.xlsx`, filtered by `DS_TABLE`.

- **DS_TABLE**: accepts a single string `"AFIH"` or a list `["AFIH", "AUFK"]` for templates built from JOINs
- **Mandatory**: field marked `M-Mandatory` in Data Standard
- **Blank detection**: empty string, `NaN`, `None`, `"nan"`, `"none"` all count as blank

**Config:**
```yaml
DS_TABLE: "AFIH"          # single table
# or
DS_TABLE:
  - "AFIH"
  - "AUFK"                # multi-table JOIN

VALIDATIONS:
  - mandatory
  - length
```

**Mandatory test cases:**

| Cell Value | Mandatory in DS | Result |
|---|---|---|
| `""` (blank) | Yes | `❌ FIELD_TGT: Missing mandatory value` |
| `"ABC"` | Yes | `✅` |
| `""` (blank) | No | `✅` (optional field, skip) |
| `"ABC"` | No | `✅` |

**Length test cases:**

| Cell Value | Max Length | Result |
|---|---|---|
| `"ABC"` | 5 | `✅` |
| `"ABCDEF"` | 5 | `❌ FIELD_TGT: length 6 exceeds max 5 (value='ABCDEF')` |
| `""` (blank) | 5 | `✅` (blank skips length check) |

---

### 2. Primary Key (`PRIMARY_KEYS`)

Checks that the combination of key columns is **unique** and **non-blank** across all rows.

**Config:**
```yaml
PRIMARY_KEYS:
  - ["AUFNR_TGT"]                    # single-column PK
  - ["AUFNR_TGT", "VORNR_TGT"]      # composite PK (each list = separate check column)
```

**Test cases:**

| AUFNR_TGT | VORNR_TGT | Result |
|---|---|---|
| `1000` | `0010` | `✅` |
| `1000` | `0020` | `✅` |
| `1000` | `0010` | `❌ Duplicate PK: 1000 \| 0010` |
| `""` | `0010` | `❌ Missing PK value(s)` |
| `""` | `""` | `❌ Missing PK value(s)` |

---

### 3. Fixed Values (`FIXED_VALUE_FIELDS`)

Checks that a column only contains values from a predefined allowed list. Blank cells are skipped.

**Config:**
```yaml
FIXED_VALUE_FIELDS:
  - column: "IWERK_TGT"
    allowed_values:
      - "4410"
      - "4411"
  - column: "ATKLE_TGT"
    allowed_values:
      - "X"
      - ""              # empty string is an allowed value
```

| Cell Value | Result |
|---|---|
| `"4410"` | `✅` |
| `"4411"` | `✅` |
| `""` (blank) | `✅` (skip) |
| `"4412"` | `❌ FIELD_TGT: value '4412' not in allowed list ['4410', '4411']` |
| `"4410 "` (trailing space) | `❌` (trimmed before check, but `"4410 "` → `"4410"` → `✅`) |

---

### 4. Prohibited Newlines (`PROHIBITED_NEWLINE_FIELDS`)

Checks that specified columns do not contain `\n` (newline) or `\r` (carriage return) characters.

**Config:**
```yaml
PROHIBITED_NEWLINE_FIELDS:
  - "KTEXT_TGT"
  - "ATNAM_TGT"
```

| Cell Value | Result |
|---|---|
| `"Normal text"` | `✅` |
| `"Line1\nLine2"` | `❌ FIELD_TGT: Newline character not allowed` |
| `"Line1\rLine2"` | `❌ FIELD_TGT: Newline character not allowed` |
| `""` (blank) | `✅` |

---

### 5. Non-Blank Optional — All (`NON_BLANK_OPTIONAL_FIELDS`)

Each listed column **must** have a value. Checked independently.

**Config:**
```yaml
NON_BLANK_OPTIONAL_FIELDS:
  - "ILOAN_TGT"
  - "ATNAM_TGT"
```

| Cell Value | Result |
|---|---|
| `"ABC"` | `✅` |
| `""` (blank) | `❌ FIELD_TGT: missing value` |
| `"0"` | `✅` (non-empty string passes) |

---

### 6. Non-Blank Optional — Any (`NON_BLANK_OPTIONAL_ANY_FIELDS`)

Groups of columns where **at least one** per group must have a value.

**Config:**
```yaml
NON_BLANK_OPTIONAL_ANY_FIELDS:
  - ["ANLBD_TGT", "ANLVD_TGT", "ANLBZ_TGT"]   # at least one of these must be filled
  - ["IWERK_TGT", "SWERK_TGT"]                  # each list is an independent group
```

| ANLBD_TGT | ANLVD_TGT | ANLBZ_TGT | Result |
|---|---|---|---|
| `"20251001"` | `""` | `""` | `✅` (at least one filled) |
| `""` | `""` | `"10:00:00"` | `✅` |
| `""` | `""` | `""` | `❌ ANLBD_TGT and ANLVD_TGT and ANLBZ_TGT: must be filled at least 1 column` |

---

### 7. Same-Sheet Reference (`SAME_SHEET_REFERENCES`)

Checks that a value in a **child** column exists somewhere in a **parent** column on the same sheet. Blank child values are skipped.

**Config:**
```yaml
SAME_SHEET_REFERENCES:
  - source_column: "AUFNRC_TGT"    # value in this column...
    target_column: "AUFNR_TGT"     # ...must exist somewhere in this column
```

| AUFNRC_TGT (child) | Values in AUFNR_TGT (parent) | Result |
|---|---|---|
| `"1000"` | `["1000", "1001", "1002"]` | `✅` |
| `""` (blank) | any | `✅` (skip) |
| `"9999"` | `["1000", "1001", "1002"]` | `❌ AUFNRC_TGT '9999' not found in AUFNR_TGT` |

---

### 8. Cross-Sheet Reference (`CROSS_SHEET_REFERENCES`)

Checks that a key combination exists in another worksheet. Runs **after all jobs** are loaded. Blank source rows are skipped.

**Config:**
```yaml
CROSS_SHEET_REFERENCES:
  # Single column
  - source_columns:       ["AUFNR_TGT"]
    target_sheet_keyword: "Order Master Data"   # exact sheet name match
    target_columns:       ["AUFNR_TGT"]

  # Composite key — all columns must match together
  - source_columns:       ["ATINN_TGT", "ATNAM"]
    target_sheet_keyword: "TH,MY_CABN_Characteristic"
    target_columns:       ["ATINN_TGT", "ATNAM_TGT"]
```

| Source value | Target sheet has | Result |
|---|---|---|
| `"1000"` | `["1000", "1001"]` | `✅` |
| `""` (blank) | any | `✅` (skip) |
| `"9999"` | `["1000", "1001"]` | `❌ ('9999',) not found in sheet 'Order Master Data'` |

**Composite key:**

| AUFNR_TGT | VORNR_TGT | Target has | Result |
|---|---|---|---|
| `"1000"` | `"0010"` | `(1000, 0010)` | `✅` |
| `"1000"` | `"0099"` | only `(1000, 0010)` | `❌ ('1000', '0099') not found in sheet '...'` |

---

### 9. KDS Mapping Reference (`KDS_REFERENCES`)

Checks that template values exist in an allowed-value table in `KDS_Mapping.xlsx`.

#### 9a. Single column

**Config:**
```yaml
KDS_REFERENCES:
  - kds_sheet:      "DT03"
    kds_field_name: "ARTPR_TOBE"    # column name in the KDS sheet
    source_columns: ["ARTPR_TGT"]   # column name in the template
```

KDS sheet `"DT03"`:

| ARTPR_TOBE |
|---|
| PM01 |
| PM02 |

| ARTPR_TGT | Result |
|---|---|
| `"PM01"` | `✅` |
| `"PM03"` | `❌ ARTPR_TGT: 'PM03' not found in KDS 'DT03'` |
| `""` (blank) | `✅` (skip) |

#### 9b. Composite key

**Config:**
```yaml
KDS_REFERENCES:
  - kds_sheet: "DT_PLANT_TYPE"
    kds_columns:               # column names in the KDS sheet (composite key)
      - "PLANT_TOBE"
      - "TYPE_TOBE"
    source_columns:            # corresponding template columns (same order)
      - "IWERK_TGT"
      - "ARTPR_TGT"
```

KDS sheet:

| PLANT_TOBE | TYPE_TOBE |
|---|---|
| 4410 | PM01 |
| 4410 | PM02 |
| 4411 | PM01 |

| IWERK_TGT | ARTPR_TGT | Result |
|---|---|---|
| `"4410"` | `"PM01"` | `✅` |
| `"4410"` | `"PM03"` | `❌` (tuple not in KDS) |
| `"4411"` | `"PM02"` | `❌` (tuple not in KDS) |
| `""` | `""` | `✅` (all blank → skip) |

#### 9c. SRC→TGT Mapping Check (`check_mapping`) — optional

Verifies that the AS-IS → TO-BE mapping matches the KDS reference table.

**Config:**
```yaml
KDS_REFERENCES:
  - kds_sheet: "DT_PLANT_TYPE"
    kds_columns:
      - "PLANT_TOBE"
      - "TYPE_TOBE"
    source_columns:
      - "IWERK_TGT"
      - "ARTPR_TGT"
    check_mapping:
      kds_src_columns:       ["PLANT_SRC", "TYPE_SRC"]   # AS-IS columns in KDS sheet
      template_src_columns:  ["IWERK_SRC", "ARTPR_SRC"]  # AS-IS columns in template
```

KDS sheet:

| ASIS | TOBE |
|---|---|
| A | B |
| A | C |
| _(blank)_ | D |
| _(blank)_ | E |

| SRC | TGT | Result |
|---|---|---|
| `""` | `""` | `✅` (both blank → skip) |
| `"A"` | `"B"` | `✅` |
| `"A"` | `"C"` | `✅` |
| `"A"` | `"X"` | `❌ Wrong mapping: FIELD_TGT: expected 'B' got 'X'` |
| `"Z"` | `"B"` | `❌ AS-IS (SRC)='Z' not found in KDS` |
| `""` | `"D"` | `✅` (blank ASIS → TOBE=D matches KDS blank-ASIS row) |
| `""` | `"E"` | `✅` (blank ASIS → TOBE=E matches KDS blank-ASIS row) |
| `""` | `"X"` | `❌ Wrong mapping: FIELD_TGT: expected one of ['D', 'E'] got 'X'` |
| `"A"` | `""` | SRC filled, TGT blank → treated as mismatch |
| `""` | `"B"` | `⚠️ SRC blank — please verify mapping in KDS` (only when KDS has **no** blank-ASIS rows) |

---

### 9d. KDS Prohibited Reference (`KDS_PROHIBITED_REFERENCES`)

The **reverse** of `KDS_REFERENCES` — validation **fails** if the value *is found* in the KDS table. Used for blacklists.

**Config:**
```yaml
KDS_PROHIBITED_REFERENCES:
  - kds_sheet: "BLACKLIST"
    source_columns: ["ARTPR_TGT"]
    # optional: kds_field_name or kds_columns to specify which KDS column(s) to match
```

KDS sheet `"BLACKLIST"`:

| ARTPR_TOBE |
|---|
| PM99 |
| PM00 |

| ARTPR_TGT | Result |
|---|---|
| `"PM01"` | `✅` (not in blacklist) |
| `"PM99"` | `❌ ARTPR_TGT: 'PM99' is prohibited (found in KDS 'BLACKLIST')` |
| `""` (blank) | `✅` (skip) |

**Composite key:**

| COL_A | COL_B | Result |
|---|---|---|
| `"X"` | `"Y"` | `❌` (tuple found in blacklist KDS) |
| `"X"` | `"Z"` | `✅` (tuple not in blacklist KDS) |
| `""` | `""` | `✅` (all blank → skip) |

---

### 10. Custom Validators (`CUSTOM_VALIDATIONS`)

Business-logic validators applied to specific columns.

---

#### `check_ad_date`

Validates date string in `YYYYMMDD` format, year range 1900–2100.
`00000000` is treated as blank and passes.

**Config:**
```yaml
CUSTOM_VALIDATIONS:
  - check_ad_date:
      - ADDAT_TGT
      - DATAN_TGT
```

| Value | Result |
|---|---|
| `""` (blank) | `✅` |
| `"00000000"` | `✅` (treated as blank) |
| `"20251001"` | `✅` |
| `"19000101"` | `✅` (boundary) |
| `"21001231"` | `✅` (boundary) |
| `"20251301"` | `❌ FIELD_TGT: Invalid format '20251301': expected YYYYMMDD` (month 13) |
| `"20250230"` | `❌` (Feb 30 doesn't exist) |
| `"18991231"` | `❌ FIELD_TGT: Year in '18991231' must be between 1900–2100` |
| `"21010101"` | `❌ FIELD_TGT: Year in '21010101' must be between 1900–2100` |
| `"01.10.2025"` | `❌ FIELD_TGT: Invalid format '01.10.2025': expected YYYYMMDD` |
| `"2025-10-01"` | `❌ FIELD_TGT: Invalid format '2025-10-01': expected YYYYMMDD` |

---

#### `check_ad_year`

Validates 4-digit year `YYYY`, range 1900–2100.

**Config:**
```yaml
CUSTOM_VALIDATIONS:
  - check_ad_year:
      - BAUJJ_TGT
```

| Value | Result |
|---|---|
| `""` (blank) | `✅` |
| `"2025"` | `✅` |
| `"1900"` | `✅` (boundary) |
| `"2100"` | `✅` (boundary) |
| `"1899"` | `❌ FIELD_TGT: Year '1899' is out of valid range (1900–2100)` |
| `"2101"` | `❌ FIELD_TGT: Year '2101' is out of valid range (1900–2100)` |
| `"25"` | `❌ FIELD_TGT: Invalid year '25': expected YYYY` |
| `"YYYY"` | `❌ FIELD_TGT: Invalid year 'YYYY': expected YYYY` |

---

#### `check_mm`

Validates 2-digit month `MM`, range 01–12.

**Config:**
```yaml
CUSTOM_VALIDATIONS:
  - check_mm:
      - BAUMM_TGT
```

| Value | Result |
|---|---|
| `""` (blank) | `✅` |
| `"01"` | `✅` |
| `"12"` | `✅` (boundary) |
| `"00"` | `❌ FIELD_TGT: Month '00' must be between 01 and 12` |
| `"13"` | `❌ FIELD_TGT: Month '13' must be between 01 and 12` |
| `"1"` | `❌ FIELD_TGT: Invalid format '1': expected MM` |
| `"Jan"` | `❌ FIELD_TGT: Invalid format 'Jan': expected MM` |

---

#### `check_uppercase`

All ASCII English letters (A–Z) in the value must be uppercase. Non-ASCII characters (Thai, numbers, symbols) are ignored.

**Config:**
```yaml
CUSTOM_VALIDATIONS:
  - check_uppercase:
      - TPLNR_TGT
      - EQKTX_TGT
```

| Value | Result |
|---|---|
| `""` (blank) | `✅` |
| `"ABC"` | `✅` |
| `"ABC123"` | `✅` (numbers ignored) |
| `"ก-ข-ABC"` | `✅` (Thai ignored) |
| `"abc"` | `❌ FIELD_TGT: Invalid format 'abc': English letters must be uppercase only (A-Z)` |
| `"ABCdef"` | `❌ FIELD_TGT: Invalid format 'ABCdef': English letters must be uppercase only (A-Z)` |
| `"ก-ข-abc"` | `❌` (English part must still be uppercase) |

---

#### `check_between_time`

Validates that start datetime is not after end datetime.
Date format: `YYYYMMDD`, Time format: `HH:MM:SS`.
`00000000` in date fields is treated as blank.

Date fields (`start_date`, `end_date`) are **required** if either is filled. Time fields (`start_time`, `end_time`) are **optional** — default to `00:00:00` when blank.

**Config:**
```yaml
CUSTOM_VALIDATIONS:
  - check_between_time:
      - start_date: ANLBD_TGT
        start_time: ANLBZ_TGT    # optional — omit or leave blank to default 00:00:00
        end_date:   ANLVD_TGT
        end_time:   ANLVZ_TGT    # optional — omit or leave blank to default 00:00:00
```

| start_date | start_time | end_date | end_time | Result |
|---|---|---|---|---|
| `""` | `""` | `""` | `""` | `✅` (all blank → skip) |
| `"00000000"` | `""` | `"00000000"` | `""` | `✅` (treated as blank → skip) |
| `"20251001"` | `"08:00:00"` | `"20251001"` | `"17:00:00"` | `✅` |
| `"20251001"` | `"08:00:00"` | `"20251001"` | `"08:00:00"` | `✅` (equal = pass) |
| `"20251001"` | `""` | `"20251001"` | `""` | `✅` (time defaults to `00:00:00`) |
| `"20251001"` | `"17:00:00"` | `"20251001"` | `"08:00:00"` | `❌ Start datetime '20251001 17:00:00' is after end datetime '20251001 08:00:00'` |
| `"20251001"` | `""` | `""` | `""` | `❌ Missing field(s): end_date` |
| `"invalid"` | `"08:00:00"` | `"20251001"` | `"17:00:00"` | `❌ Invalid datetime: start='invalid 08:00:00', end='20251001 17:00:00' (expect YYYYMMDD HH:MM:SS)` |

---

#### `check_startup_date`

Plants `2300`, `2304`, `4000`, `1201` must have startup date = `20251001`.
`00000000` is treated as blank (will fail for required plants since blank ≠ `20251001`).

**Config:**
```yaml
CUSTOM_VALIDATIONS:
  - check_startup_date:
      - planning_plant: IWERK_TGT    # column containing the planning plant code
        startup_date:   INBDT_TGT    # column containing the startup date (YYYYMMDD)
```

| planning_plant | startup_date | Result |
|---|---|---|
| `"4410"` | any | `✅` (plant not in required list) |
| `"2300"` | `"20251001"` | `✅` |
| `"2300"` | `"20241001"` | `❌ Invalid Start-up Date '20241001' for Planning Plant '2300': expected date is 20251001` |
| `"2300"` | `""` (blank) | `❌ Invalid Start-up Date '' for Planning Plant '2300': expected date is 20251001` |
| `"2300"` | `"00000000"` | `❌ Invalid Start-up Date '' for Planning Plant '2300': expected date is 20251001` |
| `""` (blank plant) | any | `✅` (plant not in required list) |

---

### 11. Overall Result

After all checks, a `Check Overall Validation Result` column is inserted as the **first** Check column.

| Row has | Overall |
|---|---|
| All `✅` | `✅` |
| Any `❌` | `❌` |
| Any `⚠️` | `❌` (warning treated as non-pass) |

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
    SHEET_KEYWORD: "Maintenance Order Header"  # exact match against sheet names
    DS_TABLE:      "AFIH"                      # SAP table filter in Data Standard
                                               # Use a list for multi-table:
                                               #   DS_TABLE:
                                               #     - "AFIH"
                                               #     - "AUFK"

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

    KDS_PROHIBITED_REFERENCES:
      # Fails if value IS found in the KDS table (blacklist)
      - kds_sheet: "BLACKLIST_CODES"
        source_columns: ["ARTPR_TGT"]
        # kds_field_name: "ARTPR_TOBE"   # optional; defaults to same column header

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
            start_time: ANLBZ_TGT    # optional — defaults to 00:00:00 if blank
            end_date:   ANLVD_TGT
            end_time:   ANLVZ_TGT    # optional — defaults to 00:00:00 if blank

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
| KDS Prohibited | `Check KDS Prohibited: COL in 'KDS_SHEET'` |
| Custom | `Check COL_TGT (check_ad_date) Format` |
