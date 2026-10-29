import sqlite3
import unittest
import numpy as np
from learning import init_journal, record_training, training_history, training_details, explain_features


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        init_journal(self.db)
        self.model=dict(weights=np.array([.1,.2,-.3,.4,.5]),mean=np.ones(4),
                        scale=np.ones(4)*2,score=.6,approved=True,samples=100,validation_samples=25)
        self.bars=[dict(time=i*300) for i in range(100)]
    def tearDown(self):
        self.db.close()
    def test_trade_count_uses_training_cutoff(self):
        details=training_details(self.model,self.bars,[dict(closed_at=1),dict(closed_at=1e9)])
        self.assertEqual(details['trade_examples'],1)
        self.assertEqual(details['candle_examples'],99)
    def test_versions_are_separate_for_each_frame(self):
        details=training_details(self.model,self.bars,[])
        a=record_training(self.db,'XAUUSD','M5',1,details)
        b=record_training(self.db,'XAUUSD','H1',2,details)
        details['score']=.57
        c=record_training(self.db,'XAUUSD','M5',3,details)
        self.assertEqual((a['version'],b['version'],c['version']),(1,1,2))
        self.assertAlmostEqual(c['score_change_pp'],-3)
        self.assertEqual(c['previous_id'],a['id'])
        self.assertEqual(training_history(self.db)[0]['id'],c['id'])
    def test_full_weights_are_recoverable(self):
        details=training_details(self.model,self.bars,[])
        record_training(self.db,'XAUUSD','M5',1,details)
        saved=training_history(self.db)[0]
        np.testing.assert_array_equal(saved['weights'],self.model['weights'])
        self.assertEqual(saved['feature_names'][0],'Momentum 1 Kerze')
    def test_explanations_reconstruct_prediction_logit(self):
        x=np.array([2.,3.,4.,5.])
        influences=explain_features(self.model,x)
        total=self.model['weights'][0]+sum(row['contribution'] for row in influences)
        expected=np.r_[1,(x-self.model['mean'])/self.model['scale']]@self.model['weights']
        self.assertAlmostEqual(total,expected)
    def test_versions_survive_reopening_database(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.sqlite'
            db=sqlite3.connect(path);init_journal(db)
            record_training(db,'XAUUSD','M5',1,training_details(self.model,self.bars,[]))
            db.close()
            db=sqlite3.connect(path)
            row=record_training(db,'XAUUSD','M5',2,training_details(self.model,self.bars,[]))
            self.assertEqual(row['version'],2)
            db.close()

if __name__=='__main__': unittest.main()
