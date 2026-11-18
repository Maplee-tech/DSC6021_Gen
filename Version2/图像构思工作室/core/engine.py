"""Local deterministic decision algorithms and durable workflow."""
import json, uuid, os, threading, hashlib, io, zipfile, time
from pathlib import Path
from datetime import datetime, timezone

def uid(): return uuid.uuid4().hex
def now(): return datetime.now(timezone.utc).isoformat()
def obj(**kw): return dict(schema_version=1, **kw)
CONFIG=json.loads((Path(__file__).resolve().parents[1]/'algorithm_config.json').read_text())
def weight(c): return CONFIG['weights'][c['strength']]

def validate_constraints(cs):
    ids={c['id'] for c in cs}; invalid=[]; conflicts=[]; order=[]
    edges={c['id']:set(c.get('depends_on',[])) for c in cs}
    for c in cs:
        invalid += [(c['id'],d) for d in edges[c['id']] if d not in ids]
    for i,a in enumerate(cs):
        for b in cs[i+1:]:
            if a['status']==b['status']=='confirmed' and a['strength']!='free' and b['strength']!='free' and a['type'] in ('quantity','existence','scene','subject') and (a['entity_id'],a['type'],a.get('scope',''))==(b['entity_id'],b['type'],b.get('scope','')) and a['value']!=b['value']:
                conflicts.append({'ids':[a['id'],b['id']],'reason':'同一实体的单值要求冲突'})
    pending={k:set(v)&ids for k,v in edges.items()}
    while pending:
        ready=sorted(k for k,v in pending.items() if not v)
        if not ready: break
        for k in ready: order.append(k); pending.pop(k)
        for v in pending.values(): v.difference_update(ready)
    return dict(conflicts=conflicts,invalid_refs=invalid,cycles=sorted(pending),dependency_order=order)

def checklist(req): return [c for c in req['constraints'] if c['status']=='confirmed' and c['strength']!='free']
def validate_checks(checks, req):
    expected={c['id'] for c in checklist(req)}
    if len(checks)!=len(expected) or {x.get('constraint_id') for x in checks}!=expected or any(x.get('status') not in ('pass','fail','uncertain') or not isinstance(x.get('evidence'),str) or not x['evidence'].strip() for x in checks):
        raise ValueError('评价格式不完整或存在重复、无效状态；图片已保留，可重试评价')
    return checks

def effective_checks(checks,corrections=()):
    """One judgment basis for planning and comparison; raw evidence stays immutable."""
    result={c['constraint_id']:dict(c,judgment_source='model') for c in checks}
    for correction in corrections:
        k=correction['constraint_id'];status=correction['corrected_status']
        if k not in result or status not in ('pass','fail','uncertain'):raise ValueError('用户纠错无效')
        result[k].update(status=status,judgment_source='user',correction_id=correction.get('correction_id'),user_reason=correction.get('reason',''))
    return list(result.values())

def evaluation_corrections(t,e):
    return [c for c in t['corrections'] if c['evaluation_id']==e['evaluation_id']] if e else []

