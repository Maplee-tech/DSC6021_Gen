import tempfile,unittest
from unittest.mock import patch
from core.engine import Workflow
from test_edit_workflow import EditingMock
from test_workflow import c

class SupplementDisplay(unittest.TestCase):
 def setUp(self):
  import ui
  self.ui=ui;self.tmp=tempfile.TemporaryDirectory();self.w=Workflow(self.tmp.name,EditingMock());self.p=patch.object(ui,'engine',self.w);self.p.start()
  self.tid=self.w.create('lecture hall')['task_id'];self.w.confirm(self.tid,[c('a'),c('b')],{})
  self.w.execute(self.tid,'v0');t=self.w.store.load(self.tid);self.w.execute(self.tid,'e0',evaluate_only=t['selected_image_id'])
  self.w.correct(self.tid,'a','fail','上一轮的优化说明');plan=self.w.plan(self.tid,['a'],True);t=self.w.execute(self.tid,'v1',plan['plan_id']);self.v1=t['images'][-1]['image_id'];self.w.execute(self.tid,'e1',evaluate_only=self.v1);self.w.select(self.tid,self.v1)
 def tearDown(self):self.p.stop();self.tmp.cleanup()
 def test_saved_content_is_displayed_after_refresh_and_restored(self):
  self.ui.add_supplement(self.tid,'后排增加一层环形看台')
  r=self.ui.refresh(self.tid)
  self.assertIn('后排增加一层环形看台',r[-3]);self.assertIn('V1',r[-3]);self.assertTrue(r[-2]['interactive']);self.assertIn('上一轮的优化说明',r[-1])
  self.assertIn(self.ui.supplement_view(self.w.store.load(self.tid))[0],r[-3]);self.assertIn('重新检查',r[-3])
 def test_added_content_sent_with_v1_reference_no_cross_rubric_comparison(self):
  self.ui.add_supplement(self.tid,'后排增加一层环形看台');before=len(self.w.store.load(self.tid)['comparisons'])
  self.ui.run(self.tid,'v2')
  prompt,refs=self.w.adapter.received[-1];self.assertIn('后排增加一层环形看台',prompt);self.assertEqual(refs[0]['image_id'],self.v1)
  t=self.w.store.load(self.tid);self.assertEqual(len(t['comparisons']),before+1);self.assertEqual(t['comparisons'][-1]['requirement_id'],t['active_requirement_id']);self.assertFalse(self.ui.refresh(self.tid)[-2]['interactive'])
 def test_empty_supplement_does_not_add_requirement(self):
  before=len(self.w.store.load(self.tid)['requirements'])
  with self.assertRaises(Exception):self.ui.add_supplement(self.tid,'  ')
  self.assertEqual(len(self.w.store.load(self.tid)['requirements']),before)
