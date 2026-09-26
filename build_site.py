"""Build the static retail product from the latest saved ONS release."""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKET = ROOT / 'outputs' / 'ons_market.json'
TEMPLATE = ROOT / 'site_template.html'


def render_market(data):
    series = data['series']
    if not series or any(series[i]['month'] >= series[i + 1]['month'] for i in range(len(series) - 1)):
        raise ValueError('ONS series must contain months in ascending order')
    latest = series[-1]
    year = latest['month'][:4]
    recent = [row for row in series if row['month'].startswith(year)]
    prior = next((row for row in series if row['month'] == f'{int(year)-1}-{latest["month"][-2:]}'), None)

    bars = ''.join(
        '<div class="barrow">'
        f'<span>{escape(row["month"])}</span>'
        '<div class="bartrack">'
        f'<div class="barfill" style="width:{max(0, min(100, (row["online_share_pct"] - 20) * 100 / 15)):.1f}%"></div>'
        '</div>'
        f'<span class="barvalue">{row["online_share_pct"]:.1f}%</span></div>'
        for row in recent
    )
    comparison = ''
    if prior:
        difference = latest['online_share_pct'] - prior['online_share_pct']
        comparison = (f'<div class="card">Online share vs {escape(prior["month"])}'
                      f'<div class="value">{difference:+.1f} pp</div>'
                      '<small>Percentage point change, not sales growth</small></div>')

    return (
        '<section id="current-market" class="market-now"><div class="section-heading"><div>'
        '<p class="eyebrow">Current market / official statistics</p>'
        '<h2>What is happening in online retail?</h2>'
        f'<p>Great Britain · latest available month <strong>{escape(latest["month"])}</strong> · '
        f'published <strong>{escape(data["release_date"])}</strong></p></div>'
        '<span class="tool-badge">ONS data</span></div>'
        '<p id="market-scope" class="market-scope">This panel describes Great Britain. It is separate from your uploaded sales.</p>'
        '<div class="cards"><div class="card">Online share of retail sales'
        f'<div class="value">{latest["online_share_pct"]:.1f}%</div>'
        '<small>Seasonally adjusted, excluding fuel</small></div>'
        '<div class="card">Average weekly online sales'
        f'<div class="value">£{latest["average_weekly_online_sales_gbp_m"]:,.1f}m</div>'
        '<small>Weekly estimate, not monthly retailer revenue</small></div>'
        + comparison + '</div>'
        f'<h3>Online share by month · {escape(year)}</h3>'
        f'<div class="bars" role="img" aria-label="ONS online share of retail sales by month in {escape(year)}, '
        f'bar scale 20 to 35 percent">{bars}</div>'
        '<p class="note">Bars use a 20–35% visual scale to show monthly differences. '
        'These are national market measures, not your uploaded sales. '
        'The ONS may revise previous months; no later month is assumed before it is released.</p>'
        f'<small>Source: <a href="{escape(data["source"], quote=True)}">ONS Retail Sales Index internet sales</a>, '
        'series MS6Y and MZX6. Refresh with <code>python ons_context.py</code>, then '
        '<code>python build_site.py</code>.</small></section>'
    )


def build():
    data = json.loads(MARKET.read_text(encoding='utf-8'))
    template = TEMPLATE.read_text(encoding='utf-8')
    if template.count('{{MARKET_PANEL}}') != 1:
        raise ValueError('Template must have exactly one market panel placeholder')
    output = template.replace('{{MARKET_PANEL}}', render_market(data))
    for name in ('index.html', 'report.html'):
        (ROOT / name).write_text(output, encoding='utf-8')
    print(f"Built site with ONS data through {data['series'][-1]['month']}")


if __name__ == '__main__':
    build()
