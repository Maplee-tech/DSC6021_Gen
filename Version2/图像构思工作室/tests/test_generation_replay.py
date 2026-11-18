import test_workflow
class ReplayTests(test_workflow.Flow):
 def test_failed_replay_has_no_index_error_and_no_second_call(self):
  from unittest.mock import patch
  with patch.object(self.w.adapter,'generate',side_effect=RuntimeError('timeout')) as generate:
   with self.assertRaises(RuntimeError):self.w.execute(self.id,'failed')
   t=self.w.execute(self.id,'failed')
   with self.assertRaisesRegex(ValueError,'上一次生成请求失败'):self.w.generated_image_for_request(t,'failed')
   self.assertEqual(generate.call_count,1)
  t=self.w.execute(self.id,'explicit-retry');self.assertEqual(len(t['images']),1)
  self.assertEqual(self.w.generated_image_for_request(t,'explicit-retry')['image_id'],t['images'][0]['image_id'])
 def test_replayed_initial_returns_its_image_not_latest(self):
  first=self.generate();p=self.w.plan(self.id,['a']);t=self.w.execute(self.id,'revision',p['plan_id'])
  self.assertEqual(self.w.generated_image_for_request(t,'first')['image_id'],first)
