import io
import json
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from sizing import SizingPreferences, selected_volume, check_broker_lots, parse_lots
from test_encoding import app

LIMITS=dict(min=.01,max=100,step=.01)


class SizingTests(unittest.TestCase):
    def test_decimal_comma_and_exact_broker_steps(self):
        self.assertEqual(check_broker_lots('1,00',LIMITS),1.)
        self.assertEqual(check_broker_lots('.30',dict(min=.1,max=5,step=.1)),.3)
        for value in ['0.015',0,101,'NaN','Infinity',True]:
            with self.subTest(value=value), self.assertRaises(ValueError):check_broker_lots(value,LIMITS)
    def test_preferences_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.sqlite'
            db=sqlite3.connect(path);prefs=SizingPreferences(db)
            self.assertEqual(prefs.get()['mode'],'auto')
            prefs.save('fixed','1,00',LIMITS);db.close()
            db=sqlite3.connect(path);prefs=SizingPreferences(db)
            self.assertEqual(prefs.get(),dict(mode='fixed',fixed_lot=1.))
            db.close()
    def test_invalid_save_preserves_previous_setting(self):
        db=sqlite3.connect(':memory:');prefs=SizingPreferences(db)
        prefs.save('fixed',1,LIMITS)
        for mode,value in [('other',2),('fixed',.015),('fixed',-1)]:
            with self.assertRaises(ValueError):prefs.save(mode,value,LIMITS)
            self.assertEqual(prefs.get(),dict(mode='fixed',fixed_lot=1.))
        db.close()
    def test_fixed_lots_are_not_silently_capped_by_auto_budget(self):
        self.assertEqual(selected_volume(dict(mode='fixed',fixed_lot=1),25,100,LIMITS),1)
        self.assertEqual(selected_volume(dict(mode='auto',fixed_lot=1),25,100,LIMITS),.25)
    def test_invalid_fixed_lot_is_never_rounded(self):
        with self.assertRaises(ValueError):selected_volume(dict(mode='fixed',fixed_lot=.015),25,100,LIMITS)


class SizingAPITests(unittest.TestCase):
    def post(self, body, token):
        handler=app.Handler.__new__(app.Handler)
        raw=json.dumps(body).encode('utf-8')
        handler.path='/api/sizing';handler.command='POST';handler.request_version='HTTP/1.1';handler.requestline='POST /api/sizing HTTP/1.1'
        handler.headers={'Host':'127.0.0.1:8765','X-Token':token,'Content-Length':str(len(raw))}
        handler.rfile=io.BytesIO(raw);handler.wfile=io.BytesIO();handler.do_POST()
        header,response=handler.wfile.getvalue().split(b'\r\n\r\n',1)
        return int(header.split()[1]),json.loads(response)
    def test_save_comma_value_and_reject_invalid_broker_step(self):
        db=sqlite3.connect(':memory:');prefs=SizingPreferences(db)
        with patch.object(app,'SIZING',prefs),patch.object(app,'STATE',dict(volume_limits=LIMITS)):
            code,data=self.post(dict(mode='fixed',fixed_lot='1,00'),app.TOKEN)
            self.assertEqual(code,200);self.assertEqual(data['preferences']['fixed_lot'],1)
            code,data=self.post(dict(mode='fixed',fixed_lot='.015'),app.TOKEN)
            self.assertEqual(code,400);self.assertEqual(prefs.get()['fixed_lot'],1)
        db.close()
    def test_missing_token_cannot_change_size(self):
        db=sqlite3.connect(':memory:');prefs=SizingPreferences(db)
        with patch.object(app,'SIZING',prefs):
            code,_=self.post(dict(mode='fixed',fixed_lot=1),'')
            self.assertEqual(code,403);self.assertEqual(prefs.get()['mode'],'auto')
        db.close()
