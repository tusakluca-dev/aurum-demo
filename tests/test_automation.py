import sqlite3
import tempfile
from pathlib import Path
import unittest
from automation import Autopilot


class AutopilotTests(unittest.TestCase):
    def test_initially_requested_but_manual_stop_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.sqlite'
            db=sqlite3.connect(path);control=Autopilot(db)
            self.assertTrue(control.state()['armed'])
            control.request(False);db.close()
            db=sqlite3.connect(path);control=Autopilot(db)
            self.assertFalse(control.state()['requested'])
            control.request(True)
            self.assertTrue(control.state()['armed'])
            db.close()
    def test_uncertain_order_halt_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.sqlite'
            db=sqlite3.connect(path);control=Autopilot(db)
            control.halt('Orderstatus unklar');db.close()
            db=sqlite3.connect(path);control=Autopilot(db)
            self.assertTrue(control.state()['requested'])
            self.assertFalse(control.state()['armed'])
            self.assertEqual(control.state()['halt_reason'],'Orderstatus unklar')
            control.request(True)
            self.assertTrue(control.state()['armed'])
            db.close()
    def test_order_attempt_deduplicates_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.sqlite'
            db=sqlite3.connect(path);control=Autopilot(db)
            self.assertTrue(control.claim_bar('XAUUSD','M5',1000));db.close()
            db=sqlite3.connect(path);control=Autopilot(db)
            self.assertFalse(control.claim_bar('XAUUSD','M5',1000))
            self.assertTrue(control.claim_bar('XAUUSD','M5',1300))
            self.assertTrue(control.claim_bar('XAUUSD','H1',1000))
            db.close()
