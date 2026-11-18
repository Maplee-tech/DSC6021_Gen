import unittest
import test_workflow
from core.engine import NoRecommendedAction
class NoPlanTests(test_workflow.Flow):
 def test_empty_selection_does_not_spend_budget(self):
  self.generate();before=self.w.store.load(self.id)
  with self.assertRaises(NoRecommendedAction) as error:self.w.plan(self.id,[])
  self.assertIn('尚未选择',str(error.exception));after=self.w.store.load(self.id)
  self.assertEqual(before['attempts'],after['attempts']);self.assertEqual(after['plans'],[])
 def test_pass_and_uncertain_not_forced_by_risk_override(self):
  self.generate()
  with self.assertRaises(NoRecommendedAction) as error:self.w.plan(self.id,['b'],True)
  self.assertIn('满足',str(error.exception))
  self.w.correct(self.id,'a','uncertain','不能确定')
  with self.assertRaises(NoRecommendedAction) as error:self.w.plan(self.id,['a'],True)
  self.assertIn('不确定',str(error.exception))
 def test_negative_utility_explained_and_explicit_override(self):
  from test_workflow import c
  self.w.confirm(self.id,[c('a',typ='scene'),c('b'),c('c')],{'mock_scenario':'mixed'})
  self.generate()
  with self.assertRaises(NoRecommendedAction) as error:self.w.plan(self.id,['a'])
  self.assertIn('U -1.30',str(error.exception))
  p=self.w.plan(self.id,['a'],True);self.assertEqual(p['target_ids'],['a'])
