"""Exercise actual HTTP rendering without sockets, under a Windows-like default codec."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
# Loading the HTTP handler for tests must not create or alter a trading journal.
spec = importlib.util.spec_from_file_location('encoding_test_app', ROOT/'app.py')
app = importlib.util.module_from_spec(spec)
with patch('sqlite3.connect'):
    spec.loader.exec_module(app)


class EncodingTests(unittest.TestCase):
    def request(self, path):
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {'Host': '127.0.0.1:8765'}
        handler.request_version = 'HTTP/1.1'
        handler.requestline = 'GET '+path+' HTTP/1.1'
        handler.command = 'GET'
        handler.wfile = io.BytesIO()
        handler.do_GET()
        header, body = handler.wfile.getvalue().split(b'\r\n\r\n', 1)
        return header.decode('ascii'), body

    def test_dashboard_under_windows_default_encoding(self):
        original = Path.read_text
        def windows_read(path, encoding=None, errors=None):
            return original(path, encoding=encoding or 'cp1252', errors=errors)
        with patch.object(Path, 'read_text', windows_read):
            header, body = self.request('/')
        html = body.decode('utf-8')
        self.assertIn('text/html; charset=utf-8', header)
        for text in ('Modellprüfung', 'Ausführung', 'schließen', '·', '↑'):
            self.assertIn(text, html)
        self.assertNotIn('__TOKEN__', html)
        self.assertNotIn('ModellprÃ', html)

    def test_unicode_status_round_trip(self):
        message = 'Ausführung geprüft · höchstens eine Position → schließen'
        with patch.object(app, 'STATE', {'status': message}):
            header, body = self.request('/api/status')
        self.assertIn('application/json; charset=utf-8', header)
        self.assertEqual(json.loads(body.decode('utf-8'))['status'], message)

    def test_learning_endpoint_returns_real_persisted_runs(self):
        import sqlite3
        from learning import init_journal, record_training
        db = sqlite3.connect(':memory:')
        try:
            init_journal(db)
            details = dict(score=.6, weights=[0, 1, 2, 3, 4])
            record_training(db, 'XAUUSD', 'M5', 1, details)
            with patch.object(app, 'DB', db):
                header, body = self.request('/api/learning')
            self.assertIn('application/json; charset=utf-8', header)
            self.assertEqual(json.loads(body)[0]['version'], 1)
            self.assertEqual(json.loads(body)[0]['frame'], 'M5')
        finally:
            db.close()

    def test_config_accepts_windows_utf8_bom(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'config.json').write_text('{"symbol":"Göld"}', encoding='utf-8-sig')
            with patch.object(app, 'ROOT', root):
                self.assertEqual(app.config()['symbol'], 'Göld')


if __name__ == '__main__':
    unittest.main()
