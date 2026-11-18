# 配置说明

四个角色各有 `BASE_URL`、`API_KEY`、`MODEL`，允许使用不同服务商。示例地址和模型名均为占位符。不要将真实密钥写进源码。

## 代码中的接口选择

| 角色或模型名称 | 当前请求方式 |
| --- | --- |
| GPT / DeepSeek 反馈 | `BASE_URL + /chat/completions`，发送多模态消息 |
| Gemini 反馈 | 原生 `v1beta/models/{model}:generateContent` |
| 绘图模型名以 `gpt-image-` 开头 | `BASE_URL + /images/generations` |
| 绘图模型名以 `gpt-` 或 `chat-` 开头，且不是 `gpt-image-` | `/responses`，请求 `image_generation` 工具 |
| 绘图模型名以 `gemini-` 开头且包含 `image` | 原生 `generateContent`，请求图像输出 |

以上描述本项目代码行为，不保证任何服务商支持对应协议。`DRAW_MODEL` 的实际名称必须符合适配器的路由条件；其他命名需修改适配器。

普通兼容接口的 `BASE_URL` 应包含所需路径前缀，例如 `/v1`，但不要再添加 `/chat/completions`。Gemini 适配器会去除末尾 `/v1`，再添加 `/v1beta/models/...`，因此不要预先填写 `/v1beta`。

`DRAW_TOOL_MODEL` 只用于 Responses 绘图工具路径。`IMAGE_SIZE` 和 `IMAGE_QUALITY` 在 images/generations 路径中发送；当前 Gemini 和 Responses 绘图路径没有发送这两个参数，不应把配置值视为实际请求或输出尺寸。

## 常见问题

- 配置显示未填写：检查 `.env` 位置，替换 `YOUR_` 占位符后重新启动程序。
- HTTP 错误：按服务商响应检查地址、权限、余额以及模型是否支持图像输入。
- 返回文本但没有图片：确认绘图通道支持对应接口或工具。
- 反馈解析失败：检查原始响应是否包含完整检查项、合法状态及非空 `revised_prompt`。
- 初图失败：查看 `manifest.json` 的 `initial_error`；该任务不会继续执行反馈分支。

运行记录可能包含用户需求、图像和服务商响应，默认不纳入版本控制。发布实验记录前应单独检查其内容。
