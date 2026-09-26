"""Reproducible analysis of the UCI Online Retail transaction dataset."""
import json
import sqlite3
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'Online Retail.xlsx'
OUTPUT = ROOT / 'outputs'
SOURCE = 'https://archive.ics.uci.edu/static/public/352/online+retail.zip'


def load_source():
    DATA.parent.mkdir(exist_ok=True)
    if not DATA.exists():
        print('Downloading the UCI source workbook...')
        with urllib.request.urlopen(SOURCE, timeout=120) as response:
            content = response.read()
        with zipfile.ZipFile(BytesIO(content)) as archive:
            DATA.write_bytes(archive.read('Online Retail.xlsx'))
    return pd.read_excel(DATA, dtype={'InvoiceNo':'string','StockCode':'string','CustomerID':'string'})


def prepare(raw):
    df = raw.copy()
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'], errors='coerce')
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
    df['UnitPrice'] = pd.to_numeric(df['UnitPrice'], errors='coerce')
    df['InvoiceNo'] = df['InvoiceNo'].astype('string').str.strip()
    df['CustomerID'] = df['CustomerID'].astype('string').str.replace(r'\.0$', '', regex=True)
    df['is_cancel_line'] = df['InvoiceNo'].str.startswith('C', na=False) | df['Quantity'].lt(0)
    valid = df['InvoiceDate'].notna() & df['Quantity'].gt(0) & df['UnitPrice'].gt(0) & ~df['is_cancel_line']
    sales = df.loc[valid].copy()
    sales['revenue'] = (sales['Quantity'] * sales['UnitPrice']).round(2)
    sales['month'] = sales['InvoiceDate'].dt.to_period('M').astype(str)
    return df, sales


def cohort_table(sales):
    known = sales.dropna(subset=['CustomerID']).copy()
    if known.empty:
        return pd.DataFrame(columns=['cohort','customers','month_1_customers','month_1_rate'])
    known['period'] = known['InvoiceDate'].dt.to_period('M')
    activity = known[['CustomerID','period']].drop_duplicates()
    first = activity.groupby('CustomerID')['period'].min().rename('cohort')
    activity = activity.join(first, on='CustomerID')
    activity['offset'] = (activity['period'].dt.year - activity['cohort'].dt.year)*12 + (activity['period'].dt.month - activity['cohort'].dt.month)
    sizes = activity.loc[activity['offset'].eq(0)].groupby('cohort')['CustomerID'].nunique()
    returned = activity.loc[activity['offset'].eq(1)].groupby('cohort')['CustomerID'].nunique()
    result = pd.DataFrame({'customers': sizes, 'month_1_customers': returned}).fillna(0)
    result['month_1_customers'] = result['month_1_customers'].astype(int)
    result['month_1_rate'] = (result['month_1_customers'] / result['customers']).round(4)
    result.index = result.index.astype(str)
    return result.rename_axis('cohort').reset_index()


def compute(raw):
    df, sales = prepare(raw)
    known = sales.dropna(subset=['CustomerID'])
    invoices = known.groupby('CustomerID')['InvoiceNo'].nunique()
    months = sales.loc[sales['month'].between('2011-01','2011-11')].groupby('month')['revenue'].sum().round(2)
    # Operational charges are not products. Use invoice frequency to avoid
    # treating a single unusually large order as broad product demand.
    product_lines = sales.loc[~sales['StockCode'].isin(['DOT','POST','M','BANK CHARGES','C2'])]
    products = (product_lines.groupby(['StockCode','Description'], dropna=False)
                .agg(invoices=('InvoiceNo','nunique'), revenue=('revenue','sum'))
                .sort_values(['invoices','revenue'], ascending=False).head(10).reset_index())
    cohort = cohort_table(sales)
    cohort = cohort.loc[cohort['cohort'].between('2010-12','2011-10')].copy()
    metrics = {
        'source_rows': int(len(df)), 'valid_sale_lines': int(len(sales)),
        'excluded_lines': int(len(df)-len(sales)),
        'cancel_lines': int(df['is_cancel_line'].sum()),
        'revenue_gbp': round(float(sales['revenue'].sum()),2),
        'valid_invoices': int(sales['InvoiceNo'].nunique()),
        'identified_customers': int(len(invoices)),
        'repeat_customer_rate': round(float(invoices.ge(2).mean()),4),
        'unknown_customer_sale_lines': int(sales['CustomerID'].isna().sum()),
    }
    return metrics, months, products, cohort, sales