def rank_actions(req, checks, allowed, corrections=(), lam=None, mu=None, grouped=False):
    lam=CONFIG['lambda'] if lam is None else lam; mu=CONFIG['mu'] if mu is None else mu
    validate_checks(checks,req)
    graph=validate_constraints(req['constraints'])
    if graph['conflicts'] or graph['invalid_refs'] or graph['cycles']: raise ValueError('需求图无效，不能排序修正动作')
    cs={c['id']:c for c in checklist(req)}; effective=effective_checks(checks,corrections)
    states={c['constraint_id']:c['status'] for c in effective};confirmed={c['constraint_id'] for c in effective if c['judgment_source']=='user'}
    all_cs={c['id']:c for c in req['constraints']}
    def ancestors(k):
        found=set(); todo=list(all_cs[k].get('depends_on',[]))
        while todo:
            d=todo.pop()
            if d in found:continue
            found.add(d); todo.extend(all_cs[d].get('depends_on',[]))
        return found
    ranked=[]; deferred=[]
    for k,c in cs.items():
        if k not in allowed or states[k]!='fail': continue
        if any(states.get(d)=='fail' for d in ancestors(k)):
            deferred.append(k+': 先处理前置条件'); continue
        affected=[j for j,v in cs.items() if states[j]=='pass' and (c['type'] in ('scene','style') or v['entity_id']==c['entity_id'] or k in v.get('depends_on',[]) or j in c.get('depends_on',[]))]
        gain=weight(c)*(CONFIG['e_user'] if k in confirmed else CONFIG['e_ai']); risk=lam*sum(weight(cs[j]) for j in affected)
        ranked.append(dict(id=k,utility=gain-risk-mu*CONFIG['cost_units'],gain=gain,risk=risk,cost=mu*CONFIG['cost_units'],affected=affected,target_ids=[k],benefit_terms=[{'constraint_id':k,'weight':weight(c),'e':CONFIG['e_user'] if k in confirmed else CONFIG['e_ai']}],risk_terms=[{'constraint_id':j,'weight':weight(cs[j])} for j in affected],cost_units=CONFIG['cost_units'],lambda_value=lam,mu_value=mu))
    if grouped:
        targets={k for k in allowed if k in cs and states[k]=='fail'}
        # A joint action can repair prerequisites and their dependents together.
        # A failed prerequisite outside the action must be resolved first.
        while True:
            blocked={k for k in targets if any(states.get(d)=='fail' and d not in targets for d in ancestors(k))}
            if not blocked:break
            targets-=blocked
        deferred=[k+': 先处理前置条件' for k in sorted(set(allowed)&set(cs)) if states[k]=='fail' and k not in targets]
        if not targets:return [],deferred
        targets=sorted(targets)
        affected=sorted({j for k in targets for j,v in cs.items() if states[j]=='pass' and (cs[k]['type'] in ('scene','style','composition') or v['entity_id']==cs[k]['entity_id'] or k in v.get('depends_on',[]) or j in cs[k].get('depends_on',[]))})
        benefit_terms=[{'constraint_id':k,'weight':weight(cs[k]),'e':CONFIG['e_user'] if k in confirmed else CONFIG['e_ai']} for k in targets]
        gain=sum(t['weight']*t['e'] for t in benefit_terms)
        risk=lam*sum(weight(cs[j]) for j in affected);cost=mu*CONFIG['cost_units']
        ranked=[dict(id=targets[0],target_ids=targets,utility=gain-risk-cost,gain=gain,risk=risk,cost=cost,affected=affected,benefit_terms=benefit_terms,risk_terms=[{'constraint_id':j,'weight':weight(cs[j])} for j in affected],cost_units=CONFIG['cost_units'],lambda_value=lam,mu_value=mu)]
    return sorted(ranked,key=lambda a:(-a['utility'],a['id'])),deferred

