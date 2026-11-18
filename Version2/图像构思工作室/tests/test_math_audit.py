import unittest,itertools
from unittest.mock import patch
from test_workflow import c,req,ev
import test_workflow
from core.engine import rank_actions,compare_versions,validate_constraints
class MathAudit(unittest.TestCase):
 def test_ranking_order_and_terms(self):
  r=req([c('a'),c('b',strength='preference'),c('p',entity='a')])
  checks=ev({'a':'fail','b':'fail','p':'pass'})['checks']
  actions,_=rank_actions(r,checks,['a','b'])
  self.assertEqual([x['id'] for x in actions],['b','a']) # .5 > .2 despite must weight
  self.assertAlmostEqual(actions[0]['utility'],.5)
  self.assertAlmostEqual(actions[1]['utility'],.2)
  for a in actions:
   self.assertAlmostEqual(a['utility'],sum(t['weight']*t['e'] for t in a['benefit_terms'])-a['lambda_value']*sum(t['weight'] for t in a['risk_terms'])-a['mu_value']*a['cost_units'])
 def test_all_transition_pairs(self):
  for old,new in itertools.product(['pass','fail','uncertain'],repeat=2):
   for strength,w in [('must',3),('preference',1)]:
    out=compare_versions(req([c('a',strength=strength)]),ev({'a':old}),ev({'a':new}))
    self.assertEqual(out['G'],w if old=='fail' and new=='pass' else 0)
    self.assertEqual(out['R'],w if old=='pass' and new=='fail' else 0)
    self.assertEqual(out['uncertain_changes'],['a'] if 'uncertain' in (old,new) else [])
 def test_resolved_uncertainty(self):
  out=compare_versions(req([c('a'),c('b')]),ev({'a':'fail','b':'uncertain'}),ev({'a':'pass','b':'pass'}))
  self.assertEqual(out['G'],3);self.assertEqual(out['recommendation'],'建议查看新版')
 def test_ancestor_and_tie_break(self):
  r=req([c('a'),c('b',deps=['a']),c('c',deps=['b'])]);a,d=rank_actions(r,ev({'a':'fail','b':'pass','c':'fail'})['checks'],['c'])
  self.assertFalse(a);self.assertTrue(d)
  a,_=rank_actions(req([c('z'),c('a')]),ev({'z':'fail','a':'fail'})['checks'],['z','a']);self.assertEqual([x['id'] for x in a],['a','z'])
 def test_multiple_details_are_not_conflicts(self):
  self.assertFalse(validate_constraints([c('a','招牌','shop'),c('b','书架','shop')])['conflicts'])
 def test_invalid_checks_not_ranked(self):
  with self.assertRaises(ValueError):rank_actions(req([c('a')]),[],['a'])
class PipelineAudit(test_workflow.Flow):
 def test_correction_invalidates_plan_before_charge(self):
  self.generate();p=self.w.plan(self.id,['a']);self.w.correct(self.id,'a','pass','AI看错了')
  with self.assertRaises(ValueError):self.w.execute(self.id,'stale',p['plan_id'])
  self.assertEqual(self.w.store.load(self.id)['revision_attempts'],0)
 def test_real_workflow_calls_both_math_functions(self):
  self.generate()
  with patch('core.engine.rank_actions',wraps=rank_actions) as rank:
   p=self.w.plan(self.id,['a']);rank.assert_called_once()
   self.assertAlmostEqual(p['ranking'][0]['utility'],1.7)
  t=self.w.execute(self.id,'candidate',p['plan_id']);candidate=t['images'][-1]['image_id']
  with patch('core.engine.compare_versions',wraps=compare_versions) as compare:
   t=self.w.execute(self.id,'evaluate_candidate',evaluate_only=candidate);compare.assert_called_once()
   self.assertEqual((t['comparisons'][-1]['G'],t['comparisons'][-1]['R']),(3,3))
 def test_reevaluate_old_mock_image_uses_old_index(self):
  old=self.generate();p=self.w.plan(self.id,['a']);self.w.execute(self.id,'candidate',p['plan_id'])
  t=self.w.execute(self.id,'old_recheck',evaluate_only=old)
  self.assertEqual(self.w.evaluation(t,old)['checks'][0]['status'],'fail')
