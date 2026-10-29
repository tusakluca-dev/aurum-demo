import unittest
from datetime import datetime, timezone
import numpy as np
from core import position_size, zone_reason, features, train, probability

class RiskTests(unittest.TestCase):
    def test_does_not_round_up_minimum(self):
        self.assertEqual(position_size(5, 1000, .01, 100, .01), 0)
    def test_size_stays_within_budget(self):
        for budget in [1, 10, 25, 100, 1000]:
            size = position_size(budget, 731, .01, 100, .01)
            self.assertLessEqual(size*731, budget+1e-8)
    def test_maximum(self):
        self.assertEqual(position_size(10000, 1, .01, 2, .01), 2)
    def test_invalid_loss(self):
        self.assertEqual(position_size(100, 0, .01, 100, .01), 0)
    def test_zones(self):
        cfg = dict(max_spread_atr=.12, blocked_hours_utc=[22], price_zones=[[2700,2710]], blocked_windows_utc=[])
        now = datetime(2026,10,29,12,tzinfo=timezone.utc)
        self.assertIsNone(zone_reason(cfg, 2720, .1, 10, now))
        self.assertIn('Preiszone', zone_reason(cfg, 2700, .1, 10, now))
        self.assertIn('Spread', zone_reason(cfg, 2720, 2, 10, now))
        self.assertIn('Handelszeit', zone_reason(cfg, 2720, .1, 10, now.replace(hour=22)))
        cfg['blocked_windows_utc'] = [['2026-10-29T11:00:00+00:00','2026-10-29T13:00:00+00:00']]
        self.assertIn('Ereignis', zone_reason(cfg, 2720, .1, 10, now))

class ModelTests(unittest.TestCase):
    def bars(self):
        c = 2700+np.cumsum(np.random.default_rng(9).normal(size=1000))
        return [dict(time=i*300, open=p, close=p, high=p+1, low=p-1) for i,p in enumerate(c)]
    def test_features_have_no_future_dependency(self):
        bars = self.bars()
        full, _ = features(bars)
        part, _ = features(bars[:500])
        np.testing.assert_allclose(full[:500], part)
    def test_model_probability_and_score(self):
        bars = self.bars()
        model = train(bars)
        self.assertTrue(0 <= model['score'] <= 1)
        x, _ = features(bars)
        self.assertTrue(0 <= probability(model, x[-1]) <= 1)
    def test_future_trade_feedback_is_excluded(self):
        bars = self.bars()
        a = train(bars)
        b = train(bars, [dict(closed_at=1e12, label=1, features=[1,2,3,4])])
        np.testing.assert_array_equal(a['weights'], b['weights'])
    def test_old_trade_enters_training(self):
        bars = self.bars()
        a = train(bars)
        b = train(bars, [dict(closed_at=1, label=1, features=[1,2,3,4])])
        self.assertEqual(b['samples'], a['samples']+1)

if __name__ == '__main__':
    unittest.main()
