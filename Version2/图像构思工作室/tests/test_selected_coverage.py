import unittest,tempfile
from unittest.mock import patch
from core.engine import Workflow
from adapters.mock import MockAdapter
class SelectedCoverage(unittest.TestCase):
 def test_all_sixteen_selected_free_suggestions_reach_prompt_and_adapter(self):
  import ui
  with tempfile.TemporaryDirectory() as root,patch.object(ui,'engine',Workflow(root,MockAdapter())):
   tid=ui.engine.create('library')['task_id']
   cs=[dict(id=str(i),entity_id=str(i),type='detail',description='field'+str(i),value='option'+str(i),source='model_suggestion',status='pending',strength='free',locked=False,depends_on=[],options=['option'+str(i),'B'+str(i),'C'+str(i)]) for i in range(16)]
   values=['A','']*16+[None,'']*4
   values[28:30]=['D','custom desk']
   saved=ui.apply_cards(tid,cs,'',*values)
   self.assertEqual(sum(c['strength']=='preference' for c in saved[0]),16)
   preview,_=ui.confirm_cards(tid,saved[2],'3:2','mixed')
   t=ui.engine.store.load(tid);prompt=t['prompts'][-1]
   self.assertEqual(len(prompt['constraint_ids']),16)
   self.assertIn('custom desk',preview)
   with patch.object(ui.engine.adapter,'generate',wraps=ui.engine.adapter.generate) as generate:
    ui.engine.execute(tid,'coverage')
    actual=generate.call_args.args[0]
    for c in saved[0]:self.assertIn(c['value'],actual)
 def test_backend_rejects_silently_excluded_user_choice(self):
  with tempfile.TemporaryDirectory() as root:
   w=Workflow(root,MockAdapter());tid=w.create('idea')['task_id']
   c=dict(id='a',entity_id='a',type='detail',description='x',value='chosen',source='user_choice',status='confirmed',strength='free',locked=False,depends_on=[])
   with self.assertRaisesRegex(ValueError,'自由发挥'):w.confirm(tid,[c],{})