def compare_versions(req, a, b, corrections_a=(), corrections_b=()):
    if a['requirement_id']!=b['requirement_id'] or a['requirement_id']!=req['requirement_id'] or a['rubric_version']!=b['rubric_version']: raise ValueError('不同需求或评价标准不可直接比较')
    validate_checks(a['checks'],req); validate_checks(b['checks'],req)
    ea=effective_checks(a['checks'],corrections_a);eb=effective_checks(b['checks'],corrections_b)
    aa={c['constraint_id']:c['status'] for c in ea}; bb={c['constraint_id']:c['status'] for c in eb}
    fixed=[k for k in aa if (aa[k],bb[k])==('fail','pass')]; reg=[k for k in aa if (aa[k],bb[k])==('pass','fail')]; uncertain=[k for k in aa if 'uncertain' in (aa[k],bb[k])]
    cs={c['id']:c for c in checklist(req)}; g=sum(weight(cs[k]) for k in fixed); r=sum(weight(cs[k]) for k in reg)
    key_unknown=any(cs[k]['strength']=='must' and bb[k]=='uncertain' for k in uncertain)
    return obj(base_id=a['image_id'],candidate_id=b['image_id'],base_evaluation_id=a.get('evaluation_id'),candidate_evaluation_id=b.get('evaluation_id'),comparison_basis='统一有效判断：该次评价的最新用户纠错优先，否则使用模型判断',basis_version=2,base_effective_checks=ea,candidate_effective_checks=eb,base_correction_ids=[c.get('correction_id') for c in corrections_a],candidate_correction_ids=[c.get('correction_id') for c in corrections_b],requirement_id=req['requirement_id'],fixed_ids=fixed,regressed_ids=reg,uncertain_changes=uncertain,G=g,R=r,fixed_terms=[{'constraint_id':k,'weight':weight(cs[k])} for k in fixed],regressed_terms=[{'constraint_id':k,'weight':weight(cs[k])} for k in reg],potential_loss_ids=[k for k in aa if aa[k]=='pass' and bb[k]=='uncertain'],algorithm_config=json.loads(json.dumps(CONFIG)),recommendation='需人工权衡' if r or key_unknown else ('建议查看新版' if g else '无明确改善'),reasons=['自动检查仅供参考；不会自动切换所选版本'])

class NoRecommendedAction(ValueError):
    """A normal decision outcome, not an operation failure."""
    def __init__(self,reasons,ranking=()):
        self.reasons=reasons; self.ranking=list(ranking)
        super().__init__('\n'.join(reasons))

class Storage:
    def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.lock=threading.RLock()
    def folder(self,tid):
        if len(tid)!=32 or any(c not in '0123456789abcdef' for c in tid): raise ValueError('无效任务 ID')
        return self.root/tid
    def save(self,t):
        p=self.folder(t['task_id']); p.mkdir(exist_ok=True); tmp=p/'manifest.tmp'
        with tmp.open('w') as f: json.dump(t,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p/'manifest.json')
    def load(self,tid): return json.loads((self.folder(tid)/'manifest.json').read_text())
    def record(self,t,kind,value):
        p=self.folder(t['task_id'])/kind; p.mkdir(exist_ok=True)
        key=next((v for k,v in value.items() if k.endswith('_id')),uid())
        with (p/(key+'.json')).open('x') as f: json.dump(value,f,ensure_ascii=False,indent=2)
    def recover(self):
        for p in self.root.glob('*/manifest.json'):
            t=json.loads(p.read_text()); dirty=False
            for a in t['attempts']:
                if a['state']=='running': a.update(state='unknown',error='程序中断，结果未知；未自动重发'); dirty=True
            if dirty: t['state']='REVIEWING' if t['images'] else 'READY'; self.save(t)

