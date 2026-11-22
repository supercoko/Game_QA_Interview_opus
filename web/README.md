# 游戏测试面试资料库

网站读取 `Neon分析/` 和 `方案/` 中列在 `build.py` 的 14 篇 Markdown。原文是内容来源，修改后重新构建即可同步到网页。纳入范围的文档会互相链接，工具和分析报告的引用指向 GitHub。

## 本地预览

从仓库根目录运行以下命令，需要 Python 3.10 或更新版本。

```powershell
python -m pip install -r web/requirements.txt
python web/build.py
```

双击 `web/index.html` 即可浏览。生成的文章和搜索索引也位于 `web/`，由 GitHub Actions 在部署时重新生成。需要加入新文档时，更新 `build.py` 的 `DOCUMENTS`。

## GitHub Pages

仓库 Pages 的发布源设为 **GitHub Actions**。推送 `master` 上的网页、资料或工作流改动时，`Deploy interview guide to GitHub Pages` 会构建并部署。也可以在 **Actions** 中从 `master` 手动运行。

站点地址为 [游戏测试面试资料库](https://supercoko.github.io/Game_QA_Interview_opus/)。
