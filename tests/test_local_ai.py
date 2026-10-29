import copy
import json
import sqlite3
import unittest
from unittest.mock import patch
from local_ai import (DEFAULTS, ResearchJournal, validate_proposal, parse_feed, propose,
                      run_research, research_entry_reason, ollama_json)
from research import DEFAULT_STRATEGY
from test_research import bars


def article():
    return dict(id='source1',title='Fed statement',published_at=500000,excerpt='Rates',background_only=False)

def proposal():
    return dict(analysis='Modellinterpretation einer Quelle',hypothesis='Momentum könnte anhalten',
                uncertainties=['Nicht verifiziert'],source_ids=['source1'],news_bias='unknown',
                risk='normal',strategy=dict(DEFAULT_STRATEGY))

class LocalAITests(unittest.TestCase):
    def test_unknown_sources_rejected(self):
        p=proposal();p['source_ids']=['invented']
        with self.assertRaises(ValueError):validate_proposal(p,[article()])
    def test_rss_ignores_future_and_undated_articles(self):
        xml=b'<rss><channel><item><title>valid</title><link>https://example.org/1</link><pubDate>Thu, 01 Jan 1970 00:00:00 GMT</pubDate></item><item><title>future</title><link>https://example.org/2</link><pubDate>Fri, 02 Jan 1970 00:00:00 GMT</pubDate></item><item><title>undated</title></item></channel></rss>'
        result=parse_feed(xml,'test',now=3600)
        self.assertEqual([a['title'] for a in result],['valid'])
    def test_strategy_request_never_sees_current_news_or_holdout(self):
        answers=[dict(hypothesis='Idea',strategy=DEFAULT_STRATEGY),proposal()]
        with patch('local_ai.ollama_json',side_effect=answers) as client:
            propose(DEFAULTS,'XAUUSD','M5',bars(),[article()],[])
        first=json.loads(client.call_args_list[0].args[1][1]['content'])
        self.assertNotIn('sources',first)
        self.assertEqual(first['development']['end'],599*300)
        self.assertLess(max(c['time'] for c in first['development']['recent_candles']),600*300)
        second=json.loads(client.call_args_list[1].args[1][1]['content'])
        self.assertEqual(second['sources'][0]['id'],'source1')
    def test_ollama_requests_only_loopback_and_disables_proxies(self):
        with patch('local_ai.request.build_opener') as build:
            response=build.return_value.open.return_value.__enter__.return_value
            response.read.return_value=b'{"message":{"content":"{}"}}'
            self.assertEqual(ollama_json(DEFAULTS,[]),{})
            req=build.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url,'http://127.0.0.1:11434/api/chat')
            self.assertEqual(build.call_args.args[0].proxies,{})
    def test_same_test_period_refreshes_news_without_retesting(self):
        journal=ResearchJournal(':memory:')
        snapshot=dict(symbol='XAUUSD',frame='M5',bars=bars(),costs={},cost_assumptions={})
        evaluation=dict(selected=None,candidate=DEFAULT_STRATEGY,tested_until=999*300,selection_reason='rejected',final_test={})
        fetch=lambda sources:([article()],[])
        try:
            with patch('local_ai.evaluate_candidate',return_value=evaluation) as evaluator:
                first=run_research(DEFAULTS,snapshot,journal,fetch,lambda *args:proposal())
                second=run_research(DEFAULTS,snapshot,journal,fetch,
                    lambda *args:self.fail('Repeated proposal'),lambda *args:proposal())
                self.assertEqual(evaluator.call_count,1)
            self.assertTrue(first['new_strategy_test'])
            self.assertFalse(second['new_strategy_test'])
            self.assertEqual(first['evaluated_at'],second['evaluated_at'])
            self.assertEqual(len(journal.history('XAUUSD','M5')),2)
        finally:journal.close()
    def test_unguarded_entries_are_explicit_opt_out(self):
        self.assertIsNone(research_entry_reason(dict(DEFAULTS,require_research_for_entries=False),None,{}))
        self.assertIn('nicht bereit',research_entry_reason(DEFAULTS,None,dict(symbol='XAUUSD',frame='M5')))
    def test_research_age_and_risk_gate(self):
        snapshot=dict(symbol='XAUUSD',frame='M5',costs=dict(slippage=0,commission=0),bars=bars(),direction=1)
        result=dict(symbol='XAUUSD',frame='M5',created_at=100,evaluated_at=100,costs=snapshot['costs'],
                    proposal=proposal(),evaluation=dict(selected=DEFAULT_STRATEGY))
        self.assertIsNone(research_entry_reason(DEFAULTS,result,snapshot,now=100))
        result['proposal']['risk']='high'
        self.assertIn('Risiko',research_entry_reason(DEFAULTS,result,snapshot,now=100))
        result['proposal']['risk']='normal'
        self.assertIn('veraltet',research_entry_reason(DEFAULTS,result,snapshot,now=100+86400*10))
        result['evaluation']['selected']=None
        self.assertIn('Keine KI-Strategie',research_entry_reason(DEFAULTS,result,snapshot,now=100))
