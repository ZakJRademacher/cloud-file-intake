# First session — one file, one result

Allow about 20–30 minutes, or pause whenever a new term needs more time. You do not need an AWS account for this lesson.

## 1. See what is in a row

Open data/samples/weekly-sales.csv in a text editor, or import it into Excel with record_id explicitly set to Text. The first row of data means two Office items at 250 cents each. Its amount is 500 cents. The row with quantity -1 represents a cancellation, so its amount is -250 cents. A zero is a recorded value, not a missing value.

Before running anything, find:

- The exact repeated record.
- The ID with two different prices.
- A blank ID, a bad quantity and a negative price.
- The invalid calendar date and unsuitable category text.

Prediction: should an early copy of a conflicting ID be accepted just because it appears first? Explain your answer before checking the data contract.

## 2. Run the actual processor

Double-click Start Local Demo.cmd. In the local browser lab, choose **Messy weekly sales**. This executes the Python processor on the included file. It is not a simulated AWS service.

Inspect the controls: **14 = 6 + 7 + 1**. Download accepted.csv and needs_review.csv. Every data row has a source_row reference. Find both copies of the conflicting ID in the review export.

Check the money independently:

- Office: 500 − 250 + 300 = 550 cents.
- Tech: 1,500 + 0 + 0 = 1,500 cents.
- Accepted total: 2,050 cents. Do not label it dollars; the demonstration contract does not specify a currency.

## 3. Run the identical file again

Choose the same sample a second time. The app should say **Safe replay**. You still have one result for those bytes, with the same totals.

This property is called idempotency: repeating the same operation does not add another business effect. A queue may deliver an event twice, so the processor must handle repeats deliberately.

The job ID is a fingerprint of the file bytes and rule version. A fingerprint identifies content; it is not encryption and does not hide the file.

## 4. Try a different kind of failure

Choose **Bad schema**. This file is missing a required column. It gets a quarantined result and an explanation; the processor does not invent a price or publish a misleading summary.

A malformed source is different from a storage outage. Fix the source for the first; retry the operation for the second. The cloud adapter and tests keep those paths separate.

## 5. Explain the boundary

Open a manifest download. It describes a whole completed result. The processor writes it after all CSV outputs have been written. If processing stops early, some files may exist, but there is no completed manifest to tell a reader the job is done.

Without looking up an answer, explain:

1. Why must IDs keep leading zeros?
2. Why do both conflicting copies need review?
3. Why is a known zero valid?
4. What happens when the same notification arrives twice?
5. Why is a manifest useful after a failed write?

We can work through these together. Being able to trace one file confidently matters more than memorizing service names.