def market_summary(sales):
    """Additive invoice-line value by country and month for the explorer."""
    grouped = (sales.assign(Country=sales['Country'].fillna('Unknown'))
               .groupby(['Country', 'month'], dropna=False)
               .agg(revenue=('revenue', 'sum'), lines=('InvoiceNo', 'size'))
               .reset_index().sort_values(['Country', 'month']))
    return [{'country': str(row.Country), 'month': str(row.month),
             'revenue': round(float(row.revenue), 2), 'lines': int(row.lines)}
            for row in grouped.itertuples(index=False)]


def render(metrics, months, products, cohort, sales):
    from html import escape
    OUTPUT.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','figure.facecolor':'#101a2a','axes.facecolor':'#101a2a',
                         'text.color':'#eaf2fb','axes.labelcolor':'#c7d8ea','xtick.color':'#c7d8ea','ytick.color':'#c7d8ea'})
    fig, ax = plt.subplots(figsize=(11,3.4))
    ax.plot(months.index, months.values/1e6, color='#54ddc1',linewidth=3,marker='o')
    ax.set_ylabel('Valid sales (£m)');ax.tick_params(axis='x',rotation=35);ax.spines[['top','right']].set_visible(False)
    fig.tight_layout();fig.savefig(OUTPUT/'monthly_revenue.png',dpi=150);plt.close(fig)
    top = products.head(8).iloc[::-1]
    labels = [str(v)[:38] for v in top['Description'].fillna(top['StockCode'])]
    fig,ax=plt.subplots(figsize=(11,4.3));ax.barh(labels,top['invoices'],color='#54ddc1')
    ax.set_xlabel('Distinct valid invoices');ax.spines[['top','right']].set_visible(False)
    fig.tight_layout();fig.savefig(OUTPUT/'top_products.png',dpi=150);plt.close(fig)
    rows=''.join(f"<tr><td>{escape(str(r.cohort))}</td><td>{r.customers:,}</td><td>{r.month_1_customers:,}</td><td>{r.month_1_rate:.1%}</td></tr>" for r in cohort.itertuples())
    market_json = json.dumps(market_summary(sales), ensure_ascii=True).replace('<', '\\u003c')
    ons_path = OUTPUT / 'ons_market.json'
    if ons_path.exists():
        ons = json.loads(ons_path.read_text(encoding='utf-8'))
        series = ons['series']
        latest = series[-1]
        current_year = latest['month'][:4]
        recent = [item for item in series if item['month'].startswith(current_year)]
        prior = next((item for item in series if item['month'] == f'{int(current_year)-1}-{latest["month"][-2:]}'), None)
        share_change = latest['online_share_pct'] - prior['online_share_pct'] if prior else None
        ons_rows = ''.join(
            f'<div class="barrow"><span>{escape(item["month"])}</span>'
            f'<div class="bartrack"><div class="barfill" style="width:{max(0, min(100, (item["online_share_pct"]-20)*100/15)):.1f}%"></div></div>'
            f'<span class="barvalue">{item["online_share_pct"]:.1f}%</span></div>'
            for item in recent
        )
        ons_html = (
            '<section id="current-market" class="market-now"><div class="section-heading"><div>'
            '<p class="eyebrow">Current market / official statistics</p><h2>What is happening in online retail?</h2>'
            f'<p>Great Britain · latest available month <strong>{escape(latest["month"])}</strong> · '
            f'published <strong>{escape(ons["release_date"])}</strong></p></div>'
            '<span class="tool-badge">ONS data</span></div>'
            '<div class="cards"><div class="card">Online share of retail sales'
            f'<div class="value">{latest["online_share_pct"]:.1f}%</div><small>Seasonally adjusted, excluding fuel</small></div>'
            '<div class="card">Average weekly online sales'
            f'<div class="value">£{latest["average_weekly_online_sales_gbp_m"]:,.1f}m</div>'
            '<small>Weekly estimate, not monthly retailer revenue</small></div>'
            + (f'<div class="card">Online share vs {escape(prior["month"])}'
               f'<div class="value">{share_change:+.1f} pp</div><small>Percentage point change, not sales growth</small></div>' if prior else '')
            + '</div>'
            f'<h3>Online share by month · {current_year}</h3>'
            f'<div class="bars" role="img" aria-label="ONS online share of retail sales by month in {current_year}, '
            f'bar scale 20 to 35 percent">{ons_rows}</div>'
            '<p class="note">Bars use a 20–35% visual scale to show monthly differences. '
            'These are national market measures, not your uploaded sales or the historical retailer’s revenue. '
            'The ONS may revise previous months; no later month is assumed before it is released.</p>'
            f'<small>Source: <a href="{escape(ons["source"])}">ONS Retail Sales Index internet sales</a>, '
            'series MS6Y and MZX6. Refresh with <code>python ons_context.py</code>, then '
            '<code>python analyze.py</code>; ONS may revise past observations.</small></section>'
        )
    else:
        ons_html = '<section id="current-market"><h2>Current UK market context · ONS</h2><p>Run <code>python ons_context.py</code> and <code>python analyze.py</code> to add the latest official ONS series.</p></section>'
    report=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Analyse a sales CSV locally, review monthly sales and data quality, and model a retail campaign. Includes a sourced historical case study."><title>Retail Decision Studio · Sales analysis &amp; campaign planning</title><link rel="stylesheet" href="style.css"></head><body>
