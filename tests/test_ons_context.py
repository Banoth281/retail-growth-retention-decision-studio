import sys
import unittest
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ons_context import parse_workbook


class ONSContextTests(unittest.TestCase):
    def test_aligns_months_by_series_id_and_preserves_units(self):
        book = Workbook()
        cover = book.active
        cover.title = 'Cover Sheet'
        cover.append(['This spreadsheet was published at 7.00am 18 September 2026'])
        for title, identifier, values in (
            ('ISCPSA3', 'MS6Y', [('2026 Jan', 27.9), ('2026 Aug', 28.8)]),
            ('IntValSA', 'MZX6', [('2026 Aug', 2827.9), ('2026 Jan', 2682.4)]),
        ):
            sheet = book.create_sheet(title)
            sheet.append(['Dataset identifier code', 'other', identifier])
            for month, value in values:
                sheet.append([month, 999, value])
            sheet.append([None, None, None])
            sheet.append(['2026 Aug', 999, 0.1])  # a separate revisions table
        stream = BytesIO()
        book.save(stream)
        result = parse_workbook(stream.getvalue())
        self.assertEqual(result['release_date'], '18 September 2026')
        self.assertEqual(result['series'], [
            {'month':'2026-01', 'online_share_pct':27.9, 'average_weekly_online_sales_gbp_m':2682.4},
            {'month':'2026-08', 'online_share_pct':28.8, 'average_weekly_online_sales_gbp_m':2827.9},
        ])


if __name__ == '__main__':
    unittest.main()
