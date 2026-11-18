import unittest,io,json,base64
from unittest.mock import patch
from PIL import Image
from legacy.app import draw
class NativeEdit(unittest.TestCase):
 def test_image_and_text_share_one_request(self):
  b=io.BytesIO();Image.new('RGB',(32,32),'blue').save(b,'PNG');raw=b.getvalue()
  response={'candidates':[{'content':{'parts':[{'inlineData':{'data':base64.b64encode(raw).decode(),'mimeType':'image/png'}}]}}]}
  with patch('legacy.app.config',return_value={'base':'https://example.test/v1','key':'test','model':'gemini-3.1-flash-image'}),patch('legacy.app.request.urlopen') as call:
   call.return_value.__enter__.return_value=io.BytesIO(json.dumps(response).encode())
   result,meta=draw('change square to blue',False,10,reference_images=[('base',raw)])
   payload=json.loads(call.call_args.args[0].data);parts=payload['contents'][0]['parts']
   self.assertEqual(parts[0]['text'],'change square to blue');self.assertEqual(base64.b64decode(parts[2]['inlineData']['data']),raw)
   self.assertEqual(meta['operation'],'image_edit');self.assertEqual(meta['reference_count'],1);self.assertTrue(result)
