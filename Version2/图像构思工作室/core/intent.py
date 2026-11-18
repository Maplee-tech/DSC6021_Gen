"""Model-produced draft IR; unconfirmed suggestions never enter the rubric."""
import json,re
from core.engine import uid,obj
SUGGESTION_COUNT=15
MAX_DRAFT_FIELDS=64
SYSTEM='''你是图像创作需求分析助手。根据用户原文，返回严格JSON，不要Markdown。不要生图。
格式 {"summary":"简洁摘要", "fields":[{"id":"f1","entity_id":"scene","type":"subject","label":"主体","value":"书店","source":"user_input","evidence":"原文逐字片段","strength":"must","options":[],"question":"主体如何呈现？","depends_on":[]}]}
将fields严格分成两类：先列原文直接表达的要求（source=user_input），再另外给出恰好15项新增的高质量优化建议（source=model_suggestion）。原文要求不计入这15项。总数=原文要求数+15，不是总共15张。type可为subject,scene,style,composition,lighting,detail,quantity,existence。
source仅user_input/model_suggestion/default。只有原文直接表达的内容可标user_input，必须提供原文逐字evidence，不能混入推断。如“赛博朋克”与“写实概念艺术”应为两个字段。不要输出confidence。
对尚未明确的维度提出贴合语境的建议和恰好3个互不重复的可选词或短句，question用简短中文。每张卡片都提出一个简短具体的选择题。覆盖与当前想法相关的场景、呈现方式、构图、色彩、光线、时间、氛围、主体细节等，避免重复。不要在options内加入D或自由输入，前端提供D。原文明确要求的字段options=[]、question=""，保留原值，不为它重新出一道题；新增建议才提供恰好3个不同的ABC选项。每项新增建议必须是原文尚未指定、可以独立选择的具体画面维度，不得重复原文内容或把同一问题换词凑数。每题的ABC都必须与原文兼容。每个单值维度使用独立entity_id，例如环境布局与地点身份分开；不要将多个scene/subject单值字段都挂在同一个entity_id上造成矛盾。所有模型补充保持model_suggestion；不要把建议当用户要求。
例如赛博朋克书店：书店、赛博朋克是明确要求；场景可问雨夜街区外景/书店室内/室内外结合；表现形式可问写实概念艺术/动漫插画/3D渲染。对不同想法动态设计选项，不机械套用书店模板。
value为字符串；新增建议可用options第一项作为候选值，仍保持待确认，不代表用户选择。strength为must/preference/free，depends_on引用本次fields中id。不要修改用户意图。模型建议的strength默认preference，待用户选择，不要把可选方案标成free；用户跳过题目才表示不约束该项。'''

def validate_draft(raw,text):
    if isinstance(raw,str): raw=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()))
    if not isinstance(raw,dict) or not isinstance(raw.get('fields'),list) or not 1<=len(raw['fields'])<=MAX_DRAFT_FIELDS: raise ValueError('模型解析格式错误：需要1至64项需求')
    fs=raw['fields']; ids=[f.get('id') for f in fs]
    if any(not isinstance(k,str) or not k for k in ids) or len(set(ids))!=len(ids):raise ValueError('模型字段ID缺失或重复')
    mapping={k:uid() for k in ids}; out=[]; questions=0
    for f in fs:
        f=dict(f)
        # A model may leave a pending suggestion's value empty until the user chooses.
        # Use its first option only as draft storage; status remains pending.
        if f.get('source')=='model_suggestion' and not f.get('value'):
            options=f.get('options')
            if isinstance(options,list) and options and isinstance(options[0],str):f['value']=options[0]
        for key in ('entity_id','type','label','value','source','strength'):
            if not isinstance(f.get(key),str) or not f[key].strip():raise ValueError('模型字段缺失：'+key)
        if f['source'] not in ('user_input','model_suggestion','default') or f['strength'] not in ('must','preference','free'):raise ValueError('模型来源或强度非法')
        options=f.get('options',[]); deps=f.get('depends_on',[])
        if not isinstance(options,list) or len(options)>6 or any(not isinstance(x,str) for x in options):raise ValueError('模型选项格式错误')
        if not isinstance(deps,list) or any(d not in mapping for d in deps):raise ValueError('模型依赖引用错误')
        explicit=f['source']=='user_input'; evidence=f.get('evidence','')
        if explicit and (not isinstance(evidence,str) or not evidence or evidence not in text):raise ValueError('模型标为原文要求但没有提供有效原文依据，请重试解析')
        question=f.get('question','')
        if not isinstance(question,str):raise ValueError('澄清问题格式错误')
        if question:questions+=1
        out.append(obj(id=mapping[f['id']],entity_id=f['entity_id'],type=f['type'],description=f['label'],value=f['value'],source=f['source'],origin=f['source'],status='confirmed' if explicit else 'pending',strength=f['strength'],locked=False,depends_on=[mapping[d] for d in deps],options=options,question=question,evidence=evidence))
    return obj(summary=str(raw.get('summary','')),constraints=out)

