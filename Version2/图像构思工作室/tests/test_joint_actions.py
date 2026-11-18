import unittest
import test_workflow
from test_workflow import c,req,ev
from core.engine import rank_actions
class JointMath(unittest.TestCase):
 def test_risk_is_union_cost_once(self):
  r=req([c('a',entity='same'),c('b',entity='same'),c('p',entity='same')])
  actions,_=rank_actions(r,ev({'a':'fail','b':'fail','p':'pass'})['checks'],['a','b'],grouped=True)
  a=actions[0];self.assertEqual(a['target_ids'],['a','b']);self.assertAlmostEqual(a['gain'],3.6);self.assertEqual(a['risk'],1.5);self.assertEqual(a['cost'],.1);self.assertAlmostEqual(a['utility'],2.0)
 def test_joint_dependencies(self):
  r=req([c('a'),c('b',deps=['a'])]);checks=ev({'a':'fail','b':'fail'})['checks']
  actions,_=rank_actions(r,checks,['a','b'],grouped=True);self.assertEqual(actions[0]['target_ids'],['a','b'])
  actions,deferred=rank_actions(r,checks,['b'],grouped=True);self.assertEqual(actions,[]);self.assertTrue(deferred)
class JointWorkflow(test_workflow.Flow):
 def test_both_targets_reach_image_request(self):
  from unittest.mock import patch
  self.generate();self.w.correct(self.id,'b','fail','第二项也有问题')
  p=self.w.plan(self.id,['a','b'],True);self.assertEqual(p['target_ids'],['a','b']);self.assertEqual(p['preserve_ids'],[])
  with patch.object(self.w.adapter,'generate',wraps=self.w.adapter.generate) as draw:
   t=self.w.execute(self.id,'joint',p['plan_id'])
   prompt=draw.call_args.args[0];self.assertIn('本轮共同修正：a: x；b: x',prompt);self.assertIn('第二项也有问题',prompt)
   self.assertEqual(draw.call_count,1);self.assertEqual(t['revision_attempts'],1)
