# DSC6021 · 图像构思工作室

围绕图像生成的需求澄清、反馈修正与版本比较构建的 Python / Gradio 项目。保留两个开发版本、实验结果及课程汇报材料。

## 推荐入口

当前版本位于 `Version2/图像构思工作室/`。`Version1/project/genai_feedback/` 保留早期多模型反馈实验，二者配置与运行方式应分别查看各自 README。

```bash
cd 'Version2/图像构思工作室'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python app.py
```

服务默认地址为 http://127.0.0.1:7860。真实服务需要在本机 `.env` 填写配置；密钥不包含在仓库中。MOCK 演示不能作为真实模型效果证据。界面与接口说明见该版本 README。

## 内容索引

- `Version2/`：当前应用、算法、适配器、测试、前端和文档。
- `Version1/`：早期原型及正式实验材料。
- 根目录 DOCX / PPTX：课程讲稿和汇报材料。

## 整理说明

保留原有目录以兼容相对路径。排除环境、缓存、私密配置、本地任务会话、原始 API 审计缓存和 ZIP 打包副本。实验汇总和结果文件保留。此轮整理不调用付费接口。
