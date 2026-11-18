# Gemini 原生编辑（优先路径）

DRAW_MODEL=gemini-3.1-flash-image 时，直接复用 DRAW_BASE_URL、DRAW_API_KEY，不需要 REFERENCE_EDIT_*。
修改请求会把选中的上一版 PNG 作为 inlineData，与修改文字一起提交到现有 Gemini generateContent 通道。跨版本偏好也通过同一通道传入对应参考图，并标注 V0/V1 及用途。失败不会自动重试或改发纯文生图。
下方网关仅保留为其他服务的可选适配方式。

# 参考图编辑接口

在 `.env` 新增三个字段（不修改现有密钥）：

```dotenv
REFERENCE_EDIT_URL=https://你的网关/完整编辑端点
REFERENCE_EDIT_MODEL=你的编辑模型ID
REFERENCE_EDIT_API_KEY=你的密钥
```

这是本应用定义的 HTTPS JSON 网关协议，不是任意供应商端点都支持。若供应商提供 multipart、原生多模态或其它编辑协议，需在 adapters/reference.py 中新增对应转换，或由你自己的网关转换。尚未进行真实服务联调，不应直接把普通生图 URL 填在此处。

POST 请求（Bearer 鉴权）：

```json
{
  "model": "编辑模型ID",
  "prompt": "确认需求和参考用途说明",
  "base_image_id": "V1对应的内部ID",
  "references": [
    {"image_id":"内部ID", "role":"base", "image_base64":"PNG字节的base64"},
    {"image_id":"内部ID", "role":"feature_reference", "image_base64":"PNG字节的base64"}
  ],
  "preferences": [
    {"dimension":"空间感", "reference_image_id":"内部ID", "reference_label":"V0", "description":"空间更紧凑"}
  ]
}
```

成功响应：`{"image_base64":"输出图像base64", "model":"可选实际返回模型名"}`。
应用检查图片可解码、保存哈希。失败不重试、不降级为文生图，尝试仍计入两轮上限。模型调用总额度也继续生效。

比较页新增双图变化观察（复用 GPT 视觉接口），以及可编辑的视觉偏好表。默认不选任何偏好，用户自行确定保留哪版。可以不调用观察模型而直接填写偏好。新偏好建立新需求版本，旧评价不与新目标计算G/R。当前只允许引用本任务已记录的图片，未提供任意文件路径输入。

限制：尚未自动为每个V0预先建立特征档案；双图观察由用户点击触发。特征替换采用有限的维度映射，复杂语义冲突仍需人工核对。参考图编辑不能保证像素级保真。
