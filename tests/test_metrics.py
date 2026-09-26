import sys
import unittest
from pathlib import Path
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze import compute, market_summary


class MetricsTests(unittest.TestCase):
    def test_revenue_cancellation_and_retention(self):
        rows=[
            ('100','A','2011-01-04',2,10,'u1'),
            ('101','B','2011-02-04',1,30,'u1'),
            ('102','B','2011-01-05',1,5,'u2'),
            ('C103','A','2011-02-05',-1,10,'u2'),
            ('104','B','2011-02-06',1,0,'u3'),
        ]
        raw=pd.DataFrame(rows,columns=['InvoiceNo','StockCode','InvoiceDate','Quantity','UnitPrice','CustomerID'])
        raw['Description']=raw['StockCode'];raw['Country']='United Kingdom'
        metrics,_,_,cohorts,_=compute(raw)
        self.assertEqual(metrics['revenue_gbp'],55)
        self.assertEqual(metrics['valid_invoices'],3)
        self.assertEqual(metrics['cancel_lines'],1)
        self.assertEqual(metrics['repeat_customer_rate'],0.5)
        jan=cohorts.loc[cohorts['cohort'].eq('2011-01')].iloc[0]
        self.assertEqual((jan['customers'],jan['month_1_customers'],jan['month_1_rate']),(2,1,0.5))

    def test_market_summary_reconciles_and_excludes_cancellations(self):
        raw=pd.DataFrame([
            ('100','2011-01-04',2,10,'United Kingdom'),
            ('101','2011-01-05',1,5,'France'),
            ('102','2011-02-04',1,30,'United Kingdom'),
            ('C103','2011-02-05',-1,10,'France'),
        ], columns=['InvoiceNo','InvoiceDate','Quantity','UnitPrice','Country'])
        raw['StockCode']='A';raw['Description']='Item';raw['CustomerID']='u1'
        metrics,_,_,_,sales=compute(raw)
        summary=market_summary(sales)
        self.assertEqual(sum(row['revenue'] for row in summary), metrics['revenue_gbp'])
        self.assertEqual(sum(row['lines'] for row in summary), metrics['valid_sale_lines'])
        self.assertEqual([(row['country'],row['month'],row['revenue']) for row in summary],
                         [('France','2011-01',5.0),('United Kingdom','2011-01',20.0),('United Kingdom','2011-02',30.0)])


if __name__=='__main__': unittest.main()
