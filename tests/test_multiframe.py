import unittest
from unittest.mock import patch
import numpy as np
from multiframe import consensus, feedback_by_frame, FrameLearner


def report(p=.8, approved=True):
    return dict(probability=p, available=True, approved=approved)


class MultiFrameTests(unittest.TestCase):
    def test_requires_confirmation(self):
        _, reason = consensus({'M5':report(), 'H1':report(.5)}, 'M5', .65, 2)
        self.assertIn('wenige', reason)
    def test_matching_frames_allow_signal(self):
        p, reason = consensus({'M5':report(), 'H1':report(.7)}, 'M5', .65, 2)
        self.assertIsNone(reason)
        self.assertEqual(p, .8)
    def test_conflicting_frames_block(self):
        _, reason = consensus({'M5':report(), 'H1':report(.2)}, 'M5', .65, 2)
        self.assertIn('widersprüchliche', reason)
    def test_failed_validation_cannot_confirm(self):
        _, reason = consensus({'M5':report(), 'H1':report(.8, False)}, 'M5', .65, 2)
        self.assertIn('wenige', reason)
    def test_execution_model_must_pass(self):
        _, reason = consensus({'M5':report(.8, False), 'H1':report()}, 'M5', .65, 2)
        self.assertIn('Validierung', reason)
    def test_missing_frame_abstains(self):
        _, reason = consensus({'M5':report(), 'H1':{'available':False}}, 'M5', .65, 2)
        self.assertIsNotNone(reason)
    def test_legacy_feedback_is_only_m5(self):
        rows=[dict(closed_at=1,label=1,features=[1,2,3,4]),
              dict(closed_at=2,label=0,features={'M5':[2,3,4,5],'H1':[6,7,8,9]})]
        grouped=feedback_by_frame(rows)
        self.assertEqual(len(grouped['M5']),2)
        self.assertEqual(len(grouped['H1']),1)
        self.assertEqual(grouped['H1'][0]['features'],[6,7,8,9])
    def test_separate_model_cache_per_symbol_and_frame(self):
        model=dict(weights=np.zeros(5),mean=np.zeros(4),scale=np.ones(4),score=.6,samples=100,validation_samples=50,approved=True)
        bars=[dict(time=i*300,close=2700+i,high=2701+i,low=2699+i) for i in range(100)]
        learner=FrameLearner()
        with patch('multiframe.train',return_value=model) as trainer:
            learner.evaluate('XAUUSD','M5',bars,[])
            learner.evaluate('XAUUSD','H1',bars,[])
            learner.evaluate('XAUUSD','M5',bars,[])
            learner.evaluate('GOLD','M5',bars,[])
            self.assertEqual(trainer.call_count,3)

if __name__=='__main__': unittest.main()
