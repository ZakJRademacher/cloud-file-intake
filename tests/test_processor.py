import csv
import io
from pathlib import Path
import unittest
from src.processor import transform, InputError, MAX_ROWS, MAX_BYTES

SAMPLE = Path(__file__).resolve().parents[1] / 'data/samples/weekly-sales.csv'
HEADER = b'record_id,sale_date,category,quantity,unit_price_cents\n'


class ProcessorTests(unittest.TestCase):
    def test_independent_counts_signed_amounts_and_all_conflicting_copies(self):
        counts, files = transform(SAMPLE.read_bytes())
        self.assertEqual(counts, {'input_rows': 14, 'accepted_rows': 6, 'review_rows': 7,
                                  'skipped_rows': 1, 'net_cents': 2050})
        rows = list(csv.DictReader(io.StringIO(files['accepted.csv'].decode())))
        self.assertEqual(rows[0]['record_id'], '00101')
        self.assertEqual([int(r['amount_cents']) for r in rows], [500, 1500, -250, 0, 300, 0])
        review = list(csv.DictReader(io.StringIO(files['needs_review.csv'].decode())))
        self.assertEqual([r['source_row'] for r in review if r['reason'] == 'conflicting_record_id'], ['5', '7'])
        self.assertEqual(files['summary.csv'].decode(), 'category,net_cents,record_count\nOffice,550,3\nTech,1500,3\n')

    def test_header_aliases_reordering_bom_and_line_endings(self):
        data = '\ufeffPrice_Cents,Qty,Product_Category,Date,ID\r\n500,1, Office ,2026-10-05,00201\r\n200,-1,Tech,2026-10-05,00202\r\n'.encode()
        counts, _ = transform(data)
        self.assertEqual(counts['net_cents'], 300)
        self.assertEqual(counts['accepted_rows'], 2)

    def test_contract_rejects_invalid_files(self):
        cases = [b'', b'\xff', HEADER+b'"unfinished', HEADER+b'1,2026-10-01,Office,1\n',
                 b'id,date,category,qty,qty\n', b'record_id,sale_date,category,quantity,unit_price_cents,extra\n',
                 HEADER+b'\x00', b'x'*(MAX_BYTES+1)]
        for data in cases:
            with self.subTest(data=data[:80]), self.assertRaises(InputError):
                transform(data)

    def test_limits_and_integer_date_rules(self):
        for q,p,day in [('1.0','100','2026-10-01'),('1','1.2','2026-10-01'),('1000001','1','2026-10-01'),('1','100000001','2026-10-01'),('1','1','2026-02-30')]:
            counts,_=transform(HEADER+f'001,{day},Office,{q},{p}\n'.encode())
            self.assertEqual(counts['review_rows'],1)
        counts,_=transform(HEADER+b'001,2026-10-01,Office,-1000000,100000000\n')
        self.assertEqual(counts['net_cents'],-100000000000000)
        rows=b''.join(f'{i},2026-10-01,Office,1,1\n'.encode() for i in range(MAX_ROWS+1))
        with self.assertRaises(InputError): transform(HEADER+rows)

    def test_review_export_neutralizes_formulas_and_preserves_input(self):
        raw=HEADER+b'001,2026-10-01,=HYPERLINK(bad),1,100\n'
        before=bytes(raw)
        _,files=transform(raw)
        self.assertIn("'=HYPERLINK(bad)",files['needs_review.csv'].decode())
        self.assertEqual(raw,before)

    def test_header_only_has_zero_controls(self):
        counts,_=transform(HEADER)
        self.assertEqual(list(counts.values()),[0,0,0,0,0])


if __name__=='__main__': unittest.main()
