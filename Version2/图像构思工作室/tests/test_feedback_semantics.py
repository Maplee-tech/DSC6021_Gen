import copy,tempfile,unittest
from unittest.mock import patch
from core.engine import Workflow,compare_versions,rank_actions,effective_checks,evaluation_corrections,checklist
from core.feedback import analyze_feedback,apply_feedback,recheck_feedback,validate_proposal
from test_edit_workflow import EditingMock
from test_workflow import c,req,ev

class FeedbackAdapter(EditingMock):
 def __init__(self):super().__init__();self.contexts=[];self.answer=None;self.evaluated=[]
 def analyze_feedback(self,context):self.contexts.append(context);return copy.deepcopy(self.answer)
 def evaluate(self,path,req,index):
  self.evaluated.append(copy.deepcopy(req))
  return [dict(constraint_id=c['id'],status='fail' if c['value']=='暖黄色' and index==0 else 'pass',evidence='可见画面') for c in checklist(req)]

def change():return dict(intent='change',explanation='用户想换颜色',question='',corrections=[],changes=[dict(constraint_id='color',value='暖黄色')])
def correction():return dict(intent='correction',explanation='原要求不变',question='',corrections=[dict(constraint_id='color',observation='请恢复冷白色')],changes=[])

class FeedbackSemantics(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.a=FeedbackAdapter();self.w=Workflow(self.tmp.name,self.a);self.tid=self.w.create('冷白色教室')['task_id']
  self.w.confirm(self.tid,[c('color','冷白色',typ='style',strength='preference'),c('people','两位学生')],{})
  t=self.w.execute(self.tid,'v0');self.base=t['selected_image_id'];self.w.execute(self.tid,'e0',evaluate_only=self.base)
 def tearDown(self):self.tmp.cleanup()
 def proposal(self,answer):self.a.answer=answer;return analyze_feedback(self.w,self.tid,'这次希望换一下颜色','color')
 def test_change_rebaseline_and_same_goal_comparison(self):
  initial=self.w.store.load(self.tid);oldreq=self.w.req(initial)['requirement_id'];olde=copy.deepcopy(initial['evaluations'])
  p=self.proposal(change());self.assertEqual(self.w.req(self.w.store.load(self.tid))['requirement_id'],oldreq)
  apply_feedback(self.w,self.tid,p['proposal_id']);t=self.w.store.load(self.tid);newreq=self.w.req(t)
  self.assertNotEqual(newreq['requirement_id'],oldreq);self.assertEqual(newreq['constraints'][0]['value'],'暖黄色')
  self.assertNotIn('冷白色',t['prompts'][-1]['text']);self.assertNotIn('冷白色',newreq['summary']);self.assertIsNone(self.w.evaluation(t,self.base))
  before=(len(t['attempts']),t['revision_attempts'])
  with self.assertRaisesRegex(ValueError,'重新检查'):self.w.execute(self.tid,'blocked')
  t=self.w.store.load(self.tid);self.assertEqual((len(t['attempts']),t['revision_attempts']),before)
  recheck_feedback(self.w,self.tid);p=self.w.plan(self.tid,['color'],True)
  self.assertEqual(p['effective_checks'][0]['status'],'fail');self.assertAlmostEqual(p['ranking'][0]['gain'],.6)
  t=self.w.execute(self.tid,'v1',p['plan_id']);new=t['images'][-1]['image_id'];t=self.w.execute(self.tid,'e1',evaluate_only=new)
  result=t['comparisons'][-1];self.assertEqual((result['G'],result['R']),(1,0));self.assertEqual(result['requirement_id'],newreq['requirement_id'])
  self.assertEqual(t['evaluations'][:1],olde);self.assertEqual(t['images'][0]['requirement_id'],oldreq)
  self.assertIn('暖黄色',self.a.received[-1][0]);self.assertEqual(self.a.received[-1][1][0]['image_id'],self.base)
 def test_correction_changes_judgment_not_goal_and_latest_wins(self):
  p=self.proposal(correction());before=self.w.req(self.w.store.load(self.tid))['requirement_id'];apply_feedback(self.w,self.tid,p['proposal_id'])
  t=self.w.store.load(self.tid);self.assertEqual(t['active_requirement_id'],before);self.assertEqual(t['evaluations'][0]['checks'][0]['status'],'pass')
  plan=self.w.plan(self.tid,['color'],True);self.assertEqual(plan['effective_checks'][0]['judgment_source'],'user');self.assertEqual(plan['ranking'][0]['gain'],1)
  t=self.w.execute(self.tid,'v1',plan['plan_id']);t=self.w.execute(self.tid,'e1',evaluate_only=t['images'][-1]['image_id'])
  self.assertEqual(t['comparisons'][-1]['G'],1)
  self.w.correct(self.tid,'color','pass','更正之前的判断');t=self.w.store.load(self.tid);self.assertEqual(t['comparisons'][-1]['G'],0);self.assertTrue(t['comparison_history'])
 def test_new_evaluation_does_not_inherit_corrections(self):
  p=self.proposal(correction());apply_feedback(self.w,self.tid,p['proposal_id']);t=recheck_feedback(self.w,self.tid)
  e=self.w.evaluation(t,self.base);self.assertEqual(evaluation_corrections(t,e),[]);self.assertEqual(e['checks'][0]['status'],'pass')
 def test_clarification_never_applied(self):
  p=self.proposal(dict(intent='clarify',explanation='',question='是描述现状，还是想改成暖黄？',corrections=[],changes=[]))
  with self.assertRaises(ValueError):apply_feedback(self.w,self.tid,p['proposal_id'])
  self.assertEqual(len(self.w.store.load(self.tid)['requirements']),1)
 def test_duplicate_confirmation_is_idempotent_and_stale_rejected(self):
  p=self.proposal(change());apply_feedback(self.w,self.tid,p['proposal_id']);apply_feedback(self.w,self.tid,p['proposal_id'])
  self.assertEqual(len(self.w.store.load(self.tid)['requirements']),2)
  recheck_feedback(self.w,self.tid);p=self.proposal(correction());self.w.correct(self.tid,'color','pass','新判断')
  with self.assertRaisesRegex(ValueError,'已变化'):apply_feedback(self.w,self.tid,p['proposal_id'])
 def test_goal_change_invalidates_old_plan_and_removes_old_guidance(self):
  self.w.correct(self.tid,'color','fail','冷白');oldplan=self.w.plan(self.tid,['color'],True)
  t=self.w.store.load(self.tid);self.w.req(t)['params']['revision_guidance']=['恢复冷白'];self.w.store.save(t)
  p=self.proposal(change());apply_feedback(self.w,self.tid,p['proposal_id']);recheck_feedback(self.w,self.tid)
  t=self.w.store.load(self.tid);self.assertNotIn('revision_guidance',self.w.req(t)['params'])
  with self.assertRaisesRegex(ValueError,'过期'):self.w.execute(self.tid,'old',oldplan['plan_id'])
  self.assertEqual(self.w.store.load(self.tid)['revision_attempts'],0)
 def test_mixed_corrections_applied_only_once_to_rebaseline(self):
  answer=change();answer['intent']='mixed';answer['corrections']=[dict(constraint_id='people',observation='只有一位学生')]
  p=self.proposal(answer);apply_feedback(self.w,self.tid,p['proposal_id']);t=recheck_feedback(self.w,self.tid)
  self.assertEqual(len(evaluation_corrections(t,self.w.evaluation(t,self.base))),1)
  t=recheck_feedback(self.w,self.tid);self.assertEqual(evaluation_corrections(t,self.w.evaluation(t,self.base)),[])
 def test_invalid_ai_output_and_locked_target_make_no_change(self):
  bad=change();bad['changes'][0]['constraint_id']='invented';self.a.answer=bad
  with self.assertRaises(ValueError):analyze_feedback(self.w,self.tid,'change')
  t=self.w.store.load(self.tid);self.assertEqual(t['attempts'][-1]['state'],'failed');self.assertEqual(len(t['requirements']),1)
  t['requirements'][0]['constraints'][0]['locked']=True;self.w.store.save(t);p=self.proposal(change())
  with self.assertRaisesRegex(ValueError,'锁定'):apply_feedback(self.w,self.tid,p['proposal_id'])
  self.assertEqual(len(self.w.store.load(self.tid)['requirements']),1)
 def test_addition_is_new_check_and_context_has_existing_goals(self):
  answer=change();answer['changes']=[dict(constraint_id=None,label='墙壁',type='detail',entity_id='wall',value='黄色墙壁')]
  p=self.proposal(answer);self.assertEqual(self.a.contexts[-1]['confirmed_requirements'][0]['value'],'冷白色')
  apply_feedback(self.w,self.tid,p['proposal_id']);t=self.w.store.load(self.tid);self.assertEqual(len(checklist(self.w.req(t))),3)
 def test_failed_recheck_keeps_goal_and_retry_is_safe(self):
  p=self.proposal(change());apply_feedback(self.w,self.tid,p['proposal_id'])
  with patch.object(self.a,'evaluate',side_effect=RuntimeError('test timeout')):
   with self.assertRaises(RuntimeError):recheck_feedback(self.w,self.tid)
  t=self.w.store.load(self.tid);self.assertEqual(self.w.req(t)['constraints'][0]['value'],'暖黄色');self.assertIsNone(self.w.evaluation(t,self.base));self.assertEqual(t['revision_attempts'],0)
  recheck_feedback(self.w,self.tid)

class UnifiedMath(unittest.TestCase):
 def test_user_judgments_drive_both_formulas_without_mutating_raw(self):
  r=req([c('color',strength='preference')]);a=ev({'color':'pass'});b=ev({'color':'fail'});raw=copy.deepcopy((a,b))
  ca=[dict(constraint_id='color',corrected_status='fail')];cb=[dict(constraint_id='color',corrected_status='pass')]
  rank,_=rank_actions(r,a['checks'],['color'],ca);out=compare_versions(r,a,b,ca,cb)
  self.assertEqual(rank[0]['gain'],1);self.assertEqual((out['G'],out['R']),(1,0));self.assertEqual((a,b),raw)
 def test_forced_meaning_and_duplicate_ids_are_validated(self):
  r=req([c('color')]);bad=change()
  with self.assertRaises(ValueError):validate_proposal(bad,r,'correction')
  bad['intent']='mixed';bad['corrections']=[dict(constraint_id='color',observation='bad')]
  with self.assertRaises(ValueError):validate_proposal(bad,r)

class FeedbackUI(unittest.TestCase):
 setUp=FeedbackSemantics.setUp
 tearDown=FeedbackSemantics.tearDown
 def test_ui_analysis_and_confirmation_update_labels_and_clear_old_comparison(self):
  import ui
  with patch.object(ui,'engine',self.w):
   self.a.answer=change();before=self.w.req(self.w.store.load(self.tid))['requirement_id']
   preview,pid,button=ui.interpret_note(self.tid,'color','改为暖黄色','auto')
   self.assertIn('冷白色 →',preview);self.assertTrue(button['interactive']);self.assertEqual(self.w.store.load(self.tid)['active_requirement_id'],before)
   out=ui.commit_feedback(self.tid,pid)
   self.assertIn('新目标与检查标准已保存',out[16]);self.assertIn('暖黄色',out[-1]);self.assertIn('旧目标的结果不会计入',out[9])
   self.assertEqual(out[7]['value'],['color']);self.assertEqual(out[19],'')
 def test_ui_all_pass_after_changed_goal_does_not_claim_more_work_needed(self):
  import ui
  with patch.object(ui,'engine',self.w):
   self.a.answer=change();_,pid,_=ui.interpret_note(self.tid,'color','改为暖黄色','auto')
   with patch.object(self.a,'evaluate',side_effect=lambda p,r,i:[dict(constraint_id=c['id'],status='pass',evidence='已符合') for c in checklist(r)]):
    out=ui.commit_feedback(self.tid,pid)
   self.assertIn('无需再生成',out[16]);self.assertEqual(out[7]['value'],[])
