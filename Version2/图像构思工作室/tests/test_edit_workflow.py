import tempfile,unittest
from unittest.mock import patch
from core.engine import Workflow
from adapters.mock import MockAdapter
from test_workflow import c
class EditingMock(MockAdapter):
 supports_edit=True
 def __init__(self):self.received=[];self.fail=False
 def edit(self,prompt,req,references):
  self.received.append((prompt,references))
  if self.fail:raise RuntimeError('edit failed')
  data,meta=MockAdapter.generate(self,prompt,req,1);meta['operation']='image_edit';return data,meta
class EditWorkflow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.adapter=EditingMock();self.w=Workflow(self.tmp.name,self.adapter);self.tid=self.w.create('bookshop')['task_id'];self.w.confirm(self.tid,[c('a'),c('b')],{})
  t=self.w.execute(self.tid,'v0');self.base=t['images'][0];self.w.execute(self.tid,'e0',evaluate_only=self.base['image_id'])
 def tearDown(self):self.tmp.cleanup()
 def test_edit_uses_selected_base_and_instructions(self):
  self.w.correct(self.tid,'a','fail','move closer to wall');p=self.w.plan(self.tid,['a'])
  self.assertEqual(p['operation'],'image_edit')
  with patch.object(self.adapter,'generate') as generate:
   t=self.w.execute(self.tid,'v1',p['plan_id']);generate.assert_not_called()
   self.w.select(self.tid,self.base['image_id']);p=self.w.plan(self.tid,['a']);self.w.execute(self.tid,'v2',p['plan_id']);generate.assert_not_called()
  for prompt,refs in self.adapter.received:
   self.assertEqual(refs[0]['image_id'],self.base['image_id']);self.assertTrue(refs[0]['path'].is_file());self.assertIn('move closer to wall',prompt)
  self.assertEqual(t['images'][-1]['operation'],'image_edit');self.assertEqual(t['selected_image_id'],self.base['image_id'])
 def test_failure_counts_once_and_does_not_fallback(self):
  p=self.w.plan(self.tid,['a']);self.adapter.fail=True
  with patch.object(self.adapter,'generate') as generate:
   with self.assertRaises(RuntimeError):self.w.execute(self.tid,'failure',p['plan_id'])
   self.w.execute(self.tid,'failure',p['plan_id']);generate.assert_not_called()
  t=self.w.store.load(self.tid);self.assertEqual(t['revision_attempts'],1);self.assertEqual(len(t['images']),1);self.assertEqual(len(self.adapter.received),1)
