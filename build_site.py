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
        '<section id="current-market" class="market-now"><p class="eyebrow">Current market / official statistics</p>'
        '<h2>Online retail by country</h2>'
        '<p>Choose a market to see the official series currently included. This section is separate from your sales CSV.</p>'
        '<label class="market-picker">Market country or territory<select id="market-country" aria-label="Market country or territory">'
        '<option value="">Choose a country or territory</option></select></label>'
        '<p id="market-empty" class="market-scope">Select a country to see available official market context.</p>'
        '<div id="market-gb" hidden><div class="section-heading"><div>'
        '<h3>Great Britain · ONS internet sales</h3>'
        f'<p>Latest available month <strong>{escape(latest["month"])}</strong> · '
        f'published <strong>{escape(data["release_date"])}</strong></p></div>'
        '<span class="tool-badge">ONS data</span></div>'
        '<p class="market-scope">Great Britain only; this is not UK-wide or your retailer’s sales.</p>'
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
        '<code>python build_site.py</code>.</small></div>'
        '<div id="market-us" hidden><div class="section-heading"><div><h3>United States · Census retail e-commerce</h3>'
        '<p>Latest included quarter <strong>2026 Q2</strong> · published <strong>18 August 2026</strong></p></div>'
        '<span class="tool-badge">U.S. Census</span></div>'
        '<p class="market-scope">Quarterly U.S. retail e-commerce; separate methodology and period from Great Britain’s monthly ONS series.</p>'
        '<div class="cards"><div class="card">E-commerce share of retail sales<div class="value">17.1%</div>'
        '<small>Seasonally adjusted, 2026 Q2</small></div><div class="card">Retail e-commerce sales'
        '<div class="value">$340.2bn</div><small>Seasonally adjusted, 2026 Q2; not adjusted for price changes</small></div>'
        '<div class="card">E-commerce sales vs 2025 Q2<div class="value">+12.2%</div>'
        '<small>Year-on-year change in seasonally adjusted estimate (±0.9 pp)</small></div></div>'
        '<p class="note">The Census estimate is quarterly and follows a different definition from the ONS monthly Great Britain series. '
        'Do not compare these shares as a like-for-like country ranking.</p>'
        '<small>Source: <a href="https://www.census.gov/retail/ecommerce.html">U.S. Census Bureau, '
        'Quarterly Retail E-Commerce Sales, 2026 Q2</a>.</small></div>'
        '<div id="market-in" hidden><h3>India · source coverage</h3>'
        '<p class="market-scope">No verified nationwide online-retail share series is included for India. '
        'The ONDC data below measure orders on that network only, not all Indian e-commerce.</p>'
        '<p>Explore <a href="https://opendata.ondc.org/retail">ONDC retail orders open data</a>. '
        'Check its reporting dates and definitions before using a number in a decision.</p></div>'
        '<div id="market-other" hidden><h3 id="market-other-title"></h3>'
        '<p class="market-scope">No verified country-specific online-retail series has been added for this selection. '
        'The site will not substitute another country’s figures or invent a market estimate.</p>'
        '<p>Your own CSV analysis and campaign scenario remain available in your selected currency.</p></div></section>'
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
