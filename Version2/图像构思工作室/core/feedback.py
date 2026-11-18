"""Reviewable model interpretation of feedback, separate from applying user intent."""
import copy,json,re
from core.engine import obj,uid,now,checklist,evaluation_corrections,effective_checks

SYSTEM='''你负责区分图像创作的用户反馈，不生成图片，也不计算分数。仅返回JSON：
{"intent":"correction|change|mixed|clarify","explanation":"解释","question":"不确定时询问","corrections":[{"constraint_id":"已有ID","observation":"图像没有做到原要求的具体描述"}],"changes":[{"constraint_id":"已有ID或null","label":"维度名称","type":"detail等","entity_id":"实体ID","value":"新的完整目标值","reason":"修改理由"}]}
correction：用户仍想要原来目标，仅指出当前图片没有做到。changes必须为空。
change：用户要替换目标、增加内容或改变偏好；不要还把新目标当成旧目标的不满足。替换字段用其原ID，新内容用null。变化相关的旧要求也须一起提出更新，避免新旧指令冲突。
mixed：独立维度分别纠正图片和改变要求；同一ID不要同时放两组。
clarify：无法判断是在描述现状还是表达新目标，例如只说“其实是暖黄灯”且上下文不明。提出一句选择题，两组为空，不擅自更新。
已有目标“冷白光”：反馈“图片现在偏黄，请恢复冷白”=>correction；“改为暖黄光，墙壁也换黄色”=>change；“其实是暖黄灯”=>clarify。
forced_intent若为correction/change，是用户明确选择，按该意思理解；无法提取完整目标仍clarify。
changes.value只写想要的完整值，不写观察/否定旧目标/编辑指令；例如“暖黄光与暗木色”。不得把用户未提到的偏好塞入目标。不改数量、人物、风格等无关项。
请基于整个confirmed_requirements检查关联项。type仅subject,scene,style,composition,lighting,detail,quantity,existence。新增单值维度使用独立entity_id。不要虚构ID。'''


def validate_proposal(raw,req,forced='auto'):
    if isinstance(raw,str):raw=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()))
    if not isinstance(raw,dict) or raw.get('intent') not in ('correction','change','mixed','clarify'):raise ValueError('反馈解析结构无效，请重新分析')
    cs={c['id']:c for c in checklist(req)};corrections=raw.get('corrections');changes=raw.get('changes')
    if not isinstance(corrections,list) or not isinstance(changes,list) or len(corrections)+len(changes)>64:raise ValueError('反馈操作列表无效')
    seen=set()
    for item in corrections:
        k=item.get('constraint_id')
        if k not in cs or k in seen or not isinstance(item.get('observation'),str) or not item['observation'].strip():raise ValueError('纠正项缺少有效目标或说明')
        seen.add(k)
    for item in changes:
        k=item.get('constraint_id')
        if k is not None and (k not in cs or k in seen):raise ValueError('修改目标引用无效或重复')
        if not isinstance(item.get('value'),str) or not item['value'].strip():raise ValueError('新目标不能为空')
        if k is not None:
            seen.add(k)
            if item['value'].strip()==str(cs[k]['value']).strip():raise ValueError('新目标与原值相同，请说明要纠正图片还是改变目标')
        elif any(not isinstance(item.get(f),str) or not item[f].strip() for f in ('label','type','entity_id')):raise ValueError('新增目标结构不完整')
        if k is None and item['type'] not in ('subject','scene','style','composition','lighting','detail','quantity','existence'):raise ValueError('新增目标类型无效')
    intent=raw['intent']
    if intent=='clarify':
        if corrections or changes or not raw.get('question'):raise ValueError('需要澄清的反馈不能带待执行修改')
    elif intent=='correction' and (not corrections or changes):raise ValueError('纠正图片不应修改目标')
    elif intent=='change' and (not changes or corrections):raise ValueError('改变目标的反馈结构无效')
    elif intent=='mixed' and (not changes or not corrections):raise ValueError('混合反馈结构无效')
    if forced in ('change','correction') and intent not in (forced,'clarify'):raise ValueError('AI 解释与您选定的修改方式不一致，请重新分析')
    return raw


def analyze_feedback(engine,tid,note,cid=None,forced='auto'):
    if not note.strip():raise ValueError('请先填写修改意见')
    if forced not in ('auto','correction','change'):raise ValueError('请选择有效的修改方式')
    with engine.store.lock:
        t=engine.store.load(tid);engine.idle(t);req=engine.req(t)
        if not t['selected_image_id']:raise ValueError('请先生成并选择一张图片')
        if cid and cid not in {c['id'] for c in checklist(req)}:raise ValueError('修改项已变化，请重新选择')
        if len(t['attempts'])>=t['operation_limit']:raise ValueError('已达到调用上限')
        e=engine.evaluation(t,t['selected_image_id']);snapshot=[c['correction_id'] for c in evaluation_corrections(t,e)]
        attempt=obj(attempt_id=uid(),request_id=uid(),kind='feedback_intent',state='running',started_at=now(),finished_at=None,latency=None,usage=None,error=None)
        t['attempts'].append(attempt);engine.store.save(t)
        context=dict(feedback=note,selected_constraint_id=cid,forced_intent=forced,confirmed_requirements=[{k:c[k] for k in ('id','description','value','type','entity_id','strength')} for c in checklist(req)])
    try:
        raw=engine.adapter.analyze_feedback(context)
        proposal=validate_proposal(raw,req,forced)
    except Exception:
        with engine.store.lock:
            t=engine.store.load(tid);a=next(a for a in t['attempts'] if a['attempt_id']==attempt['attempt_id']);a.update(state='failed',finished_at=now(),error='反馈分析未完成或返回结构无效，请重试；尚未改变目标');engine.store.save(t)
        raise ValueError('反馈分析未完成或返回结构无效，请重试。尚未改变目标或图片。') from None
    with engine.store.lock:
        current=engine.store.load(tid)
        p=obj(proposal_id=uid(),requirement_id=req['requirement_id'],image_id=t['selected_image_id'],evaluation_id=e['evaluation_id'] if e else None,correction_ids=snapshot,feedback=note,forced_intent=forced,interpretation=proposal,applied=False,created_at=now())
        current.setdefault('feedback_proposals',[]).append(p)
        a=next(a for a in current['attempts'] if a['attempt_id']==attempt['attempt_id']);a.update(state='succeeded',finished_at=now());engine.store.save(current)
    return p


