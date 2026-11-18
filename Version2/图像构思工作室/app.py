from pathlib import Path
import os
os.chdir(Path(__file__).resolve().parent)
from dotenv import load_dotenv
load_dotenv(override=True)
# Preserve imports used by the supplied formal experiment scripts.
from legacy.app import run, BRANCHES, config, configured
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('--check-config',action='store_true'); args=p.parse_args()
    mode=os.getenv('STUDIO_MODE','existing')
    if mode not in ('existing','gateway'):
        raise ValueError('正式程序只使用真实接口。请将 .env 中 STUDIO_MODE 设为 existing 或 gateway；不会回退为模拟数据。')
    if args.check_config:
        mode=os.getenv('STUDIO_MODE','existing'); print('通道:',mode)
        print('仅检查配置完整性，不代表接口连通或能力验证。')
        if mode not in ('mock','gateway','existing'): raise ValueError('STUDIO_MODE 必须为 mock/gateway/existing')
        if mode=='existing':
            from adapters.existing import ExistingProjectAdapter
            ExistingProjectAdapter(); print('绘图与评价的必需字段完整；尚未联网验证')
        if mode=='gateway':
            from adapters.provider import GatewayAdapter
            GatewayAdapter(); print('必需配置完整')
    else:
        from ui import demo
        demo.queue().launch(server_name='127.0.0.1',server_port=None,inbrowser=False,allowed_paths=[str(Path('tasks').resolve())])
