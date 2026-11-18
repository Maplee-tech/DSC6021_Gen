import io
from PIL import Image, ImageDraw
class MockAdapter:
    name='MOCK · 固定夹具，非真实识图'
    def extract(self,text):
        return {'summary':'模拟解析（非大模型输出）','fields':[{'id':'f1','entity_id':'scene','type':'subject','label':'原始想法','value':text,'source':'user_input','evidence':text,'strength':'must','options':[],'question':'','depends_on':[]},{'id':'f2','entity_id':'scene','type':'scene','label':'场景（模拟建议）','value':'室内','source':'model_suggestion','strength':'preference','options':['室内','室外','室内外结合'],'question':'场景更偏哪一种？','depends_on':[]}]}
    def generate(self,prompt,req,index):
        im=Image.new('RGB',(960,640),'#101b31'); d=ImageDraw.Draw(im)
        for x in range(90,850,170):
            d.rectangle((x,180,x+135,510),fill='#263956',outline='#68dfd0',width=3)
            for y in range(220,500,65):
                d.line((x,y,x+135,y),fill='#92a1b5',width=3)
                for k in range(7): d.rectangle((x+8+k*17,y-28,x+18+k*17,y-3),fill=['#a4cbc4','#d49d95','#c9bb88'][k%3])
        d.text((70,55),'MOCK DEMO / VERSION '+str(index),fill='white',font_size=30)
        d.text((70,110),'Placeholder illustration - not AI generated',fill='#9cabbf',font_size=22)
        for x in ([360,480,600] if index==0 else [400,560]): d.ellipse((x,450,x+35,485),fill='#e6b9a0'); d.rectangle((x,485,x+35,580),fill='#7e84df')
        b=io.BytesIO(); im.save(b,'PNG'); return b.getvalue(),{'mock':True,'actual_size':[960,640]}
    def evaluate(self,path,req,index):
        from core.engine import checklist
        mode=req['params'].get('mock_scenario','mixed'); cs=checklist(req); out=[]
        for n,c in enumerate(cs):
            status='pass' if mode=='pass' else ('uncertain' if mode=='uncertain' else ('fail' if (index==0 and n==0) or (index==1 and n==1) else 'pass'))
            out.append({'constraint_id':c['id'],'status':status,'evidence':'模拟固定夹具：'+status+'。该结果用于验证流程，不是对图片的真实判断。'})
        return out[:-1] if mode=='invalid' else out