<a class="skip" href="#main">Skip to content</a><header class="topbar"><div class="topbar-inner"><a class="brand" href="#overview">RETAIL<span> / </span>DECISION STUDIO</a><nav aria-label="Main navigation"><a href="#your-data">Your sales CSV</a><a href="#current-market">2026 market</a><a href="#scenario">Campaign planner</a><a href="#explorer">Historical explorer</a><a href="#decisions">Case study</a><a href="#methods">Methods</a><a href="https://github.com/Banoth281/retail-growth-retention-decision-studio">GitHub ↗</a></nav></div></header>
<main id="main"><div class="hero" id="overview"><div class="hero-copy"><p class="eyebrow">Retail Decision Studio / free browser tool</p><h1>From sales file to <em>clear next steps.</em></h1><p class="lede">Bring a simple CSV. See monthly sales, order value and data checks. Then use your numbers to explore a campaign decision.</p><div class="actions"><a class="button" href="#your-data">Start with your sales →</a><a class="button secondary" href="#your-data" id="hero-sample">Try the sample</a></div><p class="hero-trust">No account · CSV analysed in your browser · Sample is fictional</p></div><div class="hero-preview" aria-label="What the product includes"><span class="preview-label">YOUR WORKFLOW</span><div class="preview-row"><span class="preview-index">01</span><span>Load a sales file</span><span class="preview-mark">↗</span></div><div class="preview-row"><span class="preview-index">02</span><span>Check the numbers</span><span class="preview-mark">↗</span></div><div class="preview-row"><span class="preview-index">03</span><span>Model a decision</span><span class="preview-mark">↗</span></div><p>Built around usable results and transparent assumptions.</p></div></div>
<section id="your-data" class="own-tool"><div class="section-heading"><div><p class="eyebrow">Workspace / 01</p><h2>Analyse your sales</h2><p>Turn a sales export into a usable snapshot in three short steps.</p></div><span class="tool-badge">Local analysis</span></div><ol class="steps" aria-label="Analysis steps"><li id="step-load" class="active"><span>1</span> Load data</li><li id="step-map"><span>2</span> Match columns</li><li id="step-review"><span>3</span> Review results</li></ol>
<div class="upload-panel"><div><h3>Start with a file or sample</h3><p>CSV columns: order date, order ID, positive sales value; customer ID is optional. Use dates like 2026-03-15 or 15/03/2026.</p><div class="upload-actions"><label class="file-button" for="sales-file">Choose your CSV<input id="sales-file" type="file" accept=".csv,text/csv"></label><button id="load-sample" class="button secondary" type="button">Explore fictional sample</button></div><small>Up to 5 MB and 100,000 rows. <a href="sample_sales.csv" download>Download the sample file</a>.</small></div><div class="privacy"><strong>Your data stays in this tab</strong><p>Selected files are read locally. The tool does not upload them or combine them with the historical case study.</p></div></div>
<p id="csv-status" role="status" aria-live="polite">Choose a CSV to begin. Dates may be YYYY-MM-DD or UK DD/MM/YYYY. Positive order or line values only.</p>
<div id="csv-mapping" class="workspace-panel" hidden><p class="eyebrow">Step 2 / check the mapping</p><h3>Match your columns</h3><p>We made a best guess. Confirm each field before calculating.</p><div class="planner-fields"><label>Order date <select id="column-date"></select></label><label>Order ID <select id="column-order"></select></label><label>Sales value (£) <select id="column-value"></select></label><label>Customer ID (optional) <select id="column-customer"></select></label></div><button id="own-run" type="button">Analyse sales →</button></div>
<div id="own-results" class="workspace-panel" hidden><div class="results-heading"><div><p class="eyebrow">Step 3 / decision snapshot</p><h3>Your sales summary</h3><small id="own-source"></small></div><span class="tool-badge">Ready to review</span></div><div class="planner-results"><div class="card">Positive sales value<div class="value" id="own-revenue"></div></div><div class="card">Distinct orders<div class="value" id="own-orders"></div></div><div class="card">Average order value<div class="value" id="own-aov"></div></div><div class="card">Identified customer repeat rate<div class="value" id="own-repeat"></div></div></div><p id="own-insight" class="planner-insight"></p><h3>Monthly positive sales value</h3><div id="own-bars" class="bars" role="img" aria-label="Monthly positive sales value from the selected CSV"></div><h3>Data checks</h3><p id="own-quality"></p><div class="result-actions"><button id="own-export" type="button" disabled>Download monthly summary CSV</button><button id="use-my-aov" class="button secondary" type="button">Use my order value in planner →</button></div></div>
<p class="note">Rows with missing order IDs, invalid dates or non-positive sales values are excluded and counted. Identical-looking rows are flagged but retained because they may be valid separate line items. Repeat rate counts identified customers with at least two distinct valid order IDs. The tool does not calculate profit or validate refunds. Do not upload a sensitive file to a shared computer.</p></section>
{ons_html}
<section id="scenario" class="planner"><p class="eyebrow">Interactive tool · use your own assumptions</p><h2>Retail campaign planner</h2><p>Estimate orders, incremental sales, contribution after campaign spend and the conversion rate needed to break even. Try the example, then replace every input with your own figures.</p>
<div class="planner-fields"><label>Customers reached<input id="reached" type="number" min="0" max="10000000" step="1" value="1000"><small>Distinct people who receive the campaign</small></label><label>Expected conversion (%)<input id="conversion" type="number" min="0" max="100" step="0.1" value="5"><small>Assumed share who place an extra order</small></label><label>Average order value (£)<input id="basket" type="number" min="0" max="1000000" step="0.01" value="50"><small>Expected value of each extra order</small></label><label>Gross margin (%)<input id="margin" type="number" min="0" max="100" step="0.1" value="40"><small>After cost of goods, before campaign spend</small></label><label>Campaign spend (£)<input id="spend" type="number" min="0" max="100000000" step="0.01" value="500"><small>Incremental marketing cost</small></label></div>
<p id="planner-error" role="alert" hidden>Enter valid numbers within the ranges shown.</p><div class="planner-results" aria-live="polite"><div class="card">Expected extra orders<div id="orders" class="value">50</div></div><div class="card">Incremental sales<div id="estimate" class="value">£2,500.00</div></div><div class="card">Contribution after spend<div id="net" class="value">£500.00</div></div><div class="card">Break-even conversion<div id="break-even" class="value">2.5%</div></div></div><p id="planner-insight" class="planner-insight">At these assumptions, estimated contribution covers campaign spend.</p>
<h3>Conversion sensitivity</h3><div class="table-scroll"><table><thead><tr><th>Case</th><th>Conversion</th><th>Extra sales</th><th>Contribution after spend</th></tr></thead><tbody id="sensitivity"></tbody></table></div><button id="planner-export" type="button">Download scenario CSV</button><p class="note">Assumptions are illustrative and may not match actual behaviour. Contribution after spend = expected extra sales × gross margin − campaign spend. It is not net profit: returns, VAT, overhead, fulfillment and other costs are excluded. Break-even conversion assumes each conversion makes one additional order. No personal data or inputs are sent to a server.</p></section>
<section id="story"><p class="eyebrow">The business question</p><h2>Where should a retailer focus attention?</h2><p class="section-lead">This project turns raw transaction lines into three areas for review. Each recommendation is a decision prompt, not a claim of proven impact.</p><div class="summary-grid"><article><div class="number">01 / TIMING</div><h3>Plan around demand</h3><p>Review full-month sales patterns before allocating campaign or support capacity.</p></article><article><div class="number">02 / PRODUCTS</div><h3>Check recurring demand</h3><p>Use invoice frequency to shortlist products, then validate margins and stock before acting.</p></article><article><div class="number">03 / RETENTION</div><h3>Test the next purchase</h3><p>Compare first-purchase cohorts and design a measurable repeat-purchase experiment.</p></article></div></section>
<p class="eyebrow">Historical case study · UCI transactions from 2010–11</p>
<div class="cards"><div class="card">Valid sales line value<div class="value">£{metrics['revenue_gbp']:,.0f}</div></div><div class="card">Valid invoices<div class="value">{metrics['valid_invoices']:,}</div></div><div class="card">Identified customers<div class="value">{metrics['identified_customers']:,}</div></div><div class="card">Repeat customers<div class="value">{metrics['repeat_customer_rate']:.1%}</div></div></div>
<section id="explorer"><p class="eyebrow">Historical case study / 2010–11</p><h2>Explore the historical retailer</h2><p>Filter UCI valid sale lines by country and month in 2010–11. These are recorded positive invoice-line values, including some charges; they are not profit or current market sales. A sale line is not an order. Country is the transaction's recorded country.</p><div class="cards"><label>Country<select id="market-country"></select></label><label>Month<select id="market-month"></select></label></div><div class="cards"><div class="card">Filtered sales value<div id="market-revenue" class="value"></div></div><div class="card">Valid sale lines<div id="market-lines" class="value"></div></div><div class="card">Share of all valid sales<div id="market-share" class="value"></div></div></div><p id="market-description"></p><div id="market-bars" class="bars" role="img" aria-label="Monthly sales value for selected country"></div><p><button id="market-export" type="button">Download filtered CSV</button></p><small>Monthly chart uses January–November 2011 for comparable full months. Filtered KPIs include December 2010 and partial December 2011 when All months is selected. CSV contains aggregated country-month rows, not customer records.</small></section>
<section id="decisions"><p class="eyebrow">Historical case study / 2010–11</p><h2>Decision 1 · Plan for the monthly pattern</h2><p>UCI retailer valid sales by invoice month, January–November 2011. These are historic company transactions, not recent national market data. The partial December 2011 month is excluded.</p><img src="outputs/monthly_revenue.png" alt="Historical UCI retailer monthly valid sales, January to November 2011"></section>
<section><h2>Decision 2 · Review recurring product demand</h2><p>Top products by distinct invoices across the full observed period. Postage and manual charge codes are excluded from this ranking. Frequency avoids treating one unusually large order as broad demand. A restock decision also needs stock, costs and margin data.</p><img src="outputs/top_products.png" alt="Top products by distinct invoice count"></section>
<section><h2>Decision 3 · Measure the next purchase</h2><p>Month 1 retention by first observed purchase month. Cohorts through October 2011 have at least one subsequent calendar month available.</p><div class="table-scroll"><table><thead><tr><th>First observed month</th><th>Customers</th><th>Returned next month</th><th>Retention</th></tr></thead><tbody>{rows}</tbody></table></div></section>

