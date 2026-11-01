# Reusable CSV workbench

The workbench lets you combine CSV exports and check them using saved rules. A profile defines the output fields. Each export format maps a source's headings, delimiter, encoding, dates, and numbers to those fields, so later batches can reuse the same setup.

## Open it

Double-click **Start Workbench.cmd** in the project folder. On this computer it opens `http://127.0.0.1:8803/workspace`. Keep the launcher terminal open while working. If the service is already running, use that address directly. Another machine needs Python 3.12; from this project folder run:

```text
python -m src.local_web --port 8803 --workspace --open-browser
```

The original sales-v1 lab remains at `/` on the same server. Its existing AWS pipeline still uses the original five-field contract. The reusable workbench is local; its profiles and multi-file jobs are not sent to or executed by AWS. No additional cloud resources or charges were introduced for this extension.

## First run

1. Try **Sales exports** or **Service tickets**. These are original fictional fixtures with editable profiles. Alternatively, choose your own CSV files. For a new profile, source headings become output fields of type Text initially.
2. Open **Set up & map**. Give the profile a name. Choose Text, Whole number, Decimal or Date for each field. Set required fields, the key, numeric totals and decimal places. Optional rules include numeric bounds and explicitly allowed values.
3. Review each **export format**. Map every required and key field to its source heading. Choose the delimiter, encoding, date order and number separators. Leave optional fields unmapped when genuinely unavailable. An explicitly mapped column that disappears is a file error, even when its field is optional.
4. Choose a duplicate policy and what to do with unmapped source columns. **Preserve** is the default. It retains extras with `extra:` headings. **Flag the whole file** surfaces unfinished mapping. **Explicitly leave them out** omits extras deliberately.
5. Save the profile, return to the file list and confirm the format assigned to every file. Matching known headings and parsing settings can reuse an existing format. Two matching formats require an explicit choice, particularly when date conventions differ.
6. Run **Consolidate & check batch**. Inspect the counts, file issues, corrections, exact totals and source references. Download the accepted, review, skipped, summary and import-history CSVs, the profile and manifest.

For a new export with alternate headings, add another export format and map its headings to the same output fields. This is configuration for that format. Individual files can select an appropriate saved format. A profile can contain up to 50 export formats.

**Example:** A sales profile can have a `sales` Decimal field allowing four places and map the source's line-total column directly. No quantity or reconstructed unit price is required. This preserves discounted fractional amounts from the Kaggle trial exactly.

## Types and arithmetic

- Text trims outer whitespace and keeps case and leading zeros. IDs should normally be Text.
- Whole numbers accept numeric values only when they are mathematically integral. Output uses canonical integer text.
- Decimals accept the configured separators and up to 12 decimal places. Additional nonzero precision goes to review. There is no automatic rounding. Redundant trailing zeros can normalize away without changing the amount. Magnitudes are bounded at 10^24. Exponents, nonfinite numbers and currency symbols are rejected.
- Date fields use the export format's selected date convention and output ISO dates. There is no date-order inference. One date convention applies to date fields within each export format.
- Min/max bounds apply to number fields. Allowed values compare against canonical output text, with case preserved.
- Optional blank values stay blank. Summary files show populated and missing accepted-row counts. A total of zero with no populated rows is not evidence that missing values were known zeroes. Units and currencies are not guessed or converted.

## Duplicate and conflict decisions

Records are ordered by source filename and logical CSV record. These references survive every disposition. Keys may contain multiple fields and are checked across the whole current batch.

- **Key-based checks:** if copies have different normalized business values, or a repeated key includes any invalid row, review every copy. Otherwise accept the first valid copy and skip later identical copies. Empty key fields require review, even if the field's Required box is off.
- **Exact rows:** skip later identical normalized full-row copies without requiring keys. Invalid rows still go to review.
- **Keep all:** accept all valid rows and perform no duplicate removal.

Preserved extra fields participate in duplicate comparison. Different extra information is treated as a meaningful difference. Key and Text comparisons remain case-sensitive. There is no fuzzy matching, latest-file-wins rule or automatic conflict repair.

## Completeness, publication and replay

An unreadable file, missing mapped heading, wrong column count, ambiguous source headings or rejected extra columns becomes a visible file issue. Its parsed-row count is **Unknown**, not zero. The batch is marked **Incomplete**. Accepted outputs in that case cover the successfully parsed files only and must not be presented as a complete batch total.

For successfully parsed inputs:

```text
input rows = accepted + review + skipped
```

The workbench preserves exact raw bytes, writes the outputs, records their hashes and publishes the manifest last. A failed partial publication is not a completed job. Replaying the same source bytes, filenames, assigned formats and profile verifies existing output hashes and reuses one result. Editing rules or inputs creates a different job. Totals never accumulate across runs. This is a batch snapshot, not an incremental warehouse or cross-batch duplicate ledger.

CSV exports make formula-looking text inert by prefixing an apostrophe. Properly typed numeric negatives remain numeric. Raw source bytes and original review-record JSON preserve provenance independently of displayed CSV text.

## Storage, portability and limits

- Profiles: `local-data/workbench/profiles/`. Export/Import JSON moves configurations between machines; imported profiles are validated and saved locally.
- Jobs: `local-data/workbench/jobs/<job-id>/`. Each contains the exact profile snapshot, raw inputs, outputs and completion manifest. This data directory is ignored by Git.
- The recent-batch view can inspect saved results after a restart. A visible warning distinguishes an old result from changed current settings.
- Up to 20 files, 5 MB each, 20 MB combined and 50,000 parsed rows in a batch. Up to 80 configured output fields and 120 source headings. UTF-8 (with or without BOM) and Windows-1252; comma, semicolon, tab and pipe delimiters.
- CSV only. XLSX, database connectors, joins between different record types, arbitrary expressions, per-field date conventions and scheduled/cloud profile execution are outside this version. Save a clear client-specific configuration before using a new business process.
- The service binds to loopback and checks Host, Origin and a per-start token on mutations. It is for this computer. It does not provide a public authenticated upload portal.

## Verification

The automated suite includes cross-file conflicts, exact decimals, decimal separators, date-order choices, composite keys, required/allowed/bound checks, unknown columns, missing values, malformed files, leading-zero IDs, quoted multiline CSV, Windows-1252, portable profiles, restart/replay, interrupted publication and output corruption. The unchanged original pipeline regression tests also pass.

The external Kaggle check processed all 9,994 source rows and retained an independently calculated total of **2,297,200.8603** source units. Every mapped field and preserved extra matched the source. The former 995-row master now validates directly as line amounts, preserving **243,731.3704** source units without reconstructing or rounding unit prices. See `evidence/profile-workbench-kaggle.json`. These are local checks, distinct from the previously recorded sales-v1 cloud deployment checks.
