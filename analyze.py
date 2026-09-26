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


def render(metrics, months, products, cohort):
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
    report=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Retail Growth & Retention Decision Studio</title><style>
body{{background:#0c1422;color:#eaf2fb;font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 20px}}h1{{font-size:38px}}p,small{{color:#b9c9dc;line-height:1.6}}a{{color:#54ddc1}}.cards{{display:flex;flex-wrap:wrap;gap:14px}}.card,section{{background:#172439;border:1px solid #30435c;border-radius:12px;padding:20px;margin:18px 0}}.card{{min-width:190px;flex:1}}.value{{font-size:30px;color:#54ddc1;font-weight:700}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%}}th,td{{padding:10px;border-bottom:1px solid #30435c;text-align:left}}th{{color:#54ddc1}}.note{{border-left:4px solid #f3be67;padding-left:14px}}
label{{display:block;margin:12px 0}}input{{display:block;margin-top:5px;padding:9px;background:#0c1422;color:#eaf2fb;border:1px solid #54708d;border-radius:5px;width:160px;max-width:100%;font:inherit}}.estimate{{font-size:28px;color:#54ddc1;font-weight:700}}
</style></head><body><h1>Retail Growth & Retention</h1><p>Decision studio · historical UK online retail transactions · Dec 2010–Dec 2011</p>
<div class="cards"><div class="card">Valid sales revenue<div class="value">£{metrics['revenue_gbp']:,.0f}</div></div><div class="card">Valid invoices<div class="value">{metrics['valid_invoices']:,}</div></div><div class="card">Identified customers<div class="value">{metrics['identified_customers']:,}</div></div><div class="card">Repeat customers<div class="value">{metrics['repeat_customer_rate']:.1%}</div></div></div>
<section><h2>Decision 1 · Plan for the monthly pattern</h2><p>Valid sales by invoice month, January–November 2011. The partial December 2011 month is excluded.</p><img src="outputs/monthly_revenue.png" alt="Monthly revenue trend"></section>
<section><h2>Decision 2 · Review recurring product demand</h2><p>Top products by distinct invoices across the full observed period. Postage and manual charge codes are excluded from this ranking. Frequency avoids treating one unusually large order as broad demand. A restock decision also needs stock, costs and margin data.</p><img src="outputs/top_products.png" alt="Top products by distinct invoice count"></section>
<section><h2>Decision 3 · Measure the next purchase</h2><p>Month 1 retention by first observed purchase month. Cohorts through October 2011 have at least one subsequent calendar month available.</p><table><thead><tr><th>First observed month</th><th>Customers</th><th>Returned next month</th><th>Retention</th></tr></thead><tbody>{rows}</tbody></table></section>
<section id="scenario"><h2>Try a sales scenario</h2><p>Enter assumptions to estimate additional sales from a customer campaign. This is an illustrative calculation, not a prediction or a change to the historical KPIs.</p><div class="cards"><label>Customers reached<input id="reached" type="number" min="0" max="10000000" step="1" value="1000"></label><label>Assumed conversion (%)<input id="conversion" type="number" min="0" max="100" step="0.1" value="5"></label><label>Average basket (£)<input id="basket" type="number" min="0" max="1000000" step="0.01" value="50"></label></div><p>Illustrative additional sales: <output id="estimate" class="estimate" aria-live="polite">£2,500.00</output></p><small>Formula: customers reached × conversion ÷ 100 × average basket. Excludes campaign costs, returns and margins; it is not profit. Your entries remain in your browser.</small></section>
<section><h2>Data quality and interpretation</h2><p>{metrics['source_rows']:,} source lines; {metrics['valid_sale_lines']:,} valid sales lines; {metrics['excluded_lines']:,} excluded lines, including {metrics['cancel_lines']:,} cancellation or negative-quantity lines. {metrics['unknown_customer_sale_lines']:,} valid sales lines lack customer IDs and are excluded from customer metrics.</p><p class="note">The headline is positive invoice-line value and may include charges such as postage; it is not profit. Cancellation lines are not a refund rate. The data ends 9 December 2011 and does not describe today's market.</p><p>Source: Chen, D. (2015), <a href="https://archive.ics.uci.edu/dataset/352/online+retail">Online Retail, UCI Machine Learning Repository</a>, <a href="https://doi.org/10.24432/C5BW33">DOI 10.24432/C5BW33</a>, CC BY 4.0. All calculations are reproducible with <code>python analyze.py</code>; see README for metric definitions and SQL for review.</p></section></body></html>'''
    report=report.replace('</body></html>', '''<script>
const fields = ['reached', 'conversion', 'basket'].map(id => document.getElementById(id));
const estimate = document.getElementById('estimate');
function calculate() {
  const [reached, conversion, basket] = fields.map(field => Number(field.value));
  if (fields.some(field => !field.validity.valid || field.value === '') || !Number.isInteger(reached)) {
    estimate.textContent = 'Enter valid numbers';
    return;
  }
  estimate.textContent = new Intl.NumberFormat('en-GB', {style:'currency', currency:'GBP'}).format(reached * conversion / 100 * basket);
}
fields.forEach(field => field.addEventListener('input', calculate));
calculate();
</script></body></html>''')
    (ROOT/'report.html').write_text(report,encoding='utf-8')


def main():
    raw=load_source()
    metrics,months,products,cohort,sales=compute(raw)
    render(metrics,months,products,cohort)
    (OUTPUT/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    with sqlite3.connect(OUTPUT/'retail.db') as db:
        sales[['InvoiceNo','InvoiceDate','StockCode','Description','Quantity','UnitPrice','CustomerID','Country','revenue','month']].to_sql('valid_sales',db,if_exists='replace',index=False)
        cohort.to_sql('cohort_month_1',db,if_exists='replace',index=False)
    print(json.dumps(metrics,indent=2))
    print('Open report.html')


if __name__=='__main__': main()
