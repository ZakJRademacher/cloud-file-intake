import base64
import copy
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.profile_engine import ProfileError, consolidate, inspect_file, validate_profile
from src.workbench import Workbench, sample_bundle


def bundle(kind):
    value = sample_bundle(kind)
    return value['profile'], Workbench.unpack_files(value['files'])


class ProfileEngineTests(unittest.TestCase):
    def test_cross_file_sales_dates_separators_conflicts_and_exact_decimals(self):
        profile, files = bundle('sales')
        result, artifacts = consolidate(profile, files)
        self.assertEqual(result['counts'], {'input_rows': 9, 'accepted_rows': 5, 'review_rows': 3, 'skipped_rows': 1, 'file_issues': 0, 'files': 2})
        # Control is from the five accepted source amounts, including a return and known zero.
        self.assertEqual(result['totals'][0]['total'], '1247.4428')
        rows = list(csv.DictReader(io.StringIO(artifacts['accepted.csv'].decode())))
        self.assertEqual({r['line_id'] for r in rows}, {'0001', '0003', '0004', '0006', '0007'})
        self.assertEqual(next(r for r in rows if r['line_id'] == '0006')['sale_date'], '2026-10-06')
        self.assertEqual(next(r for r in rows if r['line_id'] == '0006')['amount'], '1234.5678')
        self.assertEqual(next(r for r in rows if r['line_id'] == '0004')['amount'], '-2.25')
        review = list(csv.DictReader(io.StringIO(artifacts['needs_review.csv'].decode())))
        self.assertEqual(sum(r['line_id'] == '0002' for r in review), 2)
        self.assertEqual(next(r for r in review if r['line_id'] == '0005')['__source_record'], '6')
        self.assertTrue(result['complete'])

    def test_unrelated_domain_status_bounds_and_missing_is_not_zero(self):
        profile, files = bundle('tickets')
        result, _ = consolidate(profile, files)
        self.assertEqual(result['counts']['accepted_rows'], 3)
        self.assertEqual(result['counts']['review_rows'], 2)
        self.assertEqual(result['counts']['skipped_rows'], 1)
        self.assertEqual(result['totals'], [{'field': 'hours', 'total': '4.00', 'populated': 2, 'missing': 1}])
        self.assertEqual({r['values']['ticket_id'] for r in result['review_preview']}, {'T003', 'T005'})

    def test_arbitrary_inventory_composite_keys_extra_columns_and_formula_safety(self):
        profile = {'version': 1, 'name': 'Inventory', 'columns': [
            {'id': 'sku', 'type': 'text', 'required': True}, {'id': 'site', 'type': 'text', 'required': True},
            {'id': 'count', 'type': 'integer', 'required': True, 'min': '0'}], 'keys': ['sku', 'site'],
            'duplicates': 'keys', 'extra_columns': 'preserve', 'totals': ['count'], 'formats': [
                {'name': 'Stock', 'delimiter': ',', 'encoding': 'utf-8-sig', 'date_format': 'YYYY-MM-DD',
                 'mapping': {'sku': 'SKU', 'site': 'Warehouse', 'count': 'On Hand'}}]}
        file = {'name': '=inventory.csv', 'format': 'Stock', 'data': b'SKU,Warehouse,On Hand,Note\n001,West,2,=HYPERLINK("x")\n001,East,3,good\n'}
        # Use correctly quoted CSV for an untrusted formula-looking note.
        file['data'] = b'SKU,Warehouse,On Hand,Note\n001,West,2,=1+1\n001,East,3,good\n'
        result, outputs = consolidate(profile, [file])
        self.assertEqual(result['counts']['accepted_rows'], 2)
        self.assertEqual(result['totals'][0]['total'], '5')
        accepted = list(csv.DictReader(io.StringIO(outputs['accepted.csv'].decode())))
        self.assertEqual(accepted[0]['sku'], '001')
        self.assertEqual(accepted[0]['extra:Note'], "'=1+1")
        self.assertEqual(accepted[0]['__source_file'], "'=inventory.csv")
        profile['extra_columns'] = 'reject'
        rejected, _ = consolidate(profile, [file])
        self.assertFalse(rejected['complete']); self.assertIsNone(rejected['history'][0]['parsed_rows'])
        profile['extra_columns'] = 'ignore'
        _, outputs = consolidate(profile, [file]); self.assertNotIn(b'extra:Note', outputs['accepted.csv'])

    def test_explicit_date_order_no_rounding_and_malformed_grouping(self):
        profile, _ = bundle('sales'); profile['formats'] = [profile['formats'][0]]
        fmt = profile['formats'][0]; fmt['date_format'] = 'M/D/YYYY'
        file = {'name': 'x.csv', 'format': fmt['name'], 'data': b'Line ID,Date,Category,Sales\na,1/2/2026,Any,1.23456\nb,1/2/2026,Anything,1.2345\nc,1/2/2026,Any,"1,23.4"\n'}
        result, _ = consolidate(profile, [file])
        self.assertEqual(result['counts']['review_rows'], 2)
        self.assertEqual(result['preview'][0]['sale_date'], '2026-01-02')
        fmt['date_format'] = 'D/M/YYYY'
        result, _ = consolidate(profile, [file]); self.assertEqual(result['preview'][0]['sale_date'], '2026-02-01')
        self.assertEqual(result['totals'][0]['total'], '1.2345')

    def test_malformed_file_is_not_silently_counted_as_empty(self):
        profile, files = bundle('sales')
        files.append({'name': 'broken.csv', 'format': 'Standard CSV', 'data': b'Line ID,Date,Category,Sales\nz,2026-01-01\n'})
        result, outputs = consolidate(profile, files)
        self.assertEqual(result['counts']['input_rows'], 9)
        self.assertEqual(result['counts']['file_issues'], 1)
        self.assertIsNone(next(x for x in result['history'] if x['file'] == 'broken.csv')['parsed_rows'])
        self.assertIn(b'Wrong column count', outputs['file_issues.csv'])

    def test_duplicates_policies_and_invalid_copy_quarantine_all_keys(self):
        profile, _ = bundle('tickets')
        files = [{'name': 'one.csv', 'format': 'Helpdesk CSV', 'data': b'Ticket,Opened,Team,Status,Hours\nT1,2026-01-01,IT,Open,-1\nT1,2026-01-01,IT,Open,-1\nT2,2026-01-01,IT,Open,1\nT2,2026-01-01,IT,Open,1\n'}]
        result, _ = consolidate(profile, files)
        self.assertEqual((result['counts']['accepted_rows'], result['counts']['review_rows'], result['counts']['skipped_rows']), (1, 2, 1))
        profile['duplicates'] = 'keep'
        result, _ = consolidate(profile, files); self.assertEqual(result['counts']['accepted_rows'], 2)
        profile['duplicates'] = 'exact'; profile['keys'] = []
        result, _ = consolidate(profile, files); self.assertEqual(result['counts']['skipped_rows'], 1)

    def test_empty_delivery_and_cp1252_quoted_multiline_records(self):
        profile, _ = bundle('tickets'); profile['formats'][0]['encoding'] = 'cp1252'
        files = [{'name': 'x.csv', 'format': 'Helpdesk CSV', 'data': 'Ticket,Opened,Team,Status,Hours\nT1,2026-01-01,"Café\nSupport",Open,1.05\n'.encode('cp1252')}]
        result, _ = consolidate(profile, files)
        self.assertEqual(result['counts']['input_rows'], 1); self.assertEqual(result['preview'][0]['__source_record'], 2)
        files[0]['data'] = b'Ticket,Opened,Team,Status,Hours\n'
        result, _ = consolidate(profile, files); self.assertEqual(result['counts']['input_rows'], 0); self.assertTrue(result['complete'])

    def test_profile_guards_ambiguous_headers_and_unmapped_required_field(self):
        profile, _ = bundle('sales')
        for edit in [lambda p: p.update(keys=[]), lambda p: p['columns'][3].update(scale=1.5),
                     lambda p: p['formats'][0]['mapping'].update(line_id='Date'),
                     lambda p: p['formats'][0].update(decimal_mark=',', group_mark=','),
                     lambda p: p['columns'][3].update(min='NaN')]:
            broken = copy.deepcopy(profile); edit(broken)
            with self.assertRaises(ProfileError): validate_profile(broken)
        with self.assertRaises(ProfileError): inspect_file(b'Row ID,row_id\n1,2\n')
        files = [{'name': 'x.csv', 'format': 'Standard CSV', 'data': b'Line ID,Category,Sales\nx,Any,1\n'}]
        result, _ = consolidate(profile, files)
        self.assertEqual(result['counts']['file_issues'], 1); self.assertFalse(result['complete'])


