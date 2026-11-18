"""Explicit reference-image gateway; no automatic fallback or retries."""
import os,base64,json
from urllib.request import Request,urlopen

def configured():return bool(os.getenv('REFERENCE_EDIT_URL') and os.getenv('REFERENCE_EDIT_MODEL') and os.getenv('REFERENCE_EDIT_API_KEY'))
def edit(prompt,req,references):
    if not configured():raise ValueError('请配置 REFERENCE_EDIT_URL / MODEL / API_KEY')
    url=os.environ['REFERENCE_EDIT_URL']
    if not url.startswith('https://'):raise ValueError('参考图接口必须使用HTTPS')
    payload={'model':os.environ['REFERENCE_EDIT_MODEL'],'prompt':prompt,'base_image_id':req['params']['base_reference_id'],'references':[{'image_id':i['image_id'],'role':i['role'],'image_base64':base64.b64encode(i['path'].read_bytes()).decode()} for i in references],'preferences':req['params']['visual_preferences']}
    request=Request(url,json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['REFERENCE_EDIT_API_KEY']})
    try:
        with urlopen(request,timeout=180) as response:out=json.load(response)
        return base64.b64decode(out['image_base64'],validate=True),{'operation':'reference_edit','reference_ids':[i['image_id'] for i in references],'response_model':out.get('model')}
    except Exception:raise RuntimeError('参考图编辑失败或超时；未自动降级或重试，已计入请求次数') from None

def compare(a,b):
    from legacy.app import post,config,endpoint
    cfg=config('gpt')
    instruction='比较图片A与图片B。只报告可见变化，不评价好坏，不推断用户偏好。返回JSON：{"differences":[{"dimension":"灯光/空间感/人物外观/构图/色调/其他具体维度","a":"A的可见特征","b":"B的可见特征"}]}。最多8项；无法确认就明确写不确定。'
    content=[{'type':'text','text':instruction}]
    for p in (a,b):content.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()}})
    out=post(endpoint(cfg,'/chat/completions'),cfg['key'],{'model':cfg['model'],'messages':[{'role':'user','content':content}],'temperature':0},120)
    import re
    raw=out['choices'][0]['message']['content'];result=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()))['differences']
    if not isinstance(result,list) or len(result)>8 or any(not isinstance(r,dict) or any(not isinstance(r.get(k),str) or not r[k].strip() for k in ('dimension','a','b')) for r in result):raise ValueError('双图观察返回格式错误')
    return result
