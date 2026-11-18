# 上传到 GitHub

1. 解压 `genai-feedback-github.zip`，打开其中的 `genai-feedback` 文件夹。
2. 在 GitHub 新建仓库，例如 `genai-feedback`；练习或暂未准备公开时选 Private。
3. 使用 Add file → Upload files，上传这个文件夹里面的文件和子目录，使 `README.md` 与 `app.py` 直接位于仓库根目录。
4. 提交说明可填：`添加多模型图像反馈实验代码与使用说明`。
5. 确认首页显示 README，且能看到 `requirements.txt` 和 `examples/`。

macOS Finder 使用 Command + Shift + . 显示隐藏文件，确保 `.gitignore`、`.gitattributes`、`.env.example` 也被上传。

不要上传原始 `project.zip`。原包包含本机 `.env`、虚拟环境及实验归档。整理包已物理排除这些文件；`.gitignore` 用于之后的 Git 操作，不能代替对网页手动上传文件的检查。

发布包未附带实验结果、DOCX 和旧快照。如需发布实验数据，建议单独整理，并明确数据来源、许可和评测协议。
