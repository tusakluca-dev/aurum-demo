"""One whole MT5 worker iteration against a fake demo terminal, no network/orders."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import numpy as np
from local_ai import DEFAULTS
from research import DEFAULT_STRATEGY
from test_research import bars

ROOT=Path(__file__).resolve().parents[1]


class EndIteration(BaseException):pass


class WorkerTests(unittest.TestCase):
    def load_app(self, db):
        spec=importlib.util.spec_from_file_location('ai_trading_test_app',ROOT/'app.py')
        app=importlib.util.module_from_spec(spec)
        with patch('sqlite3.connect',return_value=db):spec.loader.exec_module(app)
        return app
    def fake_terminal(self):
        mt=types.ModuleType('MetaTrader5')
        for key,value in dict(ACCOUNT_TRADE_MODE_DEMO=0,TIMEFRAME_M5=5,TIMEFRAME_H1=60,
                ORDER_TYPE_BUY=0,ORDER_TYPE_SELL=1,ORDER_FILLING_FOK=0,ORDER_FILLING_IOC=1,
                TRADE_ACTION_DEAL=1,ORDER_TIME_GTC=0,TRADE_RETCODE_DONE=10009,
                TRADE_RETCODE_DONE_PARTIAL=10010,POSITION_TYPE_BUY=0).items():setattr(mt,key,value)
        mt.initialize=lambda:True
        mt.account_info=lambda:types.SimpleNamespace(trade_mode=0,server='Demo',login=1,equity=10000,balance=10000)
        mt.symbol_select=lambda *a:True
        mt.symbol_info=lambda *a:types.SimpleNamespace(point=.01,digits=2,trade_stops_level=0,
                                volume_min=.01,volume_max=100,volume_step=.01,filling_mode=1)
        mt.symbol_info_tick=lambda *a:types.SimpleNamespace(time=time.time(),bid=299.95,ask=300.)
        mt.positions_get=lambda **k:[]
        mt.copy_rates_from_pos=lambda *a:bars()
        mt.order_calc_profit=lambda kind,symbol,volume,opened,closed:(closed-opened)*100
        mt.order_check=lambda *a:types.SimpleNamespace(retcode=0)
        mt.history_deals_get=lambda **k:[types.SimpleNamespace(position_id=3)]
        mt.last_error=lambda:'fake'
        mt.orders=[]
        def send(order):
            mt.orders.append(order)
            return types.SimpleNamespace(order=1,deal=2,retcode=10009)
        mt.order_send=send
        return mt
    def run_tick(self, result):
        db=sqlite3.connect(':memory:')
        app=self.load_app(db)
        mt=self.fake_terminal()
        cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        cfg.update(timeframes=['M5','H1'],blocked_hours_utc=[])
        cfg['max_spread_atr']=1
        class Learner:
            def __init__(self,*args):pass
            def evaluate(self,*args):
                return dict(available=True,approved=True,probability=.8,score=.6,samples=100,validation_samples=50),[1,2,3,4]
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'ROOT',Path(folder)), \
             patch.object(app,'config',return_value=cfg),patch.object(app,'FrameLearner',Learner), \
             patch.object(app,'load_settings',return_value=DEFAULTS), \
             patch.dict(sys.modules,{'MetaTrader5':mt}), patch.object(app.time,'sleep',side_effect=EndIteration):
            app.STATE['running']=True
            app.AI_STATE['result']=result
            with self.assertRaises(EndIteration):app.worker()
        return app,mt,db
    def test_missing_research_blocks_otherwise_strong_entry(self):
        app,mt,db=self.run_tick(None)
        try:
            self.assertEqual(mt.orders,[])
            self.assertIn('Forschung',app.STATE['status'])
            self.assertEqual(app.AI_INPUT['frame'],'M5')
        finally:db.close()
    def test_validated_strategy_is_used_and_exit_plan_persisted(self):
        now=time.time()
        result=dict(symbol='XAUUSD',frame='M5',created_at=now,evaluated_at=now,
            costs=dict(slippage=.05,commission=0),proposal=dict(risk='normal'),
            evaluation=dict(selected=dict(DEFAULT_STRATEGY,stop_atr=3, reward_risk=2)))
        app,mt,db=self.run_tick(result)
        try:
            self.assertEqual(len(mt.orders),1,app.STATE['status'])
            order=mt.orders[0]
            self.assertAlmostEqual(order['sl'],298.8,places=2)
            self.assertAlmostEqual(order['tp'],302.4,places=2)
            self.assertEqual(db.execute('SELECT hold_bars,frame FROM execution_plans').fetchone(),(12,'M5'))
        finally:db.close()

    def test_research_time_exit_uses_position_and_opposite_side(self):
        db=sqlite3.connect(':memory:')
        app=self.load_app(db);mt=self.fake_terminal()
        cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        mt.positions_get=lambda **kw:[types.SimpleNamespace(identifier=3,ticket=77,magic=cfg['magic'],type=0,volume=.1)]
        db.execute('INSERT INTO execution_plans VALUES (3,0,12,?)',('M5',))
        try:
            app.manage_research_exits(mt,cfg,'Demo:1')
            self.assertEqual(mt.orders[0]['position'],77)
            self.assertEqual(mt.orders[0]['type'],mt.ORDER_TYPE_SELL)
            self.assertEqual(mt.orders[0]['volume'],.1)
        finally:db.close()
    def test_time_exit_rejects_real_account(self):
        db=sqlite3.connect(':memory:')
        app=self.load_app(db);mt=self.fake_terminal()
        cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        mt.positions_get=lambda **kw:[types.SimpleNamespace(identifier=3,ticket=77,magic=cfg['magic'],type=0,volume=.1)]
        mt.account_info=lambda:types.SimpleNamespace(trade_mode=2,server='Live',login=1)
        db.execute('INSERT INTO execution_plans VALUES (3,0,12,?)',('M5',))
        try:
            with self.assertRaisesRegex(RuntimeError,'Demokonto'):app.manage_research_exits(mt,cfg,'Demo:1')
            self.assertEqual(mt.orders,[])
        finally:db.close()
