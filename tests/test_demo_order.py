import json
from pathlib import Path
import sqlite3
import time
import types
import unittest
from unittest.mock import patch
from demo_test import DemoOrderTest
import test_ai_trading

ROOT=Path(__file__).resolve().parents[1]


class DemoOrderTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE daily(day TEXT,account TEXT,equity REAL,PRIMARY KEY(day,account))')
        self.test=DemoOrderTest(self.db)
        self.cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        self.mt=test_ai_trading.WorkerTests().fake_terminal()
        self.mt.order_calc_profit=lambda kind,symbol,volume,opened,closed:(closed-opened)*100*volume
        self.mt.DEAL_ENTRY_OUT=1;self.mt.DEAL_ENTRY_OUT_BY=3
        self.mt.orders_get=lambda **kwargs:[]
        self.positions=[];self.sent=[]
        self.mt.positions_get=lambda **kwargs:list(self.positions)
        self.mt.order_send=self.send
    def tearDown(self):self.db.close()
    def send(self,order):
        self.sent.append(order)
        if 'position' not in order:
            self.positions.append(types.SimpleNamespace(identifier=3,ticket=77,magic=self.cfg['magic']+1,volume=order['volume']))
        else:self.positions.clear()
        return types.SimpleNamespace(order=77,deal=2,retcode=10009,comment='Done')
    def test_opens_minimum_with_protection_then_closes_only_its_position(self):
        result=self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(result['status'],'passed',result)
        self.assertEqual(len(self.sent),2)
        opening,closing=self.sent
        self.assertEqual(opening['volume'],.01)
        self.assertLess(opening['sl'],opening['price']);self.assertGreater(opening['tp'],opening['price'])
        self.assertEqual(closing['position'],77);self.assertEqual(closing['type'],self.mt.ORDER_TYPE_SELL)
        self.assertEqual(self.positions,[])
        self.assertEqual(self.test.latest()['status'],'passed')
    def test_no_real_account_orders(self):
        self.mt.account_info=lambda:types.SimpleNamespace(trade_mode=2,server='Live',login=1)
        result=self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(result['status'],'failed');self.assertEqual(self.sent,[])
    def test_existing_positions_are_untouched(self):
        self.positions.append(types.SimpleNamespace(ticket=99))
        result=self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(result['status'],'failed');self.assertEqual(self.sent,[])
        self.assertEqual(self.positions[0].ticket,99)
    def test_unknown_open_result_is_not_retried(self):
        self.mt.order_send=lambda order:self.sent.append(order)
        result=self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(result['status'],'attention')
        with self.assertRaises(ValueError):self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(len(self.sent),1)
    def test_failed_close_stays_unresolved_with_position_visible(self):
        def send(order):
            if 'position' in order:
                self.sent.append(order)
                return types.SimpleNamespace(retcode=10010,comment='Partial')
            return self.send(order)
        self.mt.order_send=send
        result=self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(result['status'],'attention');self.assertEqual(result['position_ticket'],77)
        self.assertEqual(len(self.positions),1)
        with self.assertRaises(ValueError):self.test.reset(self.mt,self.cfg['symbol'],'Demo:1')
    def test_account_switch_before_close_sends_no_order_to_live_account(self):
        demo=self.mt.account_info()
        accounts=iter([demo,demo,types.SimpleNamespace(trade_mode=2,server='Live',login=1)])
        self.mt.account_info=lambda:next(accounts)
        result=self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(result['status'],'attention');self.assertEqual(len(self.sent),1)
    def test_stale_quotes_block_test(self):
        self.mt.symbol_info_tick=lambda *args:types.SimpleNamespace(time=time.time()-100,bid=299.95,ask=300.)
        result=self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(result['status'],'failed');self.assertEqual(self.sent,[])
    def test_daily_loss_limit_blocks_test(self):
        day=time.strftime('%Y-%m-%d',time.gmtime())
        self.db.execute('INSERT INTO daily VALUES (?,?,?)',(day,'Demo:1',11000))
        result=self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(result['status'],'failed');self.assertIn('Tagesverlust',result['message'])
        self.assertEqual(self.sent,[])
    def test_duplicate_click_has_cooldown(self):
        self.test.run(self.mt,self.cfg,'Demo:1')
        with self.assertRaisesRegex(ValueError,'60 Sekunden'):self.test.run(self.mt,self.cfg,'Demo:1')
        self.assertEqual(len(self.sent),2)
