# CourseBrief

[English](README.md) | **简体中文**

CourseBrief 从课程文档中抽取学术任务，并以月历和周视图展示。当前版本是本地原型：固定评估集、gold 和评估脚本已经实现；2026-11-15 已生成一次 live 评估报告，三项指标在该固定评估集上均通过。

## 快速开始

1. 安装 Python 3.11+ 和运行依赖：

   ```bash
   python -m pip install -r requirements.txt
   ```

2. 复制 `apikey.env.example` 为 `apikey.env`。选择 `LLM_PROVIDER=deepseek` 或 `qwen`，填写 `LLM_API_KEY`。密钥只放在这个被忽略的文件中；提交的 `.env` 只包含非敏感的模型、学期和应用配置。
3. 启动应用：

   ```bash
   python run.py
   ```

   浏览器会打开 `http://127.0.0.1:32922`；修改 `.env` 中的 `PORT` 可以换端口。修改配置或 Python 代码后需要重启服务。
4. 点击 **Upload** 上传 PDF、DOCX、TXT 或 Markdown，或使用 **Paste** 粘贴文本。等待抽取完成。失败的记录会单独显示，并提供 **Retry extraction** 按钮。解析失败需要修正文件后重新上传；重试抽取不能修复损坏或扫描版文档。

离线开发时，在 `.env` 中设置 `EXTRACTOR_MODE=mock`。mock 模式每次上传只生成一条启发式任务，不能用来衡量抽取质量。

## 阅读日历

- 点击日期进入该周。任务卡片显示优先级徽标；同一天的任务保持存储顺序。
- 打开任务并点击 **Show source** 查看来源引文，或打开完整抽取文本。重复上传可以共享同一个展示任务，但保留各自的来源。
- **No confirmed deadline** 表示任务已经抽取，但截止日期无法确认。标签区分 TBA、缺少日期和需要复核的日期。点击这类任务会在上传周打开详情；日历中的日期是导入日期，不是截止日期。
- 位于 **No confirmed deadline** 区域的任务，详情中有 **Delete** 按钮。删除需要二次确认，只删除抽取出的任务；上传原文和文本仍保存在 `data/` 中。
- 估算日期范围显示在起始日，并保留 estimated 标记。

## 数据与隐私

结构化上传记录、任务和重复分组保存在 `data/db.json`；抽取文本和原始文件保存在 `data/texts/` 和 `data/originals/`。备份时复制整个 `data/` 目录。`db.json.bak` 保存最近一次成功写入前的状态。

文件保存在本机。live 抽取会把文档文本和相关上下文发送给配置的 LLM 端点。请使用合适的测试材料，并在依赖某个截止日期前核对来源。应用不访问大学账号，也不提交作业。

## 正式评估

固定评估集和评估脚本位于 `eval/`，这是仓库自带的测试/评估资产，也是项目对外的评估入口：

- `eval/gold.json`：8 篇计分文档、32 条任务，其中两篇是真实的 COMP2119 作业 handout，另含 3 篇歧义观察文档；
- 每份文档内部按归一化标题做一对一贪心匹配，相似度阈值为 `0.8`；较短标题是较长 `名称 - 副标题` 标题的完整词前缀时也算匹配；
- 指标：抽取 precision/recall、截止日期准确率、课程归属；
- 通过线：precision/recall ≥ 90%（至少 29/32），日期 ≥ 90%（至少 29/32），课程 ≥ 95%（至少 31/32）；
- 3 篇观察文档只记录系统输出，不做 hard-fail 判定。

评估集已于 2026-11-15 更新为 `eval-v2`：两篇合成 COMP3230 文档替换为真实的 COMP2119 作业 handout，Game House 观察文档也换成真实 handout。最近一次本地 live 运行（`deepseek-chat`，prompt v2）32/32 任务匹配，precision/recall、截止日期准确率和课程归属均为 100%。

两个命令都必须在**项目根目录**运行，也就是包含 `run.py` 的文件夹。

只校验评估集，不调用模型：

```bash
python eval/run_eval.py --check
```

也可以直接双击 `eval/run_eval.py`；它会执行默认的 `--check`。控制台可能在结束后关闭，想查看完整输出请在终端运行。

运行 live 评估，需要 `EXTRACTOR_MODE=live` 和已配置的 `LLM_API_KEY`：

```bash
python eval/run_eval.py --live
```

`--check` 只打印逐文档校验表和检查清单，不写文件。`--live` 会打印逐文档、逐指标的结果表，再把 `report.md` 和 `report.json` 写到本机 `data/eval_reports/<timestamp>/`；该目录被 Git 忽略，不进入仓库。live 运行会调用约 11 次模型，报告包含每篇文档的匹配数、false positives/negatives、near-miss 和总体指标。退出码：`0` 达标，`1` 未达标，`2` 配置、数据或 API 错误。

`--check` 只验证数据，不代表模型准确率；准确率只能由 live 评估报告给出。
