import os,json,html
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED','False')
os.environ.setdefault('MPLCONFIGDIR',str(__import__('pathlib').Path(__file__).resolve().parent/'.cache'))
from pathlib import Path
import gradio as gr
from core.engine import Workflow,uid,obj,checklist,NoRecommendedAction,effective_checks,evaluation_corrections
from core.feedback import analyze_feedback,apply_feedback,recheck_feedback
from core.intent import MAX_DRAFT_FIELDS,is_original,is_suggestion
from adapters.mock import MockAdapter
from adapters.provider import GatewayAdapter
from adapters.existing import ExistingProjectAdapter
ROOT=Path(__file__).resolve().parent
MODE=os.getenv('STUDIO_MODE','existing')
if MODE not in ('existing','gateway','mock'):raise ValueError('未知接口通道，请检查 STUDIO_MODE；不会自动改用模拟数据')
# Mock is only available to explicit isolated tests; app.py rejects it for normal launches.
engine=Workflow(ROOT/'tasks',{'existing':ExistingProjectAdapter,'gateway':GatewayAdapter,'mock':MockAdapter}[MODE]())
CSS=(ROOT/'frontend/better_prompt.css').read_text()
# Bundle the pinned rendering library locally; the browser requires no CDN.
BOOK_JS='() => { const THREE = (() => { const module={exports:{}}; const exports=module.exports;'+(ROOT/'frontend/vendor/three.min.js').read_text()+'; return module.exports; })();'+(ROOT/'frontend/better_scene.js').read_text()+(ROOT/'frontend/better_prompt.js').read_text()+' }'

def safe(fn):
    def wrapped(*a):
        try:return fn(*a)
        except Exception as e: raise gr.Error(str(e))
    return wrapped

def draft_rows(cs):
    return [[c.get(k,'') if k!='depends_on' else ','.join(c[k]) for k in ['id','entity_id','type','description','value','source','status','strength','locked','depends_on']] for c in cs]


def parse(data):
    cs=[]
    for row in data:
        if not str(row[4]).strip():continue
        k,entity,typ,desc,val,source,status,strength,locked,deps=row
        if source not in ('user_input','user_choice','model_suggestion','default') or status not in ('unspecified','pending','confirmed') or strength not in ('must','preference','free'): raise ValueError('来源、确认状态或约束强度无效')
        cs.append(obj(id=k or uid(),entity_id=entity,type=typ,description=desc,value=val,source=source,status=status,strength=strength,locked=locked is True or str(locked).lower()=='true',depends_on=[s.strip() for s in str(deps or '').split(',') if s.strip()]))
    return cs

def supplement_view(t):
    req=engine.req(t) if t['requirements'] else None
    items=[c['value'] for c in (checklist(req) if req else []) if c['description']=='看图后新增要求']
    changes=req['params'].get('feedback_change',{}).get('changes',[]) if req else []
    items += [c['label']+'：'+str(c['old'] or '未指定')+' → '+str(c['new']) for c in changes]
    selected=next((i for i in t['images'] if i['image_id']==t['selected_image_id']),None)
    generated=bool(req and any(i['requirement_id']==req['requirement_id'] for i in t['images']))
    available=bool(items and selected and not generated and t['revision_attempts']<2)
    summary='**已保存的额外补充**\n\n'+'\n\n'.join('• '+html.escape(str(v)) for v in items) if items else '尚未保存额外补充。'
    if items:
        summary+='\n\n'+('已用于当前需求版本的图片。' if generated else '待用于下一张图；不会伪装成当前图片已经满足的检查项。')
    if selected:summary+='\n\n后续生成基于当前保留的 **'+selected['label']+'**；要改另一版，请先明确采用该版本。'
    if t['revision_attempts']>=2:summary+='\n\n本任务两次修改机会已用完。'
    plan=next((p for p in reversed(t['plans']) if p.get('confirmed_at')),None)
    previous=html.escape(plan['instructions']) if plan else '暂无上一轮修改。'
    return summary,available,previous