<section id="methods"><h2>Methods, quality &amp; limitations</h2><p>{metrics['source_rows']:,} source lines; {metrics['valid_sale_lines']:,} valid sales lines; {metrics['excluded_lines']:,} excluded lines, including {metrics['cancel_lines']:,} cancellation or negative-quantity lines. {metrics['unknown_customer_sale_lines']:,} valid sales lines lack customer IDs and are excluded from customer metrics.</p><p class="note">The headline is positive invoice-line value and may include charges such as postage; it is not profit. Cancellation lines are not a refund rate. The data ends 9 December 2011 and does not describe today's market.</p><p>Source: Chen, D. (2015), <a href="https://archive.ics.uci.edu/dataset/352/online+retail">Online Retail, UCI Machine Learning Repository</a>, <a href="https://doi.org/10.24432/C5BW33">DOI 10.24432/C5BW33</a>, CC BY 4.0. All calculations are reproducible with <code>python analyze.py</code>; see <a href="https://github.com/Banoth281/retail-growth-retention-decision-studio">GitHub README, SQL and tests</a> for definitions and review.</p></section></main><footer>Retail Growth &amp; Retention Decision Studio · Analysis by Santhosh Banoth · <a href="https://github.com/Banoth281/retail-growth-retention-decision-studio">Source code</a></footer></body></html>'''
    report=report.replace('</body></html>', '''<script id="market-data" type="application/json">''' + market_json + '''</script><script>
const markets = JSON.parse(document.getElementById('market-data').textContent);
const countrySelect = document.getElementById('market-country');
const monthSelect = document.getElementById('market-month');
const gbp = value => new Intl.NumberFormat('en-GB', {style:'currency', currency:'GBP'}).format(value);
const number = value => new Intl.NumberFormat('en-GB').format(value);
function addOption(select, value, label) { const item = document.createElement('option'); item.value = value; item.textContent = label; select.append(item); }
addOption(countrySelect, '', 'All countries');
[...new Set(markets.map(row => row.country))].sort().forEach(country => addOption(countrySelect, country, country));
addOption(monthSelect, '', 'All months');
[...new Set(markets.map(row => row.month))].sort().forEach(month => addOption(monthSelect, month, month));
let selectedRows = [];
function updateMarket() {
  selectedRows = markets.filter(row => (!countrySelect.value || row.country === countrySelect.value) && (!monthSelect.value || row.month === monthSelect.value));
  const sales = selectedRows.reduce((sum, row) => sum + row.revenue, 0);
  const lines = selectedRows.reduce((sum, row) => sum + row.lines, 0);
  const allSales = markets.reduce((sum, row) => sum + row.revenue, 0);
  document.getElementById('market-revenue').textContent = gbp(sales);
  document.getElementById('market-lines').textContent = number(lines);
  document.getElementById('market-share').textContent = (sales / allSales * 100).toFixed(1) + '%';
  const description = (countrySelect.value || 'All countries') + ' · ' + (monthSelect.value || 'All months');
  document.getElementById('market-description').textContent = description + ' · ' + selectedRows.length + ' country-month groups';
  const byMonth = new Map();
  selectedRows.filter(row => row.month >= '2011-01' && row.month <= '2011-11').forEach(row => byMonth.set(row.month, (byMonth.get(row.month) || 0) + row.revenue));
  const bars = document.getElementById('market-bars'); bars.replaceChildren();
  const max = Math.max(0, ...byMonth.values());
  for (const [month, value] of [...byMonth].sort((a,b) => a[0].localeCompare(b[0]))) {
    const row = document.createElement('div'); row.className = 'barrow';
    const date = document.createElement('span'); date.textContent = month;
    const track = document.createElement('div'); track.className = 'bartrack';
    const fill = document.createElement('div'); fill.className = 'barfill'; fill.style.width = (max ? value/max*100 : 0) + '%'; track.append(fill);
    const label = document.createElement('span'); label.className = 'barvalue'; label.textContent = gbp(value);
    row.append(date, track, label); bars.append(row);
  }
  bars.setAttribute('aria-label', 'Monthly valid sales value, ' + description + (byMonth.size ? '' : '; no full 2011 months selected'));
}
countrySelect.addEventListener('change', updateMarket);
monthSelect.addEventListener('change', updateMarket);
document.getElementById('market-export').addEventListener('click', () => {
  const csv = ['country,month,revenue_gbp,valid_sale_lines', ...selectedRows.map(row => [row.country, row.month, row.revenue.toFixed(2), row.lines].map(value => '"' + String(value).replaceAll('"', '""') + '"').join(','))].join('\\r\\n');
  const link = document.createElement('a'); const url = URL.createObjectURL(new Blob([csv], {type:'text/csv;charset=utf-8'}));
  link.href = url; link.download = 'retail-market-summary.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
updateMarket();
</script><script src="campaign.js"></script><script src="your_data.js"></script></body></html>''')
    (ROOT/'report.html').write_text(report,encoding='utf-8')


def main():
    raw=load_source()
    metrics,months,products,cohort,sales=compute(raw)
    render(metrics,months,products,cohort,sales)
    (OUTPUT/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    with sqlite3.connect(OUTPUT/'retail.db') as db:
        sales[['InvoiceNo','InvoiceDate','StockCode','Description','Quantity','UnitPrice','CustomerID','Country','revenue','month']].to_sql('valid_sales',db,if_exists='replace',index=False)
        cohort.to_sql('cohort_month_1',db,if_exists='replace',index=False)
    print(json.dumps(metrics,indent=2))
    print('Open report.html')


if __name__=='__main__': main()