def is_original(c):
    # Keep provenance when a user later edits a selected value.
    return c.get('origin')=='user_input' or c.get('source')=='user_input' or (not c.get('origin') and c.get('source')=='user_choice' and bool(c.get('evidence')))

def is_suggestion(c):
    return not is_original(c) and (c.get('origin')=='model_suggestion' or c.get('source') in ('model_suggestion','default') or bool(c.get('options')))

def validate_suggestions(draft):
    cs=draft['constraints']
    original=[c for c in cs if is_original(c)]
    added=[c for c in cs if c['source']=='model_suggestion']
    if not original:raise ValueError('AI 未返回原文要求，请重试解析')
    if len(added)!=SUGGESTION_COUNT or any(c['source']=='default' for c in cs):
        raise ValueError('AI 返回了 '+str(len(added))+' 项新增建议，需要另外提供15项（原文要求不计入），请重试解析')
    seen=set(); explicit={(c['entity_id'],c['type'],c['description'].strip()) for c in original}
    for c in added:
        opts=[v.strip() for v in c['options']]
        if len(opts)!=3 or not all(opts) or len(set(opts))!=3 or not c['question'].strip():
            raise ValueError('新增建议需要完整问题及3个不同的ABC选项，请重试解析')
        key=re.sub(r'\s+','',c['description']).casefold()
        if key in seen or (c['entity_id'],c['type'],c['description'].strip()) in explicit:
            raise ValueError('AI 返回了重复的建议维度，请重试解析')
        seen.add(key)
    return draft

class DraftValidationError(ValueError):
    pass

def extract_task(engine,tid):
    from core.engine import now
    with engine.store.lock:
        t=engine.store.load(tid); engine.idle(t)
        if len(t['attempts'])>=t['operation_limit']:raise ValueError('已达到调用上限')
        a=obj(attempt_id=uid(),request_id=uid(),kind='extract',state='running',started_at=now(),finished_at=None,latency=None,usage=None,error=None)
        t['attempts'].append(a); engine.store.save(t)
    try:
        raw=engine.adapter.extract(t['original_input'])
        try:
            draft=validate_draft(raw,t['original_input'])
            from adapters.mock import MockAdapter
            if not isinstance(engine.adapter,MockAdapter):validate_suggestions(draft)
        except (ValueError,TypeError,KeyError,AttributeError):
            # Only expose messages produced by our validator; never raw API responses.
            import sys
            error=sys.exc_info()[1]
            message=str(error) if type(error) is ValueError else 'AI 返回结构不完整，请重试解析'
            raise DraftValidationError(message) from None
        with engine.store.lock:
            t=engine.store.load(tid); t['draft']=draft; t['attempts'][-1].update(state='succeeded',finished_at=now());engine.store.save(t)
        return draft
    except Exception as error:
        message=str(error) if isinstance(error,DraftValidationError) else '需求模型调用失败或超时。原始想法已保存，请检查文本模型接口后重试解析。'
        with engine.store.lock:
            t=engine.store.load(tid); t['attempts'][-1].update(state='failed',finished_at=now(),error=message);engine.store.save(t)
        raise ValueError(message) from None
