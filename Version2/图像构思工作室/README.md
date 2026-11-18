# 图像构思工作室

Python + Gradio 本地单用户应用。默认 MOCK，无网络模型调用，不是实际生成式绘画。

## 本机启动

用 VS Code 打开整个文件夹，按 F5 选择“启动图像工作室”，或在终端执行：

```sh
.venv/bin/python app.py
```

浏览器打开 http://127.0.0.1:7860 。也可双击 `启动.command`。停止：终端 Ctrl+C。
如重新安装：`python3 -m venv .venv`，再执行 `.venv/bin/python -m pip install -r requirements.txt`。

## 操作

1. 输入想法，创建任务。原文保存在任务中。
2. 选择场景、风格，点击“将卡片选择写入需求”。高级表可编辑要求的来源、确认状态、必须/偏好/自由、锁定、实体及依赖。
3. 确认需求，检查自动生成提示词，生成初图。
4. 查看评价，纠正 AI 判断，勾选修改项，预览包含 U 值分解的计划后执行。
5. 比较 G/R 与不确定项，明确采用某个版本。默认不自动采用候选。
6. 第二轮可以从任何保留版本开始；全任务只有两次修正请求机会，失败也计数。
7. 导出选定图像、实际提示词、对应需求及修改记录。

刷新恢复最近任务；任务 ID 可以保存后再次加载。需求修改需新确认，创建新需求版本。不同需求不直接比较。卡片改动在确认前尚未保存，标签选择在生成计划前尚未保存。

## 三个本地算法

实现：`core/engine.py`。配置：`algorithm_config.json`。

- `validate_constraints`：同实体单值冲突、无效依赖、Kahn 拓扑排序和循环检测。没有人为补充评分公式。自然语言必须先规范化实体和类型；高级表可修正。
- `rank_actions`：U(a)=Σ w_i e_i − λΣ w_j − μC(a)。收益、风险、代价分别保存在 ranking 中。默认 must=3、preference=1、用户确认错误=1、AI 判错=.6、λ=.5、μ=.1、调用单位=1。当前每轮选一个目标，避免不兼容多目标；局部动作影响同实体及直接依赖，全局动作影响全部已满足要求。uncertain 不自动修正，用户纠错优先。
- `compare_versions`：G=Σw_i·1[fail→pass]，R=Σw_i·1[pass→fail]。不确定单列，同需求同 rubric 完整对齐后才可比较。推荐不修改用户选择。

参数是启发式起点，不是经过实验证实的最优值。

## 真实接口

复制 `.env.example` 为 `.env`，自行填写服务端密钥。不要提交 `.env`。

- `STUDIO_MODE=existing`：复用原项目的 `draw` 和 `feedback`，需显式填写 DRAW、GPT 的 BASE_URL/API_KEY/MODEL。旧默认模型 ID 不作为验证依据。原项目支持的协议受 `legacy/app.py` 限制；原图 edit 未实现，始终提前告知重新生成。真实接口未调用验证。
- `STUDIO_MODE=gateway`：自定义 HTTPS JSON 网关，POST `/generate` 接收 model/prompt/params，返回 image_base64；POST `/evaluate` 接收 model/image_base64/checklist/rubric_version，返回 checks（constraint_id/status/evidence）。用于接入其它供应商。
- `STUDIO_MODE=mock`：固定演示图与评价夹具，mixed 展示修复同时引入退化；pass 全通过；uncertain 全不确定；invalid 触发格式错误并保留图片。

配置检查 `python app.py --check-config` 不表示连通性验证。本次交付没有读取旧密钥，没有发起真实付费调用。

## 目录与保存

`legacy/` 保留原 app.py/ui.py；`formal/` 保留实验工具。主入口不启动多模型实验。
`core/engine.py` 是数据、存储、算法及状态机；`adapters/` 隔离外部调用；`ui.py` 为三阶段界面。
`tasks/<id>/manifest.json` 原子保存任务，requirements/prompts/evaluations 保存不可变历史副本，images 保存 PNG。锁覆盖检查和调用预留，网络期间不占锁。重复 request_id 不重发；重启中断请求标 unknown 并保留预算。
对象带 schema_version；时间为带时区 UTC。manifest 中包含 requirements/prompts/images/evaluations/corrections/plans/attempts/comparisons/satisfaction 数组。原始评价与用户纠错分开保存。

## 验证与当前限制

运行 `.venv/bin/python -m unittest discover -s tests -v`。
自动测试覆盖公式手算、冲突/依赖、完整评价校验、双请求幂等、两轮额度、回退基准、退化不自动采用、失败与重启、导出一致性。浏览器实测：创建任务、确认、V0、评价、计划 U 分解、V1、G=3/R=3、旧版仍被选择、ZIP 导出。

这是可运行的第一版，尚未达到文档全部验收：需求解析已接入配置的文本模型，动态生成卡片和澄清选项；真实解析效果仍需结合服务商模型验证；最终提示词从需求生成，不允许绕过需求直接改写；没有区域编辑；需求详情仍使用表格；没有独立 events.jsonl；没有多进程并发支持；不确定冲突的语义识别、窄屏及保存失败 UI 专项尚未验证。真实云端接口需要用户的有效服务配置后进行授权联调。请不要把 MOCK 测试结果用于模型效果研究。

## AI 需求解析更新

开始构思会先调用文本模型，再将返回的 fields、options、question 显示为卡片；不是本地预填建议。默认复用 GPT_BASE_URL/GPT_API_KEY/GPT_MODEL，也可通过 TEXT_BASE_URL/TEXT_API_KEY/TEXT_MODEL 单独配置文本模型。原始 prompt 完整发送并保存。模型建议默认待确认，接受或自定义后才进入固定清单。每次解析计入调用额度，失败无自动重试，无本地规则兜底；可点击重试 AI 解析。确认前会自动保存当前卡片选择。


## Latest interaction update

New real-model drafts request 12-18 question cards (target 15), each with three AI options. The UI provides A/B/C and D for custom input, with optional skipping. Existing tasks keep their original drafts.

Multiple selected problems now form a joint revision action. Benefits sum across targets; risk uses the union of affected passed constraints; generation cost is counted once. Failed prerequisites outside the selection defer dependent targets. The two-attempt task limit still applies. This supersedes earlier single-target descriptions.

The simplified review flow is: select problems, optionally describe the desired correction, preview the plan, then explicitly confirm generation. Math and manual correction controls remain in advanced details.

Validation: 42 unit tests passed; a separate mock UI callback test covered 15 ABCD cards, custom input, skipped constraints, and multi-target preview. No paid API calls were made.
