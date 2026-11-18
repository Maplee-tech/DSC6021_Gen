import unittest,tempfile
from unittest.mock import patch
from core.intent import validate_draft,extract_task
from core.engine import Workflow
from adapters.mock import MockAdapter
from adapters.existing import ExistingProjectAdapter
class IntentTests(unittest.TestCase):
 def fixture(self):
  return {'summary':'草稿','fields':[{'id':'subject','entity_id':'shop','type':'subject','label':'主体','value':'书店','source':'user_input','evidence':'书店','strength':'must','options':[]},{'id':'scene','entity_id':'shop','type':'scene','label':'场景','value':'雨夜街区外景','source':'model_suggestion','strength':'preference','options':['雨夜街区外景','书店室内','室内外结合'],'question':'你更想表现哪种场景？'}]}
 def test_suggestions_not_confirmed(self):
  d=validate_draft(self.fixture(),'赛博朋克书店');self.assertEqual(d['constraints'][1]['status'],'pending');self.assertEqual(d['constraints'][1]['options'],self.fixture()['fields'][1]['options'])
 def test_no_fabricated_user_requirement(self):
  f=self.fixture();f['fields'][1].update(source='user_input',evidence='雨夜')
  with self.assertRaises(ValueError):validate_draft(f,'赛博朋克书店')
 def test_model_api_receives_original(self):
  adapter=ExistingProjectAdapter.__new__(ExistingProjectAdapter)
  with patch('legacy.app.config',return_value={'base':'https://example.test/v1','key':'test','model':'text-model'}),patch('legacy.app.post',return_value={'choices':[{'message':{'content':'{}'}}]}) as post:
   adapter.extract('赛博朋克书店');self.assertEqual(post.call_args.args[2]['messages'][1]['content'],'赛博朋克书店');self.assertTrue(post.call_args.args[0].endswith('/chat/completions'))
 def test_failure_saved_not_fallback(self):
  with tempfile.TemporaryDirectory() as root:
   w=Workflow(root,MockAdapter());t=w.create('书店')
   with patch.object(w.adapter,'extract',side_effect=RuntimeError('secret')):
    with self.assertRaises(ValueError):extract_task(w,t['task_id'])
   stored=w.store.load(t['task_id']);self.assertNotIn('draft',stored);self.assertEqual(stored['attempts'][0]['state'],'failed');self.assertNotIn('secret',stored['attempts'][0]['error'])
 def test_persistence_and_budget(self):
  with tempfile.TemporaryDirectory() as root:
   w=Workflow(root,MockAdapter());t=w.create('书店');extract_task(w,t['task_id']);saved=w.store.load(t['task_id']);self.assertEqual(saved['draft']['constraints'][1]['status'],'pending');self.assertEqual(len(saved['attempts']),1)
if __name__=='__main__':unittest.main()
