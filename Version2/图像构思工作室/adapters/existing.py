"""Compatibility wrapper around supplied project's draw/feedback functions."""
import os
from .mock import MockAdapter
class ExistingProjectAdapter:
    name='原项目云端通道（未经本机真实调用验证）'
    def __init__(self):
        for prefix in ('DRAW','GPT'):
            for key in ('BASE_URL','API_KEY','MODEL'):
                if not os.getenv(prefix+'_'+key):raise ValueError('需明确填写 '+prefix+'_'+key+'，不使用旧模型默认值')
    @property
    def supports_edit(self):return os.getenv('DRAW_MODEL')=='gemini-3.1-flash-image'
    def edit(self,prompt,req,references):
        if not self.supports_edit:raise ValueError('当前绘图通道未声明支持原图编辑')
        from legacy.app import draw
        images=[('参考图片 '+r.get('label',r['image_id'])+'，用途：'+r['role'],r['path'].read_bytes()) for r in references]
        if not images:raise ValueError('编辑请求必须包含参考图片')
        return draw(prompt,False,180,reference_images=images)
    def extract(self,text):
        from legacy.app import post,config,endpoint
        from core.intent import SYSTEM
        cfg=config('gpt')
        for key,suffix in [('base','BASE_URL'),('key','API_KEY'),('model','MODEL')]:
            cfg[key]=os.getenv('TEXT_'+suffix) or cfg[key]
        out=post(endpoint(cfg,'/chat/completions'),cfg['key'],{'model':cfg['model'],'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':text}],'temperature':0.2},120)
        return out['choices'][0]['message']['content']
    def analyze_feedback(self,context):
        import json
        from core.feedback import SYSTEM
        from legacy.app import post,config,endpoint
        cfg=config('gpt')
        for key,suffix in [('base','BASE_URL'),('key','API_KEY'),('model','MODEL')]:cfg[key]=os.getenv('TEXT_'+suffix) or cfg[key]
        result=post(endpoint(cfg,'/chat/completions'),cfg['key'],{'model':cfg['model'],'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(context,ensure_ascii=False)}],'temperature':0.1},120)
        return result['choices'][0]['message']['content']
    def generate(self,prompt,req,index):
        from legacy.app import draw
        try:return draw(prompt,False,120)
        except Exception:raise RuntimeError('原项目绘图接口调用失败；无自动重试，请检查配置与服务端日志') from None
    def evaluate(self,path,req,index):
        from legacy.app import feedback
        from core.engine import checklist
        try:
            result,meta=feedback('gpt',req['summary'],[{'id':c['id'],'text':c['description']+': '+str(c['value'])} for c in checklist(req)],path.read_bytes(),False,120)
            return [{'constraint_id':c['id'],'status':c['status'],'evidence':c['evidence']} for c in result['checks']]
        except Exception:raise RuntimeError('原项目评价接口调用或格式校验失败；图片已保留') from None
