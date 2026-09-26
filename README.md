# Retail Growth & Retention Decision Studio

**Business question:** Which customer and product opportunities should a UK online retailer prioritise?

## Live demo and scenario calculator

**[Open the interactive sales scenario calculator](https://banoth281.github.io/retail-growth-retention-decision-studio/#scenario)**. It is on the same page as the historical analysis, below the **Decision 3 · Measure the next purchase** table. Open the link in a browser, then change any of the three number fields:

| Field | Meaning | Example |
| --- | --- | ---: |
| Customers reached | People included in a hypothetical campaign | 1,000 |
| Assumed conversion (%) | Percentage expected to place an order | 5 |
| Average basket (£) | Assumed sales value per converted customer | 50 |

The **Illustrative additional sales** figure updates as you type. With the example values, it is **1,000 × 5% × £50 = £2,500**. Try changing the conversion rate to **10**; the estimate becomes **£5,000**.

This is a *what-if calculation*, not a forecast, observed campaign result, or profit. It excludes campaign costs, returns and margin. The historical KPI cards, charts and cohort table remain based on the UCI dataset; changing these inputs does not change them. Your inputs stay in your browser and are not saved or submitted.

[Open the full dashboard from the top](https://banoth281.github.io/retail-growth-retention-decision-studio/) · [View the generated report source](report.html) · [View the Python analysis](analyze.py)

![Monthly valid sales, January–November 2011](outputs/monthly_revenue.png)

This portfolio project analyses UCI's **Online Retail** dataset: historical transactions from a UK-based online retailer between December 2010 and December 2011. It is a real public dataset, not current business activity. Source credit: Chen, D. (2015), *Online Retail*, UCI Machine Learning Repository, https://doi.org/10.24432/C5BW33, licensed CC BY 4.0. No source records were altered in the supplied workbook; the analysis creates derived outputs.

## Current UK retail market context (2026)

[Open the ONS market context panel](https://banoth281.github.io/retail-growth-retention-decision-studio/#current-market). It uses the Office for National Statistics (ONS) [Retail Sales Index internet sales workbook](https://www.ons.gov.uk/businessindustryandtrade/retailindustry/datasets/retailsalesindexinternetsales), released **18 September 2026**, with monthly observations through **August 2026**.

- **28.8%** of Great Britain's retail sales excluding automotive fuel were made online in August 2026 (seasonally adjusted, ONS series **MS6Y**).
- **£2,827.9 million** was the seasonally adjusted **average weekly** online sales value in August 2026 (ONS series **MZX6**). This is not monthly revenue.
- The panel plots the monthly online share for 2026. The source includes 2025 and 2026 observations in [`outputs/ons_market.json`](outputs/ons_market.json).

**Interpretation:** These are *national market indicators*, not transactions from the retailer in the UCI case study. Do not add the ONS amount to that retailer's revenue or treat the UK market trend as its growth. ONS may revise past values in later releases. The case study's customer retention and product findings remain historical.

To refresh the ONS panel after a new official release, run this in the project folder:

```powershell
python ons_context.py
python analyze.py
Copy-Item report.html index.html
python -m unittest discover -s tests -v
```

[`ons_context.py`](ons_context.py) downloads the current official workbook, reads the two named series by their ONS IDs, checks month alignment and writes the small JSON summary. Review the output and commit `outputs/ons_market.json`, `report.html` and `index.html` to publish an updated static demo. The test fixture checks that a later revision table cannot overwrite the main series.

## Explore markets with real data

[Open the interactive market explorer](https://banoth281.github.io/retail-growth-retention-decision-studio/#explorer) near the top of the dashboard:

1. Select a **country** or keep **All countries**.
2. Select a **month** or keep **All months**.
3. Compare the filtered **positive sales line value**, **valid sale lines**, and **share of all valid sales**. Inspect the monthly trend below the filters.
4. Select **Download filtered CSV** to inspect the aggregated country-month rows in Excel or another tool. The export does not contain customer records.

For a quick demo, choose **France** and then switch between **All months** and a month in 2011. The numbers and trend come from the UCI workbook processed by [`analyze.py`](analyze.py), using the same valid-sale rule as the headline KPI. The market aggregation is checked against the headline sales value and valid sale-line count in [the tests](tests/test_metrics.py). A valid sale line is a transaction line, not an invoice or customer. Country is the value recorded in the source. The trend shows full months January–November 2011; **All months** KPIs also include December 2010 and the partial December 2011.

## Get the data and run locally (Windows, Python 3.10+)

The dataset is [Online Retail at UCI](https://archive.ics.uci.edu/dataset/352/online+retail). You can [download the source ZIP directly](https://archive.ics.uci.edu/static/public/352/online+retail.zip), extract `Online Retail.xlsx`, and put it in a `data` folder next to `analyze.py`. **You can also skip this download:** `python analyze.py` fetches and saves the workbook automatically on first run.

Open a PowerShell terminal in the repository folder:

```powershell
python -m pip install -r requirements.txt
python ons_context.py
python analyze.py
Copy-Item report.html index.html
python -m unittest discover -s tests -v
start report.html
```

The source workbook is not committed to GitHub. The first run downloads about 24 MB; later runs reuse `data/Online Retail.xlsx`. The script writes `report.html`, `outputs/metrics.json`, and `outputs/retail.db`. The separate downloadable project ZIP includes the workbook for offline analysis.

## What the analysis found

| Measure | Result | Interpretation |
| --- | ---: | --- |
| Valid invoices | 19,960 | Positive-quantity, positive-price, non-cancellation invoices |
| Identified customers | 4,338 | Customers with an ID on a valid sale |
| Repeat customer rate | 65.6% | At least two distinct valid invoices in the observed period |
| Recorded positive line value | £10.67m | Includes some charge lines; **not profit** |

![Most frequently purchased products by distinct invoice count](outputs/top_products.png)

## Definitions and decisions

* **Valid sales:** invoice does not start with `C`; positive quantity and unit price. Recorded sales value = quantity × unit price. Some invoice lines are charges such as postage; the headline may include these and is **not profit**.
* **Cancellations:** count lines with invoice starting `C` or negative quantity separately. This is an operational signal, **not a true refund rate**: original purchases and cancellation lines are not linked reliably here.
* **Customer repeat rate:** customers with at least two distinct valid invoices divided by identified customers. Guest/unknown IDs are excluded.
* **Cohort retention:** customers whose first observed purchase was in a given month and who returned in a later month, divided by cohort size. This is observed-period retention, not lifetime retention; the early data may also include existing customers.
* **Product ranking:** distinct valid invoice count, excluding known postage/manual charge codes. It measures breadth of observed demand rather than profit or stock requirements.

The December 2011 source is partial, ending 9 December. The monthly revenue chart excludes it and uses January–November 2011; cohort month 1 uses cohorts from December 2010 through October 2011 so a subsequent month is observable.

## Evidence for recruiters

The report includes a source and methods panel, KPI cards, interactive country/month market explorer with CSV export, monthly trend, product ranking, cohort retention table and a separate what-if sales calculator. The SQLite database supports ad hoc SQL review. `sql/analysis.sql` supplies reconciliation and segment queries. The tests check revenue filtering, cancellation handling and cohort denominators on a deliberately small fixture.

This is an analysis case study, not a live shop. Suggested next milestone: turn the findings into a Power BI dashboard with slicers and document one business decision and its assumptions.
