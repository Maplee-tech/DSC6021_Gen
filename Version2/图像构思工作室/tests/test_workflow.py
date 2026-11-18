import unittest,tempfile,zipfile,json
from core.engine import *
from adapters.mock import MockAdapter

def c(k,value='x',entity=None,typ='detail',strength='must',deps=()):return obj(id=k,entity_id=entity or k,type=typ,description=k,value=value,source='user_input',status='confirmed',strength=strength,locked=False,depends_on=list(deps))
def req(cs):return dict(requirement_id='r',constraints=cs)
def ev(states):return dict(image_id=uid(),requirement_id='r',rubric_version='1',checks=[dict(constraint_id=k,status=v,evidence='fixture') for k,v in states.items()])
class Algorithms(unittest.TestCase):
 def test_graph(self):
  self.assertTrue(validate_constraints([c('a',2,'person','quantity'),c('b',3,'person','quantity')])['conflicts'])
  self.assertFalse(validate_constraints([c('a',2,'customer','quantity'),c('b',3,'staff','quantity')])['conflicts'])
  self.assertTrue(validate_constraints([c('a',deps=['z'])])['invalid_refs'])
  self.assertEqual(validate_constraints([c('a',deps=['b']),c('b',deps=['a'])])['cycles'],['a','b'])
  self.assertEqual(validate_constraints([c('a'),c('b',deps=['a'])])['dependency_order'],['a','b'])
 def test_formula_u(self):
  r=req([c('a',entity='scene',typ='scene'),c('b'),c('c',strength='preference')]); checks=ev({'a':'fail','b':'pass','c':'pass'})['checks']
  actions,_=rank_actions(r,checks,['a']); a=actions[0]
  self.assertAlmostEqual(a['utility'],3*.6-.5*(3+1)-.1)
  corrected,_=rank_actions(r,checks,['a'],[{'constraint_id':'a','corrected_status':'fail'}]); self.assertAlmostEqual(corrected[0]['utility'],3-2-.1)
  self.assertEqual(rank_actions(r,checks,['a'],[{'constraint_id':'a','corrected_status':'pass'}])[0],[])
 def test_dependencies(self):
  r=req([c('a'),c('b',deps=['a']),c('z')]); actions,deferred=rank_actions(r,ev({'a':'fail','b':'fail','z':'uncertain'})['checks'],['a','b','z'])
  self.assertEqual([a['id'] for a in actions],['a']); self.assertTrue(deferred)
 def test_compare(self):
  r=req([c('a'),c('b',strength='preference'),c('c')]); a=ev({'a':'fail','b':'pass','c':'pass'}); b=ev({'a':'pass','b':'fail','c':'uncertain'}); out=compare_versions(r,a,b)
  self.assertEqual((out['G'],out['R']),(3,1)); self.assertEqual(out['uncertain_changes'],['c']); self.assertEqual(out['recommendation'],'需人工权衡')
  b['requirement_id']='other'
  with self.assertRaises(ValueError):compare_versions(r,a,b)
 def test_validation(self):
  with self.assertRaises(ValueError):validate_checks([],req([c('a')]))
  with self.assertRaises(ValueError):validate_checks([{'constraint_id':'a','status':'pass','evidence':''}],req([c('a')]))
class Flow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.w=Workflow(self.tmp.name,MockAdapter()); self.t=self.w.create('bookshop'); self.id=self.t['task_id']; self.w.confirm(self.id,[c('a'),c('b')],{'mock_scenario':'mixed'})
 def tearDown(self):self.tmp.cleanup()
 def generate(self):
  t=self.w.execute(self.id,'first'); i=t['images'][0]['image_id']; self.w.execute(self.id,'eval',evaluate_only=i); return i
 def test_full_and_budget(self):
  first=self.generate(); plan=self.w.plan(self.id,['a']); t=self.w.execute(self.id,'revision',plan['plan_id']); candidate=t['images'][-1]['image_id']; t=self.w.execute(self.id,'eval2',evaluate_only=candidate)
  self.assertEqual(t['selected_image_id'],first); self.assertEqual(t['comparisons'][0]['G'],3); self.assertEqual(t['comparisons'][0]['R'],3)
  self.w.execute(self.id,'revision',plan['plan_id']); self.assertEqual(self.w.store.load(self.id)['revision_attempts'],1)
  self.w.select(self.id,first); plan=self.w.plan(self.id,['a']); t=self.w.execute(self.id,'revision2',plan['plan_id']); self.assertEqual(t['images'][-1]['parent_image_id'],first)
  with self.assertRaises(ValueError):self.w.execute(self.id,'revision3',plan['plan_id'])
  path=self.w.export(self.id,4)
  with zipfile.ZipFile(path) as z:self.assertEqual(z.read('prompt.txt').decode(),t['images'][0]['actual_prompt'])
 def test_bad_eval_keeps_image(self):
  t=self.w.store.load(self.id); t['requirements'][0]['params']['mock_scenario']='invalid'; self.w.store.save(t); t=self.w.execute(self.id,'first'); iid=t['images'][0]['image_id']
  with self.assertRaises(ValueError):self.w.execute(self.id,'eval',evaluate_only=iid)
  t=self.w.store.load(self.id); self.assertEqual(len(t['images']),1); self.assertEqual(t['evaluations'],[])
 def test_failed_and_restart(self):
  first=self.generate(); p=self.w.plan(self.id,['a'])
  def fail(*args):raise RuntimeError('simulated timeout')
  self.w.adapter.generate=fail
  with self.assertRaises(RuntimeError):self.w.execute(self.id,'bad',p['plan_id'])
  t=self.w.store.load(self.id); self.assertEqual(t['revision_attempts'],1); self.assertEqual(t['selected_image_id'],first)
  t['attempts'][-1]['state']='running'; self.w.store.save(t); w=Workflow(self.tmp.name,MockAdapter()); self.assertEqual(w.store.load(self.id)['attempts'][-1]['state'],'unknown')
if __name__=='__main__':unittest.main()
