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

## Get the data and run locally (Windows, Python 3.10+)

The dataset is [Online Retail at UCI](https://archive.ics.uci.edu/dataset/352/online+retail). You can [download the source ZIP directly](https://archive.ics.uci.edu/static/public/352/online+retail.zip), extract `Online Retail.xlsx`, and put it in a `data` folder next to `analyze.py`. **You can also skip this download:** `python analyze.py` fetches and saves the workbook automatically on first run.

Open a PowerShell terminal in the repository folder:

```powershell
python -m pip install -r requirements.txt
python analyze.py
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

The report includes a source and methods panel, KPI cards, monthly trend, product ranking and cohort retention table. The SQLite database supports ad hoc SQL review. `sql/analysis.sql` supplies reconciliation and segment queries. The tests check revenue filtering, cancellation handling and cohort denominators on a deliberately small fixture.

This is an analysis case study, not a live shop. Suggested next milestone: turn the findings into a Power BI dashboard with slicers and document one business decision and its assumptions.
