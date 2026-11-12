import csv
import io
import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import server

PARAMS = dict(org='example', user='alice', year=2026, month=10, method='both', repo_limit=20, include_repos='', verbose=False)
REPORT = dict(organization='example', user='alice', year=2026, month=10, complete=False,
              failures=['API unavailable'], active_days=['2026-10-05'], total_active_days=1,
              daily_activity_details={'2026-10-05': ['=HYPERLINK("bad")', 'Commit: ajout café <test>']},
              generated_at='2026-11-12T12:00:00+01:00')

class ReportsTest(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(server.validate(PARAMS), PARAMS)
        for key, value in [('org', '-flag'), ('month', 13), ('repo_limit', 0), ('year', True), ('include_repos', '../secret'), ('include_repos', 'docs.wiki'), ('method', 'unknown')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                server.validate(dict(PARAMS, **{key: value}))

    def test_csv_preserves_details_and_incomplete_status(self):
        rows = list(csv.reader(io.StringIO(server.csv_report(REPORT).decode('utf-8-sig'))))
        self.assertEqual(rows[1][3], 'False')
        self.assertTrue(rows[1][5].startswith("'="))
        self.assertEqual(rows[2][5], 'Commit: ajout café <test>')
        self.assertEqual(rows[2][6], 'API unavailable')
        empty = dict(REPORT, active_days=[], daily_activity_details={})
        self.assertEqual(len(list(csv.reader(io.StringIO(server.csv_report(empty).decode('utf-8-sig'))))), 2)

    def test_pdf_multipage_and_unicode(self):
        from pypdf import PdfReader
        report = dict(REPORT, daily_activity_details={'2026-10-05': REPORT['daily_activity_details']['2026-10-05'] * 100})
        pdf = server.pdf_report(report)
        reader = PdfReader(io.BytesIO(pdf))
        self.assertGreater(len(reader.pages), 1)
        text = ''.join(page.extract_text() for page in reader.pages)
        self.assertIn('Rapport incomplet', text)
        self.assertIn('café <test>', text)

    def test_job_retains_partial_results(self):
        class Tracker:
            daily_activity = REPORT['daily_activity_details']
            failures = REPORT['failures']
            api_call_count = 3
            def __init__(self, *args): pass
            def check_gh_cli(self): return True
            def get_user_activity(self, **kwargs): return {'2026-10-05'}
            def get_user_search_activity(self): return {'2026-10-05'}
        server.JOBS['test'] = {'status': 'running'}
        with patch.object(server, 'GitHubCLIActivityTracker', Tracker):
            server.run_job('test', PARAMS)
        self.assertEqual(server.JOBS['test']['status'], 'done')
        self.assertFalse(server.JOBS['test']['report']['complete'])
        del server.JOBS['test']

    def test_http_flow(self):
        http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{http.server_port}'
        try:
            self.assertIn(b'Votre travail', urlopen(base).read())
            with patch.object(server, 'run_job'):
                req = Request(base + '/api/reports', data=json.dumps(PARAMS).encode(), headers={'Content-Type': 'application/json'})
                with urlopen(req) as response:
                    self.assertEqual(response.status, 202)
                    job_id = json.load(response)['id']
                server.JOBS[job_id].update(status='done', report=REPORT)
                self.assertEqual(json.load(urlopen(base + '/api/reports/' + job_id))['status'], 'done')
                self.assertIn(b'organization', urlopen(base + '/api/reports/' + job_id + '.csv').read())
                self.assertTrue(urlopen(base + '/api/reports/' + job_id + '.pdf').read().startswith(b'%PDF'))
                del server.JOBS[job_id]
            bad = Request(base + '/api/reports', data=b'{}', headers={'Content-Type': 'application/json', 'Origin': 'http://other.test'})
            with self.assertRaises(HTTPError) as exc:
                urlopen(bad)
            self.assertEqual(exc.exception.code, 403)
        finally:
            http.shutdown()
            http.server_close()

if __name__ == '__main__':
    unittest.main()
