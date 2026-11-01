# Sales CSV contract — sales-v1

The sales-v1 processor handles one complete CSV at a time. It does not combine jobs into a sales ledger. The samples are fictional; corrections to real records would need source evidence, with the original bytes preserved.

## File contract

- UTF-8 with optional BOM; comma delimiter and ordinary CSV quoting.
- At most 1,000,000 bytes and 5,000 nonempty data rows. Empty physical lines are ignored; source_row counts parsed data records, not physical line numbers in quoted multiline CSV.
- Exactly five columns, in any order. Header whitespace/case is normalized. Duplicate, missing or unknown headers reject the whole file.
- Recognized aliases: id/line_id → record_id; date → sale_date; product_category → category; qty → quantity; price_cents → unit_price_cents.
- An empty file, malformed quoting, invalid UTF-8, a NUL byte or a data row with the wrong number of columns rejects the whole file. Header-only files are valid zero-row deliveries.

| Field | Rule |
| --- | --- |
| record_id | Text, 1–64 characters; first character a Latin letter or digit, followed by letters, digits, underscores or hyphens. Leading zeros remain intact. |
| sale_date | Valid calendar date, exactly YYYY-MM-DD. No inferred locale or timezone. |
| category | 1–80 characters; starts with a Latin letter. Remaining letters, digits, spaces and `&/().-` allowed. This intentionally narrow demonstration contract is not a universal category parser. |
| quantity | Signed integer text, magnitude at most 1,000,000; zero and negative cancellation quantities allowed. No decimal or exponent notation. |
| unit_price_cents | Integer text from 0 to 100,000,000. A known zero is valid. Source currency is unspecified. |

Outer field whitespace is removed. Duplicate comparison uses those trimmed field strings, not a guessed numeric equivalence: `1` and `01` as quantities are different signatures for conflict purposes. Change the contract explicitly if a client needs another rule.

## Disposition order

Before accepting any row, compare all rows sharing record_id. If their normalized field strings differ, **every row of that ID goes to review**. This avoids accepting an early value before seeing its later conflict.

For each row: reject an invalid ID, then a conflicting ID, invalid date, category, quantity or price. The first applicable reason is recorded. Otherwise accept the first valid instance and skip later exact repeated copies. Invalid repeated rows remain separate review rows.

`accepted.csv` contains source_row, the five canonical fields and signed amount_cents. Quantity and price become actual integers; amount_cents = quantity × unit_price_cents.

`needs_review.csv` and `skipped.csv` retain the normalized input fields, source_row and a reason. Rejected text starting with a spreadsheet formula prefix is prefixed with an apostrophe in CSV exports. This display safeguard does not change the raw upload.

`summary.csv` groups accepted amounts and record counts by category. `manifest.json` records the rule version, source SHA-256, byte size, row counts and each output's SHA-256/size. The controls are:

    input_rows = accepted_rows + review_rows + skipped_rows
    sum(accepted.amount_cents) = sum(summary.net_cents)

## File identity and receipts

The job ID is SHA-256 of the rule version, a separator and the exact input bytes. A byte-for-byte repeat reuses the completed verified outputs. A changed file, newline encoding or rule version produces a new job. There is no global sum across jobs and no cross-file business-ID deduplication.

Each upload receipt separately records which source points to the job. Cloud receipts retain bucket, key and exact S3 version ID. Local receipts retain the filename and preserved raw key. Raw data remains in its original store; a malformed file has a quarantined status and a quarantine.json diagnosis, rather than accepted CSVs.

CLI/browser uploads over 1 MB are refused before local preservation. An oversized object uploaded directly to S3 causes an operational retry and eventually a dead-letter message; the bounded read is never presented as a hash of the complete oversized source.
