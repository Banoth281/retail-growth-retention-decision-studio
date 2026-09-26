# Retail Decision Studio

A browser based product for analysing your own recent retail sales and understanding the latest **published** Great Britain online retail market statistics.

## Try the live product

[Open Retail Decision Studio](https://banoth281.github.io/retail-growth-retention-decision-studio/).

1. Click **Explore fictional sample** to see a worked example. It contains 12 fictional 2026 orders, £527.79 in positive sales value, and a £43.98 average order value.
2. Confirm the matched order date, order ID, sales value and optional customer ID columns. Click **Analyse sales** to review monthly totals, order metrics, repeat customers and data checks.
3. Click **Use my order value in planner** to carry the calculated average order value into a campaign scenario. Reach, conversion, margin and spend remain assumptions that you can change.
4. To analyse your own recent months, choose a UTF-8 comma-separated CSV (up to 5 MB and 100,000 rows). Dates can be `YYYY-MM-DD` or UK `DD/MM/YYYY`; value must be positive. [Download the fictional sample format](sample_sales.csv).

The selected CSV is processed by JavaScript within the browser tab; it is not uploaded to this static site. The downloadable monthly summary contains aggregates. Avoid using a shared computer for sensitive files.

## Current market context

The market panel uses the [ONS Retail Sales Index internet sales dataset](https://www.ons.gov.uk/businessindustryandtrade/retailindustry/datasets/retailsalesindexinternetsales), series **MS6Y** (seasonally adjusted online share of GB retail excluding fuel) and **MZX6** (average weekly online sales in £ millions). The latest month in the committed data is **August 2026**, released **18 September 2026**. The ONS may revise observations. National measures are kept separate from a visitor's sales file and the hypothetical campaign planner.

This site is static, so it does **not** fetch new ONS data automatically. After a new release, update and build it with Python 3.10+:

```powershell
python -m pip install -r requirements.txt
python ons_context.py
python build_site.py
python -m unittest discover -s tests -v
node --test tests/campaign.test.js tests/your_data.test.js
```

`ons_context.py` downloads the current ONS workbook and extracts the two series into `outputs/ons_market.json`; `build_site.py` generates `index.html` and `report.html` from `site_template.html`. Review the new month and release date before publishing. GitHub Pages serves `index.html`; GitHub Actions runs the Python and JavaScript tests on pushes.

For a local preview, use `python -m http.server 8000` and visit `http://localhost:8000/`. Opening `index.html` as a `file://` page may prevent the one-click sample from loading because browsers restrict local fetches.

## Definitions and limits

- **Positive sales value:** sum of valid positive CSV values; not profit or net revenue after refunds.
- **Distinct orders:** count of unique valid order IDs. Multiple valid lines from one order contribute to sales value but count as one order.
- **Repeat customer rate:** identified customer IDs with at least two distinct valid order IDs divided by all identified customers. Unknown IDs are excluded.
- **Data quality:** invalid dates, missing order IDs, non-positive values and malformed rows are excluded and counted. Identical-looking rows are flagged but retained because they may be legitimate separate line items.
- **Campaign planner:** contribution after spend = expected extra sales × gross margin − campaign spend. It excludes returns, VAT, fulfilment and overhead. Results are illustrative assumptions, not forecasts.

Built by Santhosh Banoth. Source and tests are in this repository.