def refresh(tid):
    if not tid:return (None,'尚未创建任务',[],gr.update(choices=[],value=None),None,None,[],gr.update(choices=[],value=[]),gr.update(choices=[],value=None),'暂无比较','',gr.update(choices=[],value=None),[],'尚未保存额外补充。',gr.update(interactive=False),'暂无上一轮修改。')
    t=engine.store.load(tid); selected=next((i for i in t['images'] if i['image_id']==t['selected_image_id']),None)
    ev=engine.evaluation(t,t['selected_image_id']); req=engine.req(t) if t['requirements'] else None
    descriptions={c['id']:c['description']+': '+str(c['value']) for c in checklist(req)} if req else {}
    view=t.get('review_ui',{}).get(t['selected_image_id'],{})
    table=[]; labels=[]; saved_notes=[]
    if ev:
        corrections={c['constraint_id']:c['corrected_status'] for c in t['corrections'] if c['evaluation_id']==ev['evaluation_id']}
        for c in ev['checks']:
            k=c['constraint_id']; effective=corrections.get(k,c['status']); table.append([descriptions[k],c['status'],effective,c['evidence']]); labels.append((descriptions[k],k))
    if ev:
        latest_notes={c['constraint_id']:c for c in t['corrections'] if c['evaluation_id']==ev['evaluation_id']}
        saved_notes=[[descriptions.get(k,k),latest_notes[k]['reason']] for k in view.get('selected',[]) if k in latest_notes]
    gallery=[(str(engine.store.folder(tid)/i['path']),i['label']+(' · 已选择' if i==selected else '')+' · 基于 '+str(next((x['label'] for x in t['images'] if x['image_id']==i['parent_image_id']),'初始'))) for i in t['images']]
    latest=t['images'][-1] if t['images'] else None
    image_labels={i['image_id']:i['label'] for i in t['images']}
    current_comparisons=[c for c in engine.comparison_results(t) if c['requirement_id']==t['active_requirement_id']]
    comparisons='\n\n'.join('**'+image_labels.get(c['base_id'],'旧版')+' → '+image_labels.get(c['candidate_id'],'新版')+'**\n\n当前目标下比较 · 最新用户纠错优先，否则使用模型判断 · 本地计算 G/R\n\n**'+c['recommendation']+'** · G='+str(c['G'])+' / R='+str(c['R'])+'\n\n修复：'+'；'.join(descriptions.get(k,k) for k in c['fixed_ids'])+'\n\n退化：'+'；'.join(descriptions.get(k,k) for k in c['regressed_ids'])+'\n\n不确定：'+'；'.join(descriptions.get(k,k) for k in c['uncertain_changes']) for c in current_comparisons) or '当前目标下尚无两版完整评价；旧目标的结果不会计入本轮退化。'
    attempts='\n'.join(a['kind']+' · '+a['state']+(' · '+str(a['error']) if a['error'] else '') for a in t['attempts'])
    supplements,can_generate,previous=supplement_view(t)
    if selected and not ev:supplements+='\n\n**目标已更新，需点击「按当前目标重新检查图片」，再计算修改方案。**'
    if ev and req:
        changed=req['params'].get('feedback_change',{}).get('changes',[])
        saved_notes += [[descriptions.get(c['constraint_id'],c['label']),'新目标：'+str(c['new'])] for c in changed]
    return (str(engine.store.folder(tid)/selected['path']) if selected else None,'**'+t['state']+'** · 修正请求 '+str(t['revision_attempts'])+'/2 · 成功图片 '+str(len(t['images']))+' · 调用 '+str(len(t['attempts']))+'/'+str(t['operation_limit']),gallery,gr.update(choices=[(i['label'],i['image_id']) for i in t['images']],value=t['selected_image_id']),str(engine.store.folder(tid)/selected['path']) if selected else None,str(engine.store.folder(tid)/latest['path']) if latest else None,table,gr.update(choices=labels,value=[k for k in view.get('selected',[]) if k in descriptions]),gr.update(choices=labels,value=view.get('correction_id') if view.get('correction_id') in descriptions else None),comparisons,attempts,gr.update(choices=labels,value=None),saved_notes,supplements,gr.update(interactive=can_generate),previous)

