"""Durable demo-autopilot intent and order-attempt ledger."""
import sqlite3


class Autopilot:
    def __init__(self, db):
        self.db = db
        db.execute('CREATE TABLE IF NOT EXISTS autopilot (id INTEGER PRIMARY KEY CHECK(id=1), requested INTEGER, halt_reason TEXT)')
        db.execute('INSERT OR IGNORE INTO autopilot VALUES (1,1,NULL)')
        db.execute('''CREATE TABLE IF NOT EXISTS order_attempts
                     (symbol TEXT, frame TEXT, bar_time REAL,
                      PRIMARY KEY(symbol,frame,bar_time))''')
        db.commit()

    def state(self):
        requested, reason = self.db.execute('SELECT requested, halt_reason FROM autopilot WHERE id=1').fetchone()
        return dict(requested=bool(requested), halt_reason=reason,
                    armed=bool(requested and not reason))

    def request(self, enabled):
        # An explicit Start is the user's acknowledgement after inspecting a halted order.
        self.db.execute('UPDATE autopilot SET requested=?, halt_reason=NULL WHERE id=1', (int(enabled),))
        self.db.commit()
        return self.state()

    def halt(self, reason):
        self.db.execute('UPDATE autopilot SET halt_reason=? WHERE id=1', (reason,))
        self.db.commit()

    def claim_bar(self, symbol, frame, bar_time):
        try:
            self.db.execute('INSERT INTO order_attempts VALUES (?, ?, ?)', (symbol, frame, bar_time))
            self.db.commit()  # Must be durable BEFORE an external order is attempted.
            return True
        except sqlite3.IntegrityError:
            return False
