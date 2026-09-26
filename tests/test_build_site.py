import unittest

from build_site import render_market


class BuildSiteTests(unittest.TestCase):
    def test_shows_latest_release_and_separates_units(self):
        data = {
            'source': 'https://www.ons.gov.uk/example',
            'release_date': '18 September 2026',
            'series': [
                {'month': '2025-08', 'online_share_pct': 27.7, 'average_weekly_online_sales_gbp_m': 2596.0},
                {'month': '2026-07', 'online_share_pct': 28.4, 'average_weekly_online_sales_gbp_m': 2757.7},
                {'month': '2026-08', 'online_share_pct': 28.8, 'average_weekly_online_sales_gbp_m': 2827.9},
            ],
        }
        html = render_market(data)
        self.assertIn('28.8%', html)
        self.assertIn('£2,827.9m', html)
        self.assertIn('+1.1 pp', html)
        self.assertIn('18 September 2026', html)
        self.assertIn('2026-07', html)
        self.assertNotIn('2025-08</span>', html)  # only latest year in monthly chart

    def test_requires_ordered_months(self):
        with self.assertRaises(ValueError):
            render_market({'series': []})
        with self.assertRaises(ValueError):
            render_market({'series': [{'month': '2026-08'}, {'month': '2026-07'}]})
