"""Explicit generic JSON HTTP gateway. No inferred capabilities or automatic retry."""
import os,json,base64
from urllib.request import Request,urlopen
class GatewayAdapter:
    name='配置的 JSON 网关'
    def __init__(self):
        self.base=os.getenv('STUDIO_GATEWAY_URL','').rstrip('/'); self.key=os.getenv('STUDIO_API_KEY',''); self.model=os.getenv('STUDIO_MODEL','')
        if not all((self.base,self.key,self.model)): raise ValueError('真实模式需要配置网关地址、密钥及模型 ID')
        if not self.base.startswith('https://'): raise ValueError('网关需使用 HTTPS')
    def call(self,kind,payload):
        req=Request(self.base+'/'+kind,data=json.dumps(dict(model=self.model,**payload)).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=120) as r: return json.load(r)
        except Exception: raise RuntimeError('网关调用失败或超时；未自动重试，请检查服务端日志。') from None
    def extract(self,text):
        from core.intent import SYSTEM
        return self.call('extract',{'text':text,'instructions':SYSTEM})
    def analyze_feedback(self,context):
        from core.feedback import SYSTEM
        return self.call('extract',{'text':json.dumps(context,ensure_ascii=False),'instructions':SYSTEM})
    def generate(self,prompt,req,index):
        out=self.call('generate',{'prompt':prompt,'params':req['params']}); return base64.b64decode(out['image_base64'],validate=True),{'response_model':out.get('model'),'configured_model':self.model}
    def evaluate(self,path,req,index):
        from core.engine import checklist
        return self.call('evaluate',{'image_base64':base64.b64encode(path.read_bytes()).decode(),'checklist':checklist(req),'rubric_version':'1'})['checks']
