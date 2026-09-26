"""Refresh official GB online retail context from the ONS internet sales workbook.

Run ``python ons_context.py`` after a new ONS release, then ``python build_site.py``.
"""
import json
import re
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / 'outputs' / 'ons_market.json'
SOURCE_PAGE = 'https://www.ons.gov.uk/businessindustryandtrade/retailindustry/datasets/retailsalesindexinternetsales'
SOURCE_FILE = ('https://www.ons.gov.uk/file?uri=%2Fbusinessindustryandtrade%2Fretailindustry%2F'
               'datasets%2Fretailsalesindexinternetsales%2Fcurrent%2Finternetreferencetables.xlsx')


def parse_workbook(content):
    book = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        cover = ' '.join(str(row[0]) for row in book['Cover Sheet'].values if row[0])
        release = re.search(r'published at [^\n]*?\b(\d{1,2} [A-Z][a-z]+ 20\d{2})', cover)
        if not release:
            raise ValueError('ONS publication date was not found')

        def series(sheet_name, series_id):
            rows = iter(book[sheet_name].values)
            column = None
            for row in rows:
                if row[0] == 'Dataset identifier code':
                    column = row.index(series_id)
                    break
            if column is None:
                raise ValueError(f'ONS series {series_id} was not found')
            values = {}
            for row in rows:
                if isinstance(row[0], str) and re.fullmatch(r'20\d\d [A-Z][a-z]{2}', row[0]):
                    month = datetime.strptime(row[0], '%Y %b').strftime('%Y-%m')
                    if isinstance(row[column], (int, float)) and month >= '2025-01':
                        values[month] = float(row[column])
                elif values:
                    # Later tables can contain revisions for the same month.
                    break
            return values

        share = series('ISCPSA3', 'MS6Y')  # seasonally adjusted internet % of GB retail (ex fuel)
        weekly = series('IntValSA', 'MZX6')  # seasonally adjusted weekly online value, GBP million
        months = sorted(set(share) & set(weekly))
        if not months or months[-1] < '2026-01':
            raise ValueError('ONS workbook does not contain a recent common month')
        return {
            'source': SOURCE_PAGE,
            'release_date': release.group(1),
            'definition': 'Great Britain, all retailing excluding automotive fuel; seasonally adjusted',
            'series': [
                {'month': month, 'online_share_pct': round(share[month], 1),
                 'average_weekly_online_sales_gbp_m': round(weekly[month], 1)}
                for month in months
            ],
        }
    finally:
        book.close()


def main():
    request = urllib.request.Request(SOURCE_FILE, headers={'User-Agent': 'RetailDecisionStudio/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        context = parse_workbook(response.read())
    DESTINATION.parent.mkdir(exist_ok=True)
    DESTINATION.write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    print(f"ONS context through {context['series'][-1]['month']}; released {context['release_date']}")


if __name__ == '__main__':
    main()
