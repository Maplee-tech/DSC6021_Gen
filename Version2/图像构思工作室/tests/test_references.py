import os
from unittest.mock import patch
import test_workflow
from core.visual_preferences import prepare
class References(test_workflow.Flow):
 def test_reference_images_and_failure_no_fallback(self):
  first=self.generate();p=self.w.plan(self.id,['a']);t=self.w.execute(self.id,'v1',p['plan_id']);latest=t['images'][-1]
  with patch.dict(os.environ,{'REFERENCE_EDIT_URL':'https://example.test/edit','REFERENCE_EDIT_MODEL':'test','REFERENCE_EDIT_API_KEY':'test'}):
   preview=prepare(self.w,self.id,'V1',[['灯光','V1','暖色'],['空间感','V0','紧凑']]);self.assertIn('V0',preview)
   t=self.w.store.load(self.id);req=self.w.req(t)
   self.assertEqual(set(req['params']['reference_ids']),{first,latest['image_id']})
   old_count=len(t['images'])
   self.w.execute(self.id,'rebaseline',evaluate_only=t['selected_image_id'],rebaseline=True)
   with patch('adapters.reference.edit',side_effect=RuntimeError('timeout')) as edit,patch.object(self.w.adapter,'generate') as generate:
    with self.assertRaises(RuntimeError):self.w.execute(self.id,'reference')
    args=edit.call_args.args;self.assertEqual(len(args[2]),2);self.assertTrue(all(r['path'].is_file() for r in args[2]));generate.assert_not_called()
   t=self.w.store.load(self.id);self.assertEqual(t['revision_attempts'],2);self.assertEqual(len(t['images']),old_count)
 def test_no_implicit_capability(self):
  self.generate()
  with patch.dict(os.environ,{'REFERENCE_EDIT_URL':'','REFERENCE_EDIT_MODEL':'','REFERENCE_EDIT_API_KEY':''}):
   with self.assertRaisesRegex(ValueError,'尚未配置'):prepare(self.w,self.id,'V0',[['灯光','V0','冷光']])