class Workflow:
    def __init__(self,root,adapter): self.store=Storage(root); self.adapter=adapter; self.store.recover()
    def create(self,text):
        if not text.strip(): raise ValueError('请先输入想法')
        t=obj(task_id=uid(),original_input=text,state='CLARIFYING',active_requirement_id=None,selected_image_id=None,revision_attempts=0,operation_limit=12,created_at=now(),requirements=[],prompts=[],images=[],evaluations=[],corrections=[],plans=[],attempts=[],comparisons=[],satisfaction=[])
        self.store.save(t); return t
    def confirm(self,tid,cs,params,summary=None):
        with self.store.lock:
            t=self.store.load(tid); self.idle(t)
            if any(c['status']=='confirmed' and c['source']=='user_choice' and c['strength']=='free' for c in cs):raise ValueError('已选择的要求不能仍标为自由发挥，请重新确认卡片选择')
            g=validate_constraints(cs)
            if g['conflicts'] or g['invalid_refs'] or g['cycles']: raise ValueError('请解决约束问题：'+json.dumps(g,ensure_ascii=False))
            params=dict(params)
            if t['images']:params['requires_baseline_evaluation']=True
            req=obj(requirement_id=uid(),parent_id=t['active_requirement_id'],summary=summary or ('当前已确认目标：'+'；'.join(c['description']+': '+str(c['value']) for c in checklist({'constraints':cs})) if t['images'] else t['original_input']),constraints=cs,fields={},params=params,confirmed_at=now())
            if not checklist(req): raise ValueError('至少确认一项非自由要求')
            prompt=obj(prompt_id=uid(),requirement_id=req['requirement_id'],text='生成图像。\n'+'\n'.join('['+c['id']+'] '+c['description']+': '+str(c['value']) for c in checklist(req)),constraint_ids=[c['id'] for c in checklist(req)],coverage_warnings=[],confirmed_at=now())
            if params.get('revision_guidance'):prompt['text']+='\n已保存的逐项优化说明（不改变已确认要求）：\n'+'\n'.join(params['revision_guidance'])
            t['requirements'].append(req); t['prompts'].append(prompt); t.update(active_requirement_id=req['requirement_id'],state='READY'); self.store.record(t,'requirements',req); self.store.record(t,'prompts',prompt); self.store.save(t); return t
    def idle(self,t):
        if any(a['state']=='running' for a in t['attempts']): raise ValueError('当前任务正在执行，请等待')
        if t['state']=='DONE': raise ValueError('任务已结束，请创建新任务')
    def req(self,t): return next(r for r in t['requirements'] if r['requirement_id']==t['active_requirement_id'])
    def evaluation(self,t,i,requirement_id=None):
        rid=requirement_id or t['active_requirement_id']
        return next((e for e in reversed(t['evaluations']) if e['image_id']==i and e['requirement_id']==rid),None)
    def comparison_results(self,t):
        results=[]
        for image in t['images']:
            if not image['parent_image_id']:continue
            for req in t['requirements']:
                a=self.evaluation(t,image['parent_image_id'],req['requirement_id']);b=self.evaluation(t,image['image_id'],req['requirement_id'])
                if a and b:results.append(compare_versions(req,a,b,evaluation_corrections(t,a),evaluation_corrections(t,b)))
        return results
    def rebuild_comparisons(self,t):
        current=self.comparison_results(t)
        if current!=t['comparisons']:
            if t['comparisons']:t.setdefault('comparison_history',[]).append(obj(recorded_at=now(),comparisons=t['comparisons']))
            t['comparisons']=current

    def correct(self,tid,cid,status,reason):
        with self.store.lock:
            t=self.store.load(tid); self.idle(t); e=self.evaluation(t,t['selected_image_id'])
            if not e or cid not in {x['constraint_id'] for x in e['checks']}: raise ValueError('请选有效检查项')
            if status not in ('pass','fail','uncertain'): raise ValueError('无效纠错状态')
            t['corrections'].append(obj(correction_id=uid(),evaluation_id=e['evaluation_id'],constraint_id=cid,corrected_status=status,reason=reason,created_at=now())); self.rebuild_comparisons(t);self.store.save(t)
    def plan(self,tid,allowed,accept_risk=False):
        with self.store.lock:
            t=self.store.load(tid); self.idle(t); req=self.req(t); e=self.evaluation(t,t['selected_image_id'])
            if not e or e['requirement_id']!=req['requirement_id']: raise ValueError('所选图尚未按当前需求评价；请先按新目标重新检查当前图')
            corrections=[x for x in t['corrections'] if x['evaluation_id']==e['evaluation_id']]
            ranked,deferred=rank_actions(req,e['checks'],allowed,corrections,grouped=len(set(allowed))>1)
            eligible=[x for x in ranked if x['utility']>0 or accept_risk]
            if not eligible:
                states={x['constraint_id']:x['status'] for x in e['checks']}
                for correction in corrections:states[correction['constraint_id']]=correction['corrected_status']
                names={c['id']:c['description']+': '+str(c['value']) for c in checklist(req)}
                reasons=[]
                if not allowed: reasons.append('尚未选择修改项。请先勾选快捷修改清单，再计算计划。')
                for k in allowed:
                    if k not in states:reasons.append('所选检查项已失效，请刷新清单。')
                    elif states[k]=='pass':reasons.append(names[k]+'：当前判断为满足，不需要自动修正；若判断有误，请先保存“确认不满足”。')
                    elif states[k]=='uncertain':reasons.append(names[k]+'：当前判断不确定，系统不会据此自动修正；请先核实。')
                for message in deferred:
                    k=message.split(':',1)[0];reasons.append(names.get(k,k)+'：先处理未满足的前置条件。')
                for action in ranked:
                    reasons.append(names[action['id']]+f"：收益 {action['gain']:.2f} − 风险 {action['risk']:.2f} − 代价 {action['cost']:.2f} = U {action['utility']:.2f}，没有正收益。")
                if ranked:reasons.append('如果你仍希望尝试，可以勾选“明确接受可能较高的预计风险”，重新计算并确认计划；这不保证图片改善。')
                raise NoRecommendedAction(reasons or ['暂无可执行修正，可保留当前图片。'],ranked)
            target=eligible[0]['id']; targets=eligible[0]['target_ids']; cs=checklist(req)
            plan=obj(plan_id=uid(),requirement_id=req['requirement_id'],base_image_id=t['selected_image_id'],target_ids=targets,preserve_ids=[c['id'] for c in cs if c['id'] not in targets],allowed_change_ids=allowed,operation='regenerate',instructions='本轮共同修正：'+'；'.join(c['description']+': '+str(c['value']) for c in cs if c['id'] in targets),risk_notes=['重新生成，其他画面内容也可能改变；保留指令不是保真承诺'],ranking=ranked,deferred=deferred,evaluation_id=e['evaluation_id'],correction_ids=[c['correction_id'] for c in corrections],algorithm_config=json.loads(json.dumps(CONFIG)),judgment_basis='最新用户纠错优先，否则使用模型判断',effective_checks=effective_checks(e['checks'],corrections),confirmed_at=None)
            if getattr(self.adapter,'supports_edit',False):
                plan['operation']='image_edit';plan['risk_notes']=['传入基准图和文字执行原图编辑；未修改部分仍可能发生变化，并非像素级保真。']
            latest_corrections={c['constraint_id']:c for c in corrections}
            plan['user_observations']=[{'constraint_id':k,'text':latest_corrections[k]['reason'].strip()} for k in targets if k in latest_corrections and latest_corrections[k]['reason'].strip()]
            notes=list(dict.fromkeys(x['text'] for x in plan['user_observations']))
            if notes:plan['instructions']+='\n用户对本轮目标的观察：'+'；'.join(notes)+'\n上述文字作为问题观察；生成要求仍以已确认清单为准，不据此新增要求或改变其他要求。'
            t['plans'].append(plan); t['state']='PLANNING'; self.store.save(t); return plan
    def execute(self,tid,request_id,plan_id=None,evaluate_only=None,rebaseline=False):
        with self.store.lock:
            t=self.store.load(tid)
            if any(a['request_id']==request_id for a in t['attempts']): return t
            self.idle(t); req=self.req(t); plan=None
            if len(t['attempts'])>=t['operation_limit']: raise ValueError('已达到全部模型调用上限')
            if not evaluate_only and t['images'] and req['params'].get('requires_baseline_evaluation') and not self.evaluation(t,t['selected_image_id']):
                raise ValueError('目标已更新，请先按新目标重新检查当前保留图，再生成修改版')
            if plan_id:
                plan=next(p for p in t['plans'] if p['plan_id']==plan_id)
                if plan['base_image_id']!=t['selected_image_id'] or plan['requirement_id']!=req['requirement_id']: raise ValueError('计划已过期，请重新规划')
                current=self.evaluation(t,plan['base_image_id'])
                correction_ids=[c['correction_id'] for c in t['corrections'] if current and c['evaluation_id']==current['evaluation_id']]
                if not current or plan.get('evaluation_id')!=current['evaluation_id'] or plan.get('correction_ids')!=correction_ids: raise ValueError('评价或用户判断已更新，请重新计算修正计划')
                if t['revision_attempts']>=2: raise ValueError('两次修正请求机会已用完')
                t['revision_attempts']+=1; plan['confirmed_at']=now()
            elif not evaluate_only and any(i['requirement_id']==req['requirement_id'] for i in t['images']): raise ValueError('已有初图，请通过修正计划继续')
            if not evaluate_only and not plan and t['images']:
                if t['revision_attempts']>=2:raise ValueError('两次修正请求机会已用完')
                t['revision_attempts']+=1
            attempt=obj(attempt_id=uid(),request_id=request_id,kind='evaluate' if evaluate_only else 'generate',state='running',started_at=now(),finished_at=None,latency=None,usage=None,error=None)
            t['attempts'].append(attempt); t['state']='EVALUATING' if evaluate_only else ('REVISING' if plan else 'GENERATING'); self.store.save(t)
        start=time.monotonic()
        try:
            prompt=next(p for p in reversed(t['prompts']) if p['requirement_id']==req['requirement_id'])
            if evaluate_only:
                image=next(i for i in t['images'] if i['image_id']==evaluate_only)
                if image['requirement_id']!=req['requirement_id'] and not rebaseline: raise ValueError('目标已变化，请明确按新目标重新检查此图')
                checks=self.adapter.evaluate(self.store.folder(tid)/image['path'],req,next(n for n,i in enumerate(t['images']) if i['image_id']==image['image_id']))
                ev=obj(evaluation_id=uid(),image_id=image['image_id'],requirement_id=req['requirement_id'],rubric_version='1',checks=validate_checks(checks,req),model=self.adapter.name,image_requirement_id=image['requirement_id'],purpose='rebaseline' if rebaseline else 'evaluation',created_at=now())
                with self.store.lock:
                    t=self.store.load(tid); t['evaluations'].append(ev); self.store.record(t,'evaluations',ev)
                    self.rebuild_comparisons(t)
            else:
                actual=prompt['text']+ ('\n'+plan['instructions']+'\n尽量保留其他已确认要求。' if plan else '')
                if req['params'].get('reference_ids'):
                    from adapters.reference import edit
                    references=[{'image_id':i['image_id'],'label':i['label'],'path':self.store.folder(tid)/i['path'],'role':'base' if i['image_id']==req['params']['base_reference_id'] else 'feature_reference'} for i in t['images'] if i['image_id'] in req['params']['reference_ids']]
                    actual+='\n以base图片为基础，保留已完成的修改。其他参考图仅用于各自指定特征，不复制无关内容。'
                    raw,meta=self.adapter.edit(actual,req,references) if getattr(self.adapter,'supports_edit',False) else edit(actual,req,references)
                elif t['images'] and getattr(self.adapter,'supports_edit',False):
                    base_id=plan['base_image_id'] if plan else t['selected_image_id']
                    base=next(i for i in t['images'] if i['image_id']==base_id)
                    actual+='\n请基于提供的上一版图片编辑，而不是重新设计整个画面。仅执行本轮修改；尽量保持未涉及的人物、灯光、色调、空间密度及构图。如果某项已在本轮明确改变，以当前目标为准，不保留该项的旧值。'
                    raw,meta=self.adapter.edit(actual,req,[{'image_id':base_id,'label':base['label'],'path':self.store.folder(tid)/base['path'],'role':'base'}])
                else:raw,meta=self.adapter.generate(actual,req,len(t['images']))
                from PIL import Image
                decoded=Image.open(io.BytesIO(raw)); decoded.verify(); decoded=Image.open(io.BytesIO(raw))
                iid=uid(); rel='images/'+iid+'.png'; folder=self.store.folder(tid); (folder/'images').mkdir(exist_ok=True); decoded.save(folder/rel,'PNG'); raw=(folder/rel).read_bytes()
                image=obj(image_id=iid,label='V'+str(len(t['images'])),requirement_id=req['requirement_id'],prompt_id=prompt['prompt_id'],actual_prompt=actual,parent_image_id=plan['base_image_id'] if plan else (t['selected_image_id'] if t['images'] else None),plan_id=plan_id,operation=meta.get('operation', 'reference_edit' if req['params'].get('reference_ids') else ('regenerate' if plan else 'generate')),path=rel,sha256=hashlib.sha256(raw).hexdigest(),attempt_id=attempt['attempt_id'],created_at=now(),size=list(decoded.size),metadata=meta)
                with self.store.lock:
                    t=self.store.load(tid); t['images'].append(image)
                    if not t['selected_image_id']: t['selected_image_id']=iid
            with self.store.lock:
                a=next(a for a in t['attempts'] if a['attempt_id']==attempt['attempt_id']); a.update(state='succeeded',finished_at=now(),latency=time.monotonic()-start); t['state']='COMPARING' if evaluate_only and image['parent_image_id'] else 'REVIEWING'; self.store.save(t)
        except Exception as exc:
            with self.store.lock:
                t=self.store.load(tid); a=next(a for a in t['attempts'] if a['attempt_id']==attempt['attempt_id']); a.update(state='failed',finished_at=now(),error=str(exc)[:400],latency=time.monotonic()-start); t['state']='REVIEWING' if t['images'] else 'READY'; self.store.save(t)
            raise
        return t
    def generated_image_for_request(self,t,request_id):
        attempt=next((a for a in t['attempts'] if a['request_id']==request_id),None)
        if not attempt:raise ValueError('未找到生成请求，请重新确认生成方案')
        if attempt['state']=='running':raise ValueError('生成请求仍在处理中，请等待完成后刷新；未重复调用接口')
        if attempt['state']!='succeeded':
            raise ValueError('上一次生成请求失败或结果未知，没有可读取的新图片。未重复调用接口。初图请点击“重试初图”；修正请重新生成计划后确认，均计入调用额度。')
        image=next((i for i in t['images'] if i['attempt_id']==attempt['attempt_id']),None)
        if not image:raise ValueError('生成请求未关联到图片，请检查任务记录；不会读取旧版冒充本次结果')
        return image
    def select(self,tid,iid):
        with self.store.lock:
            t=self.store.load(tid); self.idle(t)
            if iid not in [i['image_id'] for i in t['images']]: raise ValueError('无效版本')
            t['selected_image_id']=iid; self.store.save(t)
    def export(self,tid,satisfaction=None):
        with self.store.lock:
            t=self.store.load(tid); self.idle(t); image=next(i for i in t['images'] if i['image_id']==t['selected_image_id']); req=next(r for r in t['requirements'] if r['requirement_id']==image['requirement_id']); folder=self.store.folder(tid); dest=folder/'result.zip'
            with zipfile.ZipFile(dest,'w') as z:
                z.write(folder/image['path'],'selected.png'); z.writestr('prompt.txt',image['actual_prompt']); z.writestr('requirements.json',json.dumps(req,ensure_ascii=False,indent=2)); z.writestr('history.json',json.dumps({'images':[{k:i[k] for k in ('label','image_id','parent_image_id','plan_id')} for i in t['images']],'comparisons':self.comparison_results(t),'raw_evaluations':t['evaluations'],'user_corrections':t['corrections'],'comparison_history':t.get('comparison_history',[]),'satisfaction':satisfaction},ensure_ascii=False,indent=2))
            t['satisfaction'].append(obj(value=satisfaction,image_id=image['image_id'],created_at=now())); self.store.save(t); return str(dest)