with gr.Blocks(title='Better Prompt · 立体创作之书',css=CSS,js=BOOK_JS) as demo:
    gr.HTML((ROOT/'frontend/better_shell.html').read_text(),elem_id='bp-shell')
    with gr.Accordion('任务与连接信息',open=True,elem_id='bp-task-settings'):
        gr.Markdown('**当前通道：'+engine.adapter.name+'** · 每任务最多两次修正请求 · 全部调用上限 12。')
        tid=gr.Textbox(label='任务 ID（自动保存；可粘贴历史 ID 恢复）'); load=gr.Button('恢复 / 刷新任务')
    status=gr.Markdown('尚未创建任务',elem_id='pb-status')
    with gr.Row(elem_id='bp-book'):
        with gr.Column(scale=3,min_width=200,elem_id='bp-left'):
            gr.HTML('<div class="bp-page-head"><span id="bp-left-kicker">01 / THE IDEA</span><h2 id="bp-left-title">从一个想法开始</h2><p id="bp-left-subtitle">不必想得很完整。把脑海中的画面写下来。</p></div>')
            with gr.Group(elem_id='bp-idea-input'):
                idea=gr.Textbox(label='你的初始想法',placeholder='比如：两个大学生在图书馆，一起赶最后一份 project……',lines=6)
                create=gr.Button('分析这个想法 ↗',variant='primary',elem_id='bp-analyze')
                gr.Markdown('点击分析后，AI 会保留原始要求，并另外提供 15 项可选建议。输入文字本身不会自动调用接口。',elem_classes='bp-help')
                with gr.Accordion('解析状态与重试',open=False):
                    retry_extract=gr.Button('重试 AI 解析当前任务',elem_id='bp-retry-analysis')
                    draft_summary=gr.Markdown('写下想法，右页将出现 AI 提供的选项。')
                draft_state=gr.State([])
                gr.HTML('<div class="bp-margin-note"><span>A SMALL BEGINNING</span><p>一个好画面，<br>从一句话开始。</p><i>✳</i></div>')
            with gr.Group(elem_id='bp-image-view'):
                selected_image=gr.Image(label='当前保留的图片',type='filepath',elem_id='pb-main-image',show_download_button=True)
                gr.HTML('<p id="pb-image-caption">生成第一张图片后，它会出现在这里。</p><div id="bp-version-ribbons"></div><small id="bp-image-folio">YOUR IMAGE / STILL IN THE MAKING</small>')
                with gr.Accordion('展开两版对比',open=False,elem_id='bp-comparison-images'):
                    baseline=gr.Image(label='当前保留版本',type='filepath')
                    candidate=gr.Image(label='最新候选（不会自动采用）',type='filepath')
                with gr.Accordion('全部历史图片',open=False):
                    gallery=gr.Gallery(label='版本时间轴',columns=3,height=180,elem_id='pb-history')
            gr.HTML('<div class="bp-page-foot"><span>BETTER PROMPT</span><span id="bp-left-folio">01</span></div>')
        with gr.Column(scale=4,min_width=280,elem_id='bp-center'):
            gr.HTML((ROOT/'frontend/better_center.html').read_text(),elem_id='bp-scene-block')
        with gr.Column(scale=3,min_width=200,elem_id='bp-right'):
            gr.HTML('<div class="bp-page-head"><span id="bp-right-kicker">MAKE IT YOURS</span><h2 id="bp-right-title">把细节，慢慢补齐</h2><p id="bp-right-subtitle">展开卡片，做一道关于画面的选择题。</p></div>')
            with gr.Group(elem_id='bp-choice-tools'):
                analysis_status=gr.HTML('<div data-analysis-state="idle">输入想法后，点击左侧「分析这个想法」。</div>',elem_id='bp-analysis-status')
                with gr.Accordion('原始要求 · 已保留，不计入建议数量',open=False,elem_id='bp-original-requirements'):
                    original_summary=gr.Markdown('尚无原始要求。')
                    gr.Markdown('这些要求会自动保留；需要调整时，可在下方「画幅与高级要求」中编辑。')
                gr.HTML('<div class="bp-card-meta"><span>AI 新增建议 · 目标 15 项</span><span id="bp-card-progress">等待 AI 分析</span></div>')
                slot_outputs=[]; slot_inputs=[]
                with gr.Row(elem_id='pb-card-tray'):
                    for n in range(MAX_DRAFT_FIELDS):
                        with gr.Group(visible=False,elem_classes=['panel','pb-index-card']) as group:
                            heading=gr.Markdown()
                            value=gr.Radio(choices=[],label='选择一项（未选择即跳过）',interactive=True)
                            custom=gr.Textbox(label='D · 我自己填写',placeholder='选择 D 后填写你的想法',visible=False)
                            skip=gr.Button('跳过这题',size='sm')
                            value.input(lambda v:gr.update(visible=v=='D'),value,custom)
                            skip.click(lambda:(None,gr.update(visible=False)),outputs=[value,custom])
                        slot_outputs.extend([group,heading,value,custom]); slot_inputs.extend([value,custom])
                confirm=gr.Button('确认选择，整理生成方案 →',variant='primary',elem_id='bp-confirm')
                with gr.Accordion('还有想补充的细节？',open=False):
                    extra=gr.Textbox(label='自由补充（每行一项）',placeholder='还希望画面中出现什么？',lines=2)
                    apply=gr.Button('保存卡片选择与自由补充')
                    saved_notice=gr.Markdown()
                with gr.Accordion('画幅与高级要求',open=False):
                    ratio=gr.Dropdown(['1:1','3:2','2:3','16:9'],value='3:2',label='画幅')
                    scenario=gr.Dropdown(['mixed','pass','uncertain','invalid'],value='mixed',label='模拟验证场景',visible=isinstance(engine.adapter,MockAdapter))
                    gr.Markdown('修改已锁定值前请先取消锁定并保存。confirmed=确认，pending=待确认；must=必须，preference=偏好。')
                    cards=gr.Dataframe(headers=['ID','实体','类型','名称','内容','来源','确认状态','约束强度','locked','依赖ID'],datatype=['str']*8+['bool','str'],type='array',interactive=True)
                with gr.Accordion('查看提示词 / 生成第一张图',open=False,elem_id='pb-first-plan'):
                    prompt=gr.Textbox(elem_id='pb-prompt',label='已确认的生成方案',lines=5,interactive=False)
                    generate=gr.Button('生成 V0，翻开下一页 →',variant='primary',elem_id='pb-generate')
                    retry_initial=gr.Button('重试失败的初图请求',elem_id='bp-retry-image')
            with gr.Group(elem_id='bp-supplement-tools'):
                supplement=gr.Button('＋ 补充现有选项以外的内容',elem_id='bp-add-supplement')
                supplement_saved=gr.Markdown('尚未保存额外补充。',elem_id='bp-supplement-saved')
                with gr.Group(visible=False,elem_id='bp-supplement-panel') as supplement_panel:
                    supplement_text=gr.Textbox(label='补充你希望画面中出现的内容',placeholder='例如：教室后方再增加一层环形看台。',lines=3)
                    gr.Markdown('可以补充新内容，也可以替换原要求。AI 会先解释你的意思；确认后才更新目标。',elem_classes='bp-help')
                    supplement_save=gr.Button('分析这段补充',variant='primary',elem_id='bp-supplement-analyze')
                    supplement_notice=gr.Markdown()
                supplement_generate=gr.Button('预览新目标的修改方案',interactive=False,elem_id='bp-supplement-image')
                with gr.Group(elem_id='bp-feedback-review'):
                    feedback_mode=gr.Radio([('让 AI 区分','auto'),('纠正图片，原要求不变','correction'),('改变或增加要求','change')],value='auto',label='这次意见的意思',elem_id='bp-feedback-mode')
                    feedback_preview=gr.Markdown('填写下方优化意见或补充内容，分析后在这里确认。')
                    feedback_id=gr.State('')
                    feedback_confirm=gr.Button('确认理解并保存',interactive=False,elem_id='bp-feedback-confirm')
                    feedback_recheck=gr.Button('按当前目标重新检查图片',elem_id='bp-feedback-recheck')
                with gr.Accordion('上一轮已执行的修改说明',open=False):
                    previous_guidance=gr.Markdown('暂无上一轮修改。')
            with gr.Group(elem_id='bp-review-tools'):
                gr.HTML('<div class="bp-check-strip"><span>已满足 <b id="bp-pass">—</b></span><span>待优化 <b id="bp-fail">—</b></span><span>待确认 <b id="bp-uncertain">—</b></span></div>')
                with gr.Accordion('01 / 逐项记录优化方向',open=True):
                    problem_tag=gr.Radio(choices=[],label='选择一个要优化的问题',interactive=True,elem_id='pb-fix-chips')
                    simple_note=gr.Textbox(elem_id='pb-note',label='希望这一项怎么改？',placeholder='例如：两人看同一台电脑，其余内容尽量保留。',lines=3)
                    save_tag=gr.Button('分析这一项优化意见',elem_id='bp-save-note')
                    note_status=gr.Markdown('每个问题分别保存，再一起修改。',elem_classes='bp-help')
                with gr.Accordion('02 / 本轮修改与生成',open=False,elem_id='bp-revision-plan') as revision_panel:
                    saved_items=gr.Dataframe(headers=['已保存的问题','该项优化点'],interactive=False)
                    fixes=gr.CheckboxGroup(label='本轮采用哪些已保存优化项？（可多选）',elem_id='bp-fix-selection')
                    simple_plan=gr.Button('看看修改方案 →',variant='primary',elem_id='pb-plan')
                    plantext=gr.Textbox(label='这次准备怎么改',lines=5,interactive=False); planid=gr.State(''); requestid=gr.State('')
                    execute=gr.Button('确认方案，生成修改版 →',variant='primary',interactive=False,elem_id='pb-execute')
                with gr.Accordion('AI 检查、纠错与算法依据',open=False):
                    gr.Markdown('AI 先区分纠正图片与改变目标；改变目标后，两版都按新目标检查。U、G/R 统一使用该次评价的最新用户纠错，否则使用模型判断。U 是本地规则估计；G/R 是同一目标下的加权修复／退化统计，不确定不算修复或退化。原始模型结果与用户纠错分别留存。')
                    checks=gr.Dataframe(elem_id='pb-checks',headers=['要求','AI状态','用户修正后状态','可见依据'],interactive=False)
                    correction_id=gr.Dropdown(label='纠正哪个检查项'); correction_status=gr.Dropdown([('AI看错了：满足','pass'),('确认不满足','fail'),('无法确定','uncertain')],value='pass',label='你的判断')
                    reason=gr.Textbox(label='纠错说明 / 补充观察'); correction=gr.Button('保存用户判断')
                    risk=gr.Checkbox(label='允许预览高风险方案',value=False); makeplan=gr.Button('按高级设置计算计划')
                    math_detail=gr.Textbox(label='本地公式计算明细（依据模型检查与用户判断）',lines=6,interactive=False)
                    retry=gr.Button('重新评价当前图片（调用视觉模型）',elem_id='bp-reevaluate')
            with gr.Group(elem_id='bp-version-tools'):
                comparison=gr.Markdown(elem_id='bp-comparison-result')
                with gr.Accordion('选择、回退与导出',open=True):
                    version=gr.Dropdown(label='选择要保留的版本'); select=gr.Button('明确采用所选版本 / 回退',variant='primary')
                    satisfaction=gr.Slider(1,5,value=3,step=1,label='你的满意度（独立于 AI 评价）'); export=gr.Button('导出当前保留版本'); download=gr.File(label='图片、提示词与历史')
                with gr.Accordion('组合各版本喜欢的部分',open=False):
                    gr.Markdown('AI 观察指出变化，由你选择保留。确认偏好会建立新需求版本，仍受两次修正上限约束。')
                    observe_button=gr.Button('AI 找出两个版本的变化（调用视觉模型）',elem_id='bp-observe')
                    observations=gr.Dataframe(headers=['特征','旧版/当前基准观察','新版观察'],interactive=False)
                    ref_base=gr.Textbox(label='以哪个版本为基础？',value='V1')
                    ref_choices=gr.Dataframe(headers=['特征','参考版本（V0/V1）','希望保留的样子'],datatype=['str','str','str'],type='array',row_count=(2,'dynamic'),col_count=(3,'fixed'),value=[['','',''],['','','']],interactive=True)
                    ref_prepare=gr.Button('确认偏好，预览参考图方案')
                    ref_preview=gr.Textbox(label='待执行方案',interactive=False)
                    ref_execute=gr.Button('确认传入参考图并生成',interactive=False,elem_id='bp-reference-image')
                with gr.Accordion('调用记录',open=False):
                    attempts=gr.Textbox(label='调用历史与失败记录',lines=4,interactive=False)
            gr.HTML('<div class="bp-page-foot"><span id="bp-right-foot">YOUR CHOICES, YOUR PICTURE</span><span id="bp-right-folio">02</span></div>')
    outputs=[baseline,status,gallery,version,selected_image, candidate,checks,fixes,correction_id,comparison,attempts,problem_tag,saved_items,supplement_saved,supplement_generate,previous_guidance]
    def render_draft(cs,summary='',analysis_state=None):
        if len(cs)>MAX_DRAFT_FIELDS:raise ValueError('需求超过64项，请合并后再展示')
        updates=[cs,summary,draft_rows(cs)]
        for n in range(MAX_DRAFT_FIELDS):
            if n>=len(cs):updates.extend([gr.update(visible=False),'',gr.update(choices=[],value=None),gr.update(value='',visible=False)]);continue
            c=cs[n]; source='原文已指定' if c['source']=='user_input' else ('你已选择' if c['source']=='user_choice' else 'AI 提议，可跳过')
            options=c.get('options',[])[:3]
            # Old saved drafts may have fewer choices; do not invent AI options.
            choice=None
            if c['status']=='confirmed':choice=next((chr(65+i) for i,v in enumerate(options) if v==c['value']),'D')
            items=[(chr(65+i)+' · '+v,chr(65+i)) for i,v in enumerate(options)]+[('D · 我自己填写','D')]
            updates.extend([gr.update(visible=not is_original(c),elem_classes=['panel','pb-index-card','pb-ai-card' if is_suggestion(c) else 'pb-user-card']),'### '+str(sum(not is_original(x) for x in cs[:n+1]))+'. '+(c.get('question') or c['description'])+'\n'+source,gr.update(choices=items,value=choice),gr.update(value=c['value'] if choice=='D' else '',visible=choice=='D')])
        originals=[c for c in cs if is_original(c)]
        suggestions=[c for c in cs if is_suggestion(c)]
        original_text='\n\n'.join('**'+html.escape(c['description'])+'**：'+html.escape(str(c['value'])) for c in originals) or '尚无原始要求。'
        mode='mock' if isinstance(engine.adapter,MockAdapter) else 'ready'
        state=analysis_state or (mode if cs else 'idle')
        if state=='loading':message='AI 正在分析，正在生成额外 15 项建议…'
        elif state=='error':message=summary+' 原始输入已保留；可点击左侧「解析状态与重试」。'
        elif state=='mock':message='当前是模拟通道，未调用 AI。这里只是测试选项；真实解析请使用 existing 或 gateway 通道。'
        elif cs:message='已保留 '+str(len(originals))+' 项原始要求；另外提供 '+str(len(suggestions))+' 项 AI 建议。'+(' 这是历史草稿，不会自动补调用；如需 15 项请重新分析。' if len(suggestions)!=15 else ' 展开卡片选择 ABC，或选 D 自填。')
        else:message=summary or '输入想法后，点击左侧「分析这个想法」。'
        updates.extend([original_text,'<div role="status" aria-live="polite" data-analysis-state="'+state+'">'+html.escape(message)+'</div>'])
        return updates
    draft_outputs=[draft_state,draft_summary,cards]+slot_outputs+[original_summary,analysis_status]
    @safe
    def start(text):
        t=engine.create(text); return t['task_id'],'','',uid()
    @safe
    def analyze(tid):
        from core.intent import extract_task
        draft=extract_task(engine,tid)
        return render_draft(draft['constraints'],draft['summary'])
    def analysis_request(text,task_id='',retry=False):
        from core.intent import extract_task
        rid=uid()
        button_off=[gr.update(interactive=False),gr.update(interactive=False)]
        button_on=[gr.update(interactive=True),gr.update(interactive=True)]
        yield [gr.skip(),'','',rid]+render_draft([],'正在请求 AI 分析，请等待……','loading')+button_off
        try:
            if retry:
                if not task_id:raise ValueError('请先输入想法并开始分析')
            else:
                if not text.strip():raise ValueError('请先输入你的想法')
                task_id=engine.create(text.strip())['task_id']
            yield [task_id,'','',rid]+render_draft([],'正在请求 AI 分析，请等待……','loading')+button_off
            draft=extract_task(engine,task_id)
            result=render_draft(draft['constraints'],draft['summary'])
        except Exception as error:
            # extract_task redacts provider details; no raw transport credentials reach this UI.
            message=str(error) if isinstance(error,ValueError) else '解析未完成，请重试。'
            result=render_draft([],message,'error')
        yield [task_id,'','',rid]+result+button_on
    def new_analysis(text):yield from analysis_request(text)
    def retry_analysis(task_id):yield from analysis_request('',task_id,True)
    analysis_outputs=[tid,prompt,planid,requestid]+draft_outputs+[create,retry_extract]
    create.click(new_analysis,idea,analysis_outputs,show_progress='minimal',concurrency_id='intent-analysis').then(safe(refresh),tid,outputs)
    retry_extract.click(retry_analysis,tid,analysis_outputs,show_progress='minimal',concurrency_id='intent-analysis').then(safe(refresh),tid,outputs)
    @safe
    def apply_cards(tid,cs,extra,*values):
        import copy
        cs=copy.deepcopy(cs)
        if not cs:raise ValueError('请先完成 AI 解析')
        for n,c in enumerate(cs):
            if is_original(c):continue
            choice,custom=values[n*2:n*2+2]
            accept=choice is not None
            if choice=='D':val=(custom or '').strip()
            elif choice in ('A','B','C'):
                options=c.get('options',[]);index=ord(choice)-65
                if index>=len(options):raise ValueError('选项已变化，请重新选择')
                val=options[index]
            else:val=c['value']
            if accept and not val:raise ValueError(c['description']+'：选择D后请填写内容，或跳过这题')
            if val!=c['value'] or (accept and c['source']!='user_input'):c['source']='user_choice'
            if accept and c['strength']=='free':c['strength']='preference'
            c.update(value=val,status='confirmed' if accept else 'pending')
        # Keep supplementary rows in the draft so they are editable after saving.
        for line in extra.splitlines():
            if line.strip() and not any(c['value']==line.strip() for c in cs):
                if len(cs)>=MAX_DRAFT_FIELDS:raise ValueError('最多64项要求，请合并内容后再保存')
                cs.append(obj(id=uid(),entity_id=uid(),type='detail',description='你的补充',value=line.strip(),source='user_choice',status='confirmed',strength='must',locked=False,depends_on=[],options=[],question=''))
        with engine.store.lock:
            t=engine.store.load(tid);engine.idle(t);t['draft']={'schema_version':1,'summary':'已保存你的选择','constraints':cs};engine.store.save(t)
        return render_draft(cs,'已保存你的选择；确认需求后才能生成。')+['已保存','']
    @safe
    def apply_form(tid,cs,extra,data,*values):
        import copy
        cs=copy.deepcopy(cs); edits={c['id']:c for c in parse(data)}
        for c in cs:
            if is_original(c) and c['id'] in edits:c.update(edits[c['id']])
        return apply_cards(tid,cs,extra,*values)
    apply.click(apply_form,[tid,draft_state,extra,cards]+slot_inputs,draft_outputs+[saved_notice,extra])
    @safe
    def confirm_cards(tid,data,ratio,scenario):
        cs=parse(data)
        for c in cs:
            if c['status']=='confirmed' and c['source']=='user_choice' and c['strength']=='free':c['strength']='preference'
        t=engine.store.load(tid)
        if t['requirements']:
            old={c['id']:c for c in engine.req(t)['constraints']}
            for c in cs:
                if c['id'] in old and old[c['id']]['locked'] and c['value']!=old[c['id']]['value']: raise ValueError('锁定内容不能直接修改；先保持原值取消锁定并确认，再编辑')
        t=engine.confirm(tid,cs,{'aspect_ratio':ratio,'mock_scenario':scenario}); return '已确认 '+str(len(checklist(engine.req(t))))+' 项要求（已全部纳入提示词及检查清单）\n\n'+t['prompts'][-1]['text'],uid()
    confirm.click(apply_form,[tid,draft_state,extra,cards]+slot_inputs,draft_outputs+[saved_notice,extra]).success(confirm_cards,[tid,cards,ratio,scenario],[prompt,requestid]).success(fn=None,js="() => {window.betterPrompt?.openPlan()}").then(safe(refresh),tid,outputs)
    @safe
    def run(tid,rid,pid=None):
        before=engine.store.load(tid)
        if before['images'] and not engine.evaluation(before,before['selected_image_id']):
            recheck_feedback(engine,tid)
        t=engine.execute(tid,rid,pid or None)
        image=engine.generated_image_for_request(t,rid)
        if not engine.evaluation(t,image['image_id']):engine.execute(tid,rid+'-eval',evaluate_only=image['image_id'])
        return refresh(tid)
    first_generation=generate.click(lambda: gr.update(interactive=False),outputs=generate).then(safe(lambda t,r:run(t,r)),[tid,requestid],outputs)
    def request_feedback(event):
        event.then(fn=None,js="() => {window.betterPrompt?.endRequest()}")
        return event
    request_feedback(first_generation)
    first_generation.then(lambda: gr.update(interactive=True),outputs=generate)
    first_generation.success(fn=None,js="() => {window.betterPrompt?.go(1)}")
    @safe
    def retry_initial_image(tid):
        t=engine.store.load(tid)
        previous=[a for a in t['attempts'] if a['kind']=='generate']
        if not previous or previous[-1]['state'] not in ('failed','unknown','interrupted'):raise ValueError('没有可重试的失败生成请求')
        return run(tid,uid())
    request_feedback(retry_initial.click(retry_initial_image,tid,outputs)).success(fn=None,js="() => {window.betterPrompt?.go(1)}")
    def save_review(tid,allowed,cid,status,note):
        with engine.store.lock:
            t=engine.store.load(tid);engine.idle(t)
            ev=engine.evaluation(t,t['selected_image_id'])
            if not ev:raise ValueError('请先完成图片评价')
            if cid:
                existing=next((c for c in reversed(t['corrections']) if c['evaluation_id']==ev['evaluation_id'] and c['constraint_id']==cid),None)
                if not existing or (existing['corrected_status'],existing['reason'])!=(status,note):engine.correct(tid,cid,status,note)
            t=engine.store.load(tid)
            t.setdefault('review_ui',{})[t['selected_image_id']]={'selected':list(allowed or []),'correction_id':cid}
            engine.store.save(t)
    @safe
    def save_judgment(tid,allowed,cid,status,note):
        if not cid:raise ValueError('请先选择要纠正的检查项')
        save_review(tid,allowed,cid,status,note)
        return refresh(tid)
    correction.click(save_judgment,[tid,fixes,correction_id,correction_status,reason],outputs).success(lambda:('判断已保存，已保留勾选项。请重新计算计划。','',gr.update(interactive=False)),outputs=[plantext,planid,execute])
    def plan(tid,allowed,risk,cid=None,status='pass',note=''):
        try:
            save_review(tid,allowed,cid,status,note)
            p=engine.plan(tid,allowed,risk)
        except NoRecommendedAction as exc:
            return '本轮暂不生成修改计划\n\n'+str(exc),'','',gr.update(interactive=False)
        except Exception as exc:
            return '无法生成计划：'+str(exc),'','',gr.update(interactive=False)
        names={c['id']:c['description']+': '+str(c['value']) for c in checklist(engine.req(engine.store.load(tid)))}
        text=p['instructions']+'\n尽量保留：'+'；'.join(names[k] for k in p['preserve_ids'])+('\n执行：基于原图编辑\n' if p['operation']=='image_edit' else '\n执行：重新生成\n')+'；'.join(p['risk_notes'])
        for a in p['ranking']: text+='\n'+' + '.join(names[k] for k in a['target_ids'])+f"：U={a['gain']:.2f} − {a['risk']:.2f} − {a['cost']:.2f} = {a['utility']:.2f}；预计影响："+'；'.join(names[k] for k in a['affected'])
        text+='\n未纳入本轮的原因：'+'；'.join(p['deferred'])
        return text,p['plan_id'],uid(),gr.update(interactive=True)
    makeplan.click(plan,[tid,fixes,risk,correction_id,correction_status,reason],[plantext,planid,requestid,execute])
    def simple_preview(tid,allowed,note):
        try:
            if not allowed:return '请先勾选至少一个想改的地方。','','',gr.update(interactive=False),''
            t=engine.store.load(tid);e=engine.evaluation(t,t['selected_image_id'])
            saved={c['constraint_id']:c for c in t['corrections'] if e and c['evaluation_id']==e['evaluation_id']}
            changed={c['constraint_id'] for c in engine.req(t)['params'].get('feedback_change',{}).get('changes',[])}
            if any(k not in saved and k not in changed for k in allowed):return '请先逐项填写并保存优化点，再预览方案。','','',gr.update(interactive=False),''
            result=plan(tid,allowed,True)
            if not result[1]:return (*result,'')
            t=engine.store.load(tid);p=next(p for p in t['plans'] if p['plan_id']==result[1])
            names={c['id']:c['description']+': '+str(c['value']) for c in checklist(engine.req(t))}
            text='本轮一起修改：'+'；'.join(names[k] for k in p['target_ids'])
            for observation in p.get('user_observations',[]):text+='\n'+names[observation['constraint_id']]+' → '+observation['text']
            text+='\n尽量保留：'+'；'.join(names[k] for k in p['preserve_ids'])
            remaining=[names[k] for k in allowed if k not in p['target_ids']]
            if remaining:text+='\n后续再处理：'+'；'.join(remaining)
            text+=('\n执行方式：传入上一版图片及修改要求，基于原图编辑。旧图保留。' if p['operation']=='image_edit' else '\n执行方式：重新生成，旧图保留。')
            if p['ranking'][0]['utility']<=0:text+='\n注意：预计风险较高，算法建议保留当前版本。只有你仍想尝试时，才点击下方确认生成。'
            return text,result[1],result[2],result[3],result[0]
        except Exception as exc:return '暂时无法制定方案：'+str(exc),'','',gr.update(interactive=False),''
    def preview_saved(tid,allowed,cid,note):
        if cid and note.strip()!=load_tag_note(tid,cid).strip():
            return '当前这项优化点尚未保存，请先分析意见，再确认理解并保存。','','',gr.update(interactive=False),''
        return simple_preview(tid,allowed,'')
    simple_plan.click(preview_saved,[tid,fixes,problem_tag,simple_note],[plantext,planid,requestid,execute,math_detail])
    @safe
    def load_tag_note(tid,cid):
        t=engine.store.load(tid);e=engine.evaluation(t,t['selected_image_id'])
        c=next((c for c in reversed(t['corrections']) if e and c['evaluation_id']==e['evaluation_id'] and c['constraint_id']==cid),None)
        return c['reason'] if c else ''
    problem_tag.input(load_tag_note,[tid,problem_tag],simple_note).then(
        fn=None,inputs=simple_note,outputs=simple_note,
        js="(note) => {const input=document.querySelector('#pb-fix-chips input:checked');const label=input?.closest('label')?.textContent.trim();const value=note || (label ? '请在原图基础上修正「'+label+'」，使画面符合这一项要求。' : '');const count=document.querySelector('#pb-note-count');if(count)count.textContent=value.length+' 字 · 保存后才加入修改计划';return [value]}")
    @safe
    def save_tag_note(tid,cid,note,allowed):
        if not cid:raise ValueError('请先选择一个问题')
        if not note.strip():raise ValueError('请填写这一项的优化点')
        chosen=list(dict.fromkeys(list(allowed or [])+[cid]))
        save_review(tid,chosen,cid,'fail',note.strip())
        return (*refresh(tid),'已保存这一项，可继续选择下一个问题。','', '',gr.update(interactive=False))
    @safe
    def interpret_note(tid,cid,note,mode):
        p=analyze_feedback(engine,tid,note,cid,mode);v=p['interpretation']
        req=engine.req(engine.store.load(tid));cs={c['id']:c for c in checklist(req)}
        text='**'+{'correction':'纠正图片：保留原目标','change':'改变目标：更新要求与检查标准','mixed':'同时包含图片纠正和目标变更','clarify':'需要明确你的意思'}[v['intent']]+'**\n\n'+html.escape(v.get('explanation',''))
        for c in v['corrections']:text+='\n\n• 纠正「'+html.escape(cs[c['constraint_id']]['description'])+'」：'+html.escape(c['observation'])
        for c in v['changes']:
            old=cs.get(c['constraint_id']);text+='\n\n• '+html.escape(old['description'] if old else c['label'])+'：'+html.escape(str(old['value']) if old else '未指定')+' → **'+html.escape(c['value'])+'**'
        if v['intent']=='clarify':text+='\n\n'+html.escape(v['question'])+' 请在上方选择意思，再点击分析。'
        elif v['changes']:text+='\n\n确认后先按新目标检查当前图；不会立即生成图片。'
        return text,p['proposal_id'],gr.update(interactive=v['intent']!='clarify')
    feedback_outputs=[feedback_preview,feedback_id,feedback_confirm]
    for event in (save_tag.click(interpret_note,[tid,problem_tag,simple_note,feedback_mode],feedback_outputs),supplement_save.click(safe(lambda t,n,m:interpret_note(t,None,n,m)),[tid,supplement_text,feedback_mode],feedback_outputs)):
        request_feedback(event).success(fn=None,js="() => {document.querySelector('#bp-feedback-review')?.scrollIntoView({block:'center',behavior:'smooth'})}")
    @safe
    def commit_feedback(tid,pid):
        p=apply_feedback(engine,tid,pid);message='已保存图片纠正；原目标不变，可以继续记录下一项。'
        if p['interpretation']['changes']:
            t=engine.store.load(tid)
            try:
                if not engine.evaluation(t,t['selected_image_id']):recheck_feedback(engine,tid)
                current=engine.store.load(tid);ev=engine.evaluation(current,current['selected_image_id'])
                states=effective_checks(ev['checks'],evaluation_corrections(current,ev))
                message='新目标与检查标准已保存，已重新检查当前图。请预览修改方案；生成后按同一新目标比较。'
                if all(c['status']=='pass' for c in states):message='新目标与检查标准已保存。AI 重新检查后认为当前图已全部满足新目标，可直接保留，无需再生成；若判断不符，可逐项纠正。'
            except Exception as exc:message='新目标已保存，重新检查未完成：'+str(exc)+'。请点击「按当前目标重新检查图片」重试。'
        t=engine.store.load(tid)
        return (*refresh(tid),message,'',gr.update(interactive=False),'','',gr.update(interactive=False),t['prompts'][-1]['text'])
    commit_event=request_feedback(feedback_confirm.click(commit_feedback,[tid,feedback_id],outputs+[feedback_preview,feedback_id,feedback_confirm,simple_note,planid,execute,prompt]))
    for control in (simple_note,supplement_text,feedback_mode,problem_tag,version,tid):
        control.input(lambda:('',gr.update(interactive=False)),outputs=[feedback_id,feedback_confirm])
    request_feedback(feedback_recheck.click(safe(lambda t:recheck_feedback(engine,t)),tid)).then(safe(refresh),tid,outputs)

    supplement.click(lambda:gr.update(visible=True),outputs=supplement_panel)
    @safe
    def add_supplement(tid,text):
        import copy
        if not text.strip():raise ValueError('请先填写新增内容')
        with engine.store.lock:
            t=engine.store.load(tid);engine.idle(t)
            if t['revision_attempts']>=2:raise ValueError('本任务修正次数已用完；可新建任务使用新增要求')
            req=engine.req(t);cs=copy.deepcopy(req['constraints'])
            if len(cs)>=MAX_DRAFT_FIELDS:raise ValueError('当前已达64项要求，请先在构思页合并已有要求')
            cs.append(obj(id=uid(),entity_id=uid(),type='detail',description='看图后新增要求',value=text.strip(),source='user_choice',status='confirmed',strength='must',locked=False,depends_on=[],options=[],question=''))
            params=copy.deepcopy(req['params'])
            e=engine.evaluation(t,t['selected_image_id'])
            chosen=t.get('review_ui',{}).get(t['selected_image_id'],{}).get('selected',[])
            notes={c['constraint_id']:c['reason'] for c in t['corrections'] if e and c['evaluation_id']==e['evaluation_id']}
            params['revision_guidance']=[c['description']+'：'+notes[c['id']] for c in cs if c['id'] in chosen and notes.get(c['id'])]
            t=engine.confirm(tid,cs,params);t['draft']={'schema_version':1,'summary':'已添加看图后的补充','constraints':cs};engine.store.save(t)
        return '已保存：'+text.strip()+'\n\n补充已加入下一张图的提示词；点击下方按钮才会生成。原图保留。',gr.update(interactive=True),'',gr.update(interactive=False)
    supplement_generate.click(safe(lambda t:simple_preview(t,engine.store.load(t).get('review_ui',{}).get(engine.store.load(t)['selected_image_id'],{}).get('selected',[]),'')),tid,[plantext,planid,requestid,execute,math_detail]).success(lambda:gr.update(open=True),outputs=revision_panel).success(fn=None,js="() => {document.querySelector('#bp-revision-plan')?.scrollIntoView({block:'center',behavior:'smooth'})}")
    @safe
    def execute_revision(tid,rid,pid):
        if not pid:raise ValueError('请先生成并确认有效修改计划')
        return run(tid,rid,pid)
    request_feedback(execute.click(execute_revision,[tid,requestid,planid],outputs)).success(fn=None,js="() => {window.betterPrompt?.go(2)}")
    def invalidate_plan():return '选择或判断已变化，请重新计算计划。','',gr.update(interactive=False)
    for control in (fixes,risk,version,tid,correction_id,correction_status,reason,simple_note):
        control.input(invalidate_plan,outputs=[plantext,planid,execute])
    retry.click(invalidate_plan,outputs=[plantext,planid,execute])
    feedback_recheck.click(invalidate_plan,outputs=[plantext,planid,execute])
    request_feedback(retry.click(safe(lambda t:recheck_feedback(engine,t)),tid)).then(safe(refresh),tid,outputs)
    select.click(safe(engine.select),[tid,version]).then(safe(refresh),tid,outputs)
    export.click(safe(engine.export),[tid,satisfaction],download)
    load.click(safe(refresh),tid,outputs)
    from core.visual_preferences import observe,prepare
    request_feedback(observe_button.click(safe(lambda t:observe(engine,t)),tid,observations))
    @safe
    def prepare_reference(t,b,rows):return prepare(engine,t,b,rows),gr.update(interactive=True)
    ref_prepare.click(prepare_reference,[tid,ref_base,ref_choices],[ref_preview,ref_execute])
    request_feedback(ref_execute.click(safe(lambda t:run(t,uid())),tid,outputs))
    for control in (ref_base,ref_choices):control.input(lambda:gr.update(interactive=False),outputs=ref_execute)
    def resume():
        files=sorted((ROOT/'tasks').glob('*/manifest.json'),key=lambda p:p.stat().st_mtime)
        if MODE!='mock':
            files=[p for p in files if not json.loads(p.read_text()).get('draft',{}).get('summary','').startswith('模拟解析')]
        if not files:return '',[],''
        t=json.loads(files[-1].read_text()); cs=engine.req(t)['constraints'] if t['requirements'] else []
        data=[[c.get(k,'') if k!='depends_on' else ','.join(c[k]) for k in ['id','entity_id','type','description','value','source','status','strength','locked','depends_on']] for c in cs]
        return t['task_id'],data,t['prompts'][-1]['text'] if t['prompts'] else ''
    def restore_draft(tid):
        if not tid:return render_draft([])
        t=engine.store.load(tid);d=t.get('draft',{})
        if MODE!='mock' and d.get('summary','').startswith('模拟解析'):
            return render_draft([],'这是以前的模拟记录，请输入想法并调用真实接口重新分析。','error')
        return render_draft(d.get('constraints',engine.req(t)['constraints'] if t['requirements'] else []),d.get('summary',''))
    demo.load(resume,outputs=[tid,cards,prompt]).then(safe(restore_draft),tid,draft_outputs).then(safe(refresh),tid,outputs)
    load.click(safe(restore_draft),tid,draft_outputs)
    commit_event.success(safe(restore_draft),tid,draft_outputs)