class WorkbenchPublicationTests(unittest.TestCase):
    def test_saved_portable_profile_replay_restart_and_rule_change(self):
        with tempfile.TemporaryDirectory() as path:
            workbench = Workbench(path); example = sample_bundle('sales')
            saved = workbench.save_profile(example['profile'])
            self.assertEqual(Workbench(path).profiles()[0]['profile'], saved['profile'])
            first = workbench.run(saved['profile'], example['files'])
            repeat = Workbench(path).run(saved['profile'], list(reversed(example['files'])))
            self.assertTrue(repeat['reused']); self.assertEqual(first['job_id'], repeat['job_id'])
            self.assertEqual(first['counts'], repeat['counts'])
            altered = copy.deepcopy(saved['profile']); altered['columns'][3]['scale'] = 2
            second = workbench.run(altered, example['files'])
            self.assertNotEqual(first['job_id'], second['job_id'])
            self.assertEqual(len(workbench.jobs()), 2)

    def test_manifest_last_retry_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as path:
            workbench = Workbench(path); example = sample_bundle('tickets'); original_write = workbench.write
            def failure(target, data):
                if target.name == 'needs_review.csv': raise OSError('Deliberate interrupted publication')
                original_write(target, data)
            with patch.object(workbench, 'write', side_effect=failure):
                with self.assertRaises(OSError): workbench.run(example['profile'], example['files'])
            self.assertEqual(workbench.jobs(), [])
            result = workbench.run(example['profile'], example['files'])
            output = workbench.root / 'jobs' / result['job_id'] / 'accepted.csv'; output.write_bytes(b'corrupt')
            with self.assertRaises(RuntimeError): workbench.run(example['profile'], example['files'])
            with self.assertRaises(RuntimeError): workbench.download(result['job_id'], 'accepted.csv')
            self.assertIsNone(workbench.download(result['job_id'], '../raw/00.csv'))


if __name__ == '__main__': unittest.main()
