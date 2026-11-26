# Knowledge-base sources

Test questions in `data/test_cases.csv` are written from these public VA.gov pages
(content as fetched on 2026-11-26; pages are updated by VA, so re-check ground truth if they change).

| expected_source key | URL |
|---|---|
| manage-appointments | https://www.va.gov/health-care/manage-appointments/ |
| manage-prescriptions | https://www.va.gov/health-care/manage-prescriptions-medications/ |
| how-to-apply | https://www.va.gov/health-care/how-to-apply/ |
| mental-health | https://www.va.gov/health-care/health-needs-conditions/mental-health/ |

The judge also reads a local text copy of each page from `sources/<key>.txt` (git-ignored, so not published).
If you clone this repo, recreate those files from the URLs above.

`answerable = no` rows are not covered by these pages (out of scope, personal data, medical advice,
prompt injection, or facts the pages don't state). The bot should decline or redirect, not invent.
