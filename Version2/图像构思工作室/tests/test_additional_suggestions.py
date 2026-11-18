import copy,tempfile,unittest
from unittest.mock import patch
from core.intent import validate_draft,validate_suggestions,extract_task,is_original,is_suggestion
from core.engine import Workflow
from adapters.mock import MockAdapter

class AdditionalSuggestions(unittest.TestCase):
    def fixture(self,n=15,original=7):
        fs=[dict(id='o'+str(i),entity_id='o'+str(i),type='detail',label='原文'+str(i),value='讲堂',source='user_input',evidence='讲堂',strength='must',options=[],question='',depends_on=[]) for i in range(original)]
        fs += [dict(id='s'+str(i),entity_id='s'+str(i),type='detail',label='新增'+str(i),value='A'+str(i),source='model_suggestion',strength='preference',options=['A'+str(i),'B'+str(i),'C'+str(i)],question='问题'+str(i),depends_on=[]) for i in range(n)]
        return dict(summary='AI 分析',fields=fs)
    def draft(self,n=15,original=7):return validate_draft(self.fixture(n,original),'大学讲堂')
    def test_15_extra_not_15_total_and_can_exceed_20(self):
        d=validate_suggestions(self.draft());self.assertEqual(len(d['constraints']),22)
        self.assertEqual(sum(is_original(c) for c in d['constraints']),7)
        self.assertEqual(sum(is_suggestion(c) for c in d['constraints']),15)
    def test_reject_originals_counted_in_total(self):
        with self.assertRaisesRegex(ValueError,'8 项新增建议'):validate_suggestions(self.draft(8))
    def test_reject_duplicate_dimension_and_options(self):
        d=self.draft();d['constraints'][-1]['description']=d['constraints'][-2]['description']
        with self.assertRaisesRegex(ValueError,'重复'):validate_suggestions(d)
        d=self.draft();d['constraints'][-1]['options']=['相同']*3
        with self.assertRaisesRegex(ValueError,'ABC'):validate_suggestions(d)
    def test_empty_pending_value_uses_model_option_without_accepting(self):
        f=self.fixture();f['fields'][-1]['value']=''
        d=validate_suggestions(validate_draft(f,'大学讲堂'))
        self.assertEqual(d['constraints'][-1]['value'],'A14')
        self.assertEqual(d['constraints'][-1]['status'],'pending')
    def test_suggestion_citing_input_does_not_become_original(self):
        c=self.draft()['constraints'][-1];c['evidence']='讲堂'
        self.assertFalse(is_original(c));self.assertTrue(is_suggestion(c))
    def test_edit_preserves_origin(self):
        d=self.draft();c=d['constraints'][0];c['source']='user_choice';self.assertTrue(is_original(c))
        c=d['constraints'][-1];c['source']='user_choice';self.assertTrue(is_suggestion(c))
    def test_all_choices_reach_prompt_and_original_is_kept(self):
        import ui
        with tempfile.TemporaryDirectory() as root,patch.object(ui,'engine',Workflow(root,MockAdapter())):
            tid=ui.engine.create('大学讲堂')['task_id'];cs=self.draft()['constraints']
            values=[None,'']*7+['A','']*15+[None,'']*(64-22)
            values[42:44]=['D','自定义画面细节']
            result=ui.apply_cards(tid,cs,'',*values)
            self.assertEqual(len([c for c in result[0] if c['status']=='confirmed']),22)
            preview,_=ui.confirm_cards(tid,result[2],'3:2','mixed')
            self.assertIn('自定义画面细节',preview)
            self.assertEqual(len(ui.engine.store.load(tid)['prompts'][-1]['constraint_ids']),22)
    def test_loading_failure_and_retry_are_persistent_and_redacted(self):
        import ui
        with tempfile.TemporaryDirectory() as root,patch.object(ui,'engine',Workflow(root,MockAdapter())):
            with patch.object(ui.engine.adapter,'extract',side_effect=RuntimeError('secret-api-key')):
                frames=list(ui.new_analysis('大学讲堂'))
            self.assertIn('data-analysis-state="loading"',frames[0][-3])
            self.assertIn('data-analysis-state="error"',frames[-1][-3])
            self.assertNotIn('secret-api-key',str(frames))
            tid=frames[-1][0];self.assertTrue(frames[-1][-2]['interactive'])
            with patch.object(ui.engine.adapter,'extract',return_value=self.fixture()):
                retry=list(ui.retry_analysis(tid))
            self.assertEqual(retry[-1][0],tid)
            self.assertEqual(len(ui.engine.store.load(tid)['attempts']),2)