def apply_feedback(engine,tid,pid):
    with engine.store.lock:
        t=engine.store.load(tid);engine.idle(t)
        p=next((p for p in t.get('feedback_proposals',[]) if p['proposal_id']==pid),None)
        if not p:raise ValueError('请先分析修改意见')
        if p['applied']:return p
        req=engine.req(t);e=engine.evaluation(t,t['selected_image_id'])
        if (p['requirement_id'],p['image_id'],p['evaluation_id'],p['correction_ids'])!=(req['requirement_id'],t['selected_image_id'],e['evaluation_id'] if e else None,[c['correction_id'] for c in evaluation_corrections(t,e)]):raise ValueError('目标、图片或判断已变化，请重新分析反馈')
        intent=p['interpretation']
        if intent['intent']=='clarify':raise ValueError('请先明确是纠正图片还是改变目标')
        if not intent['changes'] and not e:raise ValueError('请先按当前目标检查图片')
        if intent['changes']:
            if t['revision_attempts']>=2:raise ValueError('本任务修改机会已用完，请新建任务使用新目标')
            cs=copy.deepcopy(req['constraints']);by_id={c['id']:c for c in cs};changed=[]
            for item in intent['changes']:
                k=item['constraint_id']
                if k is None:
                    k=uid();c=obj(id=k,entity_id=item['entity_id'],type=item['type'],description=item['label'],value=item['value'].strip(),source='user_choice',origin='user_choice',status='confirmed',strength='must',locked=False,depends_on=[],options=[],question='');cs.append(c);old=None
                else:
                    c=by_id[k]
                    if c['locked']:raise ValueError('目标已锁定，请先在需求编辑中解锁：'+c['description'])
                    old=c['value'];c.update(value=item['value'].strip(),source='user_choice',status='confirmed')
                changed.append(dict(constraint_id=k,label=c['description'],old=old,new=c['value']))
            if len(cs)>64:raise ValueError('最多64项要求，请先合并内容')
            params=copy.deepcopy(req['params'])
            for key in ('revision_guidance','reference_ids','base_reference_id'):params.pop(key,None)
            params['feedback_change']={'proposal_id':pid,'base_image_id':p['image_id'],'changes':changed,'pending_corrections':intent['corrections']}
            summary='当前已确认目标：'+'；'.join(c['description']+': '+str(c['value']) for c in checklist({'constraints':cs}))
            t=engine.confirm(tid,cs,params,summary=summary)
            t['draft']={'schema_version':1,'summary':'已按修改意见更新目标','constraints':cs}
            t.setdefault('review_ui',{})[p['image_id']]={'selected':[]}
        else:
            for c in intent['corrections']:engine.correct(tid,c['constraint_id'],'fail',c['observation'])
            t=engine.store.load(tid)
        p=next(p for p in t['feedback_proposals'] if p['proposal_id']==pid);p.update(applied=True,applied_requirement_id=t['active_requirement_id'],applied_at=now())
        engine.store.save(t)
        if not intent['changes']:select_feedback_targets(engine,tid,[c['constraint_id'] for c in intent['corrections']])
        return p


def select_feedback_targets(engine,tid,ids):
    with engine.store.lock:
        t=engine.store.load(tid);e=engine.evaluation(t,t['selected_image_id'])
        if not e:return
        states={c['constraint_id']:c['status'] for c in effective_checks(e['checks'],evaluation_corrections(t,e))}
        view=t.setdefault('review_ui',{}).setdefault(t['selected_image_id'],{})
        view['selected']=list(dict.fromkeys([k for k in view.get('selected',[]) if states.get(k)=='fail']+[k for k in ids if states.get(k)=='fail']))
        engine.store.save(t)


def recheck_feedback(engine,tid):
    t=engine.store.load(tid);req=engine.req(t);base=t['selected_image_id']
    if not base:raise ValueError('请先选择图片')
    t=engine.execute(tid,uid(),evaluate_only=base,rebaseline=True)
    change=req['params'].get('feedback_change',{})
    if change.get('base_image_id')==base:
        if not change.get('corrections_applied'):
            for c in change.get('pending_corrections',[]):engine.correct(tid,c['constraint_id'],'fail',c['observation'])
            with engine.store.lock:
                current=engine.store.load(tid);engine.req(current)['params']['feedback_change']['corrections_applied']=True;engine.store.save(current)
        ids=[c['constraint_id'] for c in change.get('changes',[])]+[c['constraint_id'] for c in change.get('pending_corrections',[])]
        select_feedback_targets(engine,tid,ids)
    return engine.store.load(tid)
