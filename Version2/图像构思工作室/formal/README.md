# 原正式实验脚本

此目录保留原项目脚本，不包含原始运行数据。主项目的 mock 和网页入口不依赖此目录。

| 脚本 | 作用与依赖 |
| --- | --- |
| `prepare.py` | 从原 DOCX 提取 T01–T10，每条 C1–C8；依赖 `SOURCE` 指定文档及 `snapshots/freeze.json` |
| `run_formal.py` | 校验模型、地址、提示词及版本与冻结配置一致；执行前需 `batch_input.json` 和真实配置 |
| `launch_audited.py` | 包装正式运行并记录 HTTP 请求体与响应；需先创建 `audit/` |
| `verify_run.py` | 核验已有正式数据，需要 `batch_input.json` 和 `data/` |
| `package_blind.py` | 创建匿名图片及私有映射，需要批输入、图片和评分模板 |
| `summarize_run.py` | 原实验专用汇总，含固定请求数断言及固定结果叙述，不可直接用于新实验 |

使用前须调整 `prepare.py` 的 `SOURCE` 和 `summarize_run.py` 的 `O` 绝对路径，补齐原始材料及冻结配置。当前没有自动生成冻结配置的通用入口。

`run_formal.py` 默认只预检，但预检也要求这些文件和配置存在；传入 `--start-paid` 才发起正式 API 请求。不要在尚未理解输入和成本时启用该参数。

`summarize_run.py` 中的原实验统计是历史脚本内容，不是本发布包重新验证的结果。任何新实验都应重新计算统计并重写对应汇总逻辑。

原实验快照、匿名映射、图片和审核文件没有随此次代码整理发布；原始压缩包保持不变。
