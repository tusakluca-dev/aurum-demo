import unittest
from unittest.mock import patch
from research import DEFAULT_STRATEGY, validate_strategy, signal, backtest, evaluate_candidate, development_summary


def bars(n=1000):
    return [dict(time=i*300,open=100+i*.2,close=100+i*.2+.15,high=100+i*.2+.3,low=100+i*.2-.1,spread=0.) for i in range(n)]


class StrategyTests(unittest.TestCase):
    def test_rejects_code_and_invalid_values(self):
        for change in [dict(family='exec(code)'),dict(lookback=True),dict(stop_atr=float('nan')),dict(lookback=500)]:
            with self.assertRaises(ValueError):validate_strategy(dict(DEFAULT_STRATEGY,**change))
        with self.assertRaises(ValueError):validate_strategy(dict(DEFAULT_STRATEGY,code='print(1)'))
    def test_momentum_and_reversion_opposite(self):
        data=bars(200)
        self.assertEqual(signal(DEFAULT_STRATEGY,data,.4),1)
        self.assertEqual(signal(dict(DEFAULT_STRATEGY,family='mean_reversion'),data,.4),-1)
    def test_no_future_data_used(self):
        data=bars()
        a=backtest(DEFAULT_STRATEGY,data,200,500)
        for b in data[500:]:b['close']+=10000;b['high']+=10000
        self.assertEqual(a,backtest(DEFAULT_STRATEGY,data,200,500))
        self.assertEqual(development_summary(bars())['end'],599*300)
    def test_costs_reduce_returns(self):
        strategy=dict(DEFAULT_STRATEGY,max_hold_bars=1)
        a=backtest(strategy,bars(),200,500)
        b=backtest(strategy,bars(),200,500,slippage=.03,commission=.02)
        self.assertLess(b['net_r'],a['net_r'])
    def test_ambiguous_candle_uses_stop_first(self):
        data=bars(103)
        data[101]['high']+=100;data[101]['low']-=100
        result=backtest(DEFAULT_STRATEGY,data,101,102)
        self.assertAlmostEqual(result['net_r'],-1)
    def test_stop_gap_can_exceed_one_r(self):
        data=bars(103)
        data[102].update(open=90,high=90.5,low=89,close=90)
        result=backtest(DEFAULT_STRATEGY,data,101,103)
        self.assertLess(result['net_r'],-1)
    def test_promote_only_if_both_intervals_pass_and_beat_reference(self):
        good=dict(trades=40,net_r=5,max_drawdown_r=2,mean_r=.125)
        ref=dict(good,net_r=3)
        with patch('research.backtest',side_effect=[good,ref,good,ref]):
            r=evaluate_candidate(dict(DEFAULT_STRATEGY,lookback=30),DEFAULT_STRATEGY,bars(),{})
        self.assertTrue(r['promoted'])
        weak=dict(good,trades=2)
        with patch('research.backtest',side_effect=[good,ref,weak,ref]):
            r=evaluate_candidate(dict(DEFAULT_STRATEGY,lookback=30),DEFAULT_STRATEGY,bars(),{})
        self.assertFalse(r['promoted'])
        self.assertEqual(r['selected'],DEFAULT_STRATEGY)
    def test_reject_all_if_candidate_and_reference_fail(self):
        weak=dict(trades=0,net_r=0,max_drawdown_r=0,mean_r=0)
        with patch('research.backtest',return_value=weak):
            r=evaluate_candidate(DEFAULT_STRATEGY,DEFAULT_STRATEGY,bars(),{})
        self.assertIsNone(r['selected'])
