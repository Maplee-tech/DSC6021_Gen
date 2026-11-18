import copy
from core.engine import obj,uid,now
from adapters import reference

def pair(w,tid):
    t=w.store.load(tid)
    if len(t['images'])<2:raise ValueError('至少需要两个图像版本')
    a=next(i for i in t['images'] if i['image_id']==t['selected_image_id']);b=t['images'][-1]
    if a['image_id']==b['image_id']:
        a=next((i for i in t['images'] if i['image_id']==b['parent_image_id']),t['images'][-2])
    return t,a,b

def observe(w,tid):
    with w.store.lock:
        t,a,b=pair(w,tid);w.idle(t)
        if len(t['attempts'])>=t['operation_limit']:raise ValueError('模型调用额度已用完')
        aid=uid();t['attempts'].append(obj(attempt_id=aid,request_id=uid(),kind='visual_compare',state='running',started_at=now(),finished_at=None,latency=None,usage=None,error=None));w.store.save(t)
    try:
        result=reference.compare(w.store.folder(tid)/a['path'],w.store.folder(tid)/b['path'])
        with w.store.lock:
            t=w.store.load(tid);t.setdefault('visual_observations',[]).append(obj(base_id=a['image_id'],candidate_id=b['image_id'],differences=result,created_at=now()));next(x for x in t['attempts'] if x['attempt_id']==aid).update(state='succeeded',finished_at=now());w.store.save(t)
        return [[r['dimension'],r['a'],r['b']] for r in result]
    except Exception:
        with w.store.lock:
            t=w.store.load(tid);next(x for x in t['attempts'] if x['attempt_id']==aid).update(state='failed',error='双图观察失败，未伪造变化或自动重试',finished_at=now());w.store.save(t)
        raise ValueError('双图观察失败；可以手动填写偏好，或检查视觉模型接口后重试') from None

def prepare(w,tid,base_label,rows):
    if not getattr(w.adapter,'supports_edit',False) and not reference.configured():raise ValueError('尚未配置参考图编辑接口，请先填写 .env 中 REFERENCE_EDIT_*；不会以文生图冒充参考图编辑')
    with w.store.lock:
        t=w.store.load(tid);w.idle(t)
        if t['revision_attempts']>=2:raise ValueError('两次修正机会已用完；保存旧版仍可导出')
        by_label={i['label']:i for i in t['images']}
        if base_label not in by_label:raise ValueError('基础版本不存在，请填写V0、V1等实际版本名')
        preferences=[]
        for row in rows:
            dimension,label,description=[str(x or '').strip() for x in row]
            if not dimension and not label and not description:continue
            if label not in by_label or not dimension or not description:raise ValueError('每行需填写特征、参考版本和希望保留的描述')
            if any(p['dimension']==dimension for p in preferences):raise ValueError('同一特征只能选择一个参考版本')
            preferences.append({'dimension':dimension,'reference_image_id':by_label[label]['image_id'],'reference_label':label,'description':description})
        if not preferences:raise ValueError('请至少确认一项视觉偏好')
        base=by_label[base_label];req=next(r for r in t['requirements'] if r['requirement_id']==base['requirement_id']);cs=copy.deepcopy(req['constraints'])
        mapping={'灯光':['lighting'],'空间感':['spatial_density'],'构图':['composition'],'色调':['color_palette']}
        for p in preferences:
            for c in cs:
                if c['type'] in mapping.get(p['dimension'],[]) or c['description']==p['dimension']:c['status']='pending'
            cs.append(obj(id=uid(),entity_id=uid(),type='detail',description='版本偏好：'+p['dimension'],value='参照'+p['reference_label']+'：'+p['description'],source='user_choice',status='confirmed',strength='must',locked=False,depends_on=[]))
        params=copy.deepcopy(req['params']);params.update(base_reference_id=base['image_id'],visual_preferences=preferences,reference_ids=list(dict.fromkeys([base['image_id']]+[p['reference_image_id'] for p in preferences])))
        t=w.confirm(tid,cs,params);t['selected_image_id']=base['image_id'];t['draft']={'schema_version':1,'constraints':cs,'summary':'已确认跨版本视觉偏好'};w.store.save(t)
        return '基础图：'+base_label+'。保留基础图已完成的修改，仅按以下偏好编辑：\n'+'\n'.join(p['dimension']+' ← '+p['reference_label']+'：'+p['description'] for p in preferences)+'\n将传入参考图片；无法保证像素级保真。新目标不与旧评价直接计算G/R。'
