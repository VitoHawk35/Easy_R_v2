# task-E7 交付说明

## 任务ID / 分支 / 基线提交

- 任务 ID：`task-E7`（Easy_R_v2 设计文档，📐 只出方案）
- 分支：`docs/E7-proposals`
- 基线提交：`origin/main@9332500`（`9332500ccbe9d07bf11c8d5e17b0914565b168dd`）
- 工作目录：`D:\agent-workspace\worktrees\task-E7`

## 交付文档清单

| 文档 | 路径 |
|---|---|
| E7a 嵌套 CV | `docs/proposals/E7a-嵌套CV.md` |
| E7b 指标修正 | `docs/proposals/E7b-指标修正.md` |
| E7c EPV 与 TRIPOD+AI | `docs/proposals/E7c-EPV与TRIPOD.md` |
| E7d ECharts 迁移 | `docs/proposals/E7d-ECharts迁移.md` |

每份文档均包含：现状（文件:行号证据）→ 目标做法（统计/工程依据）→ 对 API 和向导 UI 的影响 → 实现工作量估算 → 风险与回退方案 → 🧑‍⚖️ 待用户拍板的决策点。

## 每份文档关键结论（3 行以内）

- **E7a**：现有"筛选服务 + 把 final 变量传给模型"等价于用全样本结局选变量，下游 CV 指标带选择性乐观偏倚；应把筛选封装成 sklearn Transformer 放进 Pipeline，外层重复 CV、内层调参，形成嵌套 CV；建议先做 LR/LASSO/Boruta + 稳定性表（MVP 6–8 人日），ALR/CLR 需拆分确定性变换与有监督筛峰（完整 12–16 人日）。
- **E7b**：Youden 界值与评估共用 OOF（`metrics.py:84-87`）、重复间 CI 用 `SD/√R`（`metrics.py:116-117`）、KNN 在测试集选 K（`knn_service.py:38-44`）、Logistic 用 OLS 帽子矩阵（`adv_diag_service.py:50-52`）、Cox 只报训练集表观 C-index 且无 PH 检验（`cox_service.py:38-70`）；建议统一改为"选择/评估分离 + 患者级 Bootstrap/DeLong + GLM 影响度量 + 测试集 C-index/Schoenfeld 检验"，约 21–28 人日，可先做 B1–B3。
- **E7c**：全仓无 EPV/TRIPOD/DeLong/NRI/IDI/BH-FDR/Firth/class_weight/ICI 等实现；建议增加分析质量层（EPV/Riley 预警、BH-FDR、校准扩展、DeLong+Holm、NRI/IDI、DCA 带、临床影响曲线、描述性 OR/Firth、TRIPOD+AI 清单/样本流程图/缺失说明/可复现性），MVP 约 9–11 人日，完整 29–38 人日。
- **E7d**：现有图表为 matplotlib SVG/PNG 字符串，前端 `dangerouslySetInnerHTML` 注入（`ResultDisplay.tsx:33-34`），ECharts 已声明但零引用（`package.json:17-18`）；建议新增 `type="echarts"` + option JSON 契约，前端 ECharts + `supabase-med` 主题，报告保留 matplotlib 同源渲染，彻底移除 SVG 注入；一期 10–12 人日，完整 22–28 人日。

## E7a 过渡措施：已加警示语的位置（文件:行号）+ 截图

文案（全站统一）：

> 变量筛选在全部数据上完成，内部验证结果偏乐观
>
> 报告方法学章节追加：内部验证不等于外部验证，结果不能直接用于临床决策。

| 位置 | 文件:行号 | 实现 |
|---|---|---|
| 结果页顶部 warn pill | `frontend/src/components/ResultDisplay/ResultDisplay.tsx:73-79` | Ant Design `Alert type="warning" showIcon`，位于 `result.summary` 之前 |
| 报告方法学（Word） | `backend/app/services/report_service.py:104-106` | 在 `METHOD_TEXT` 后新增加粗段落 |
| 报告方法学（PDF） | `backend/app/services/report_service.py:246-247` | reportlab `Paragraph` |
| 报告方法学（HTML 预览） | `backend/app/services/report_service.py:173-174` | `<p><b>注意：</b>…</p>` |
| 常量定义 | `backend/app/services/report_service.py:36-40` | `E7A_WARNING_TEXT`，三种格式共用 |

截图（本地，不入 git）：`D:\agent-workspace\deliveries\task-E7\result-warning.png`

渲染校验（本机 Python 3.11 + python-docx/reportlab）：

- HTML 预览包含警示语：`HTML_HAS_WARNING=True`
- Word 报告包含警示语：`DOCX_HAS_WARNING=True`
- PDF 文本包含两句警示语：`PDF_HAS_WARNING=True`（PyMuPDF 提取，`report_1792251440.pdf`）
- 截图显示结果页黄色警示条：已人工查看确认。

## 验收清单逐条结果

| # | 验收项 | 结果 | 证据/说明 |
|---:|---|---|---|
| 1 | 依赖确认：E7 无依赖（只出文档） | ✅ | `PROGRESS.md` E7 行依赖列为"无（只出文档）" |
| 2 | PROGRESS 开工改 🔵进行中 + Agent + 日期 | ✅ | 仅 Edit E7 行；Agent=`Claude-E7-agent (orchestrator wave1)`，日期 `2026-10-17` |
| 3 | worktree + 分支正确 | ✅ | `D:\agent-workspace\worktrees\task-E7`，分支 `docs/E7-proposals`，基线 `origin/main@9332500` |
| 4 | 四份设计文档齐全且包含六段结构 | ✅ | 见交付清单；每份均含现状/目标/API/UI/工作量/风险/🧑‍⚖️ |
| 5 | E7b–E7d 只出文档、未实施 | ✅ | `git diff` 仅 E7a 两个文件 + docs；无业务逻辑改动 |
| 6 | E7a 结果页警示语 | ✅ | `ResultDisplay.tsx:73-79`；截图 `result-warning.png` |
| 7 | E7a 报告警示语（Word/PDF/HTML） | ✅ | `report_service.py:36-40,104-106,173-174,246-247`；三种格式渲染均命中 |
| 8 | 前端 `npm run build` 通过 | ✅ | `tsc && vite build` 成功，3107 modules；仅 chunk >500KB 警告；日志 `deliveries/task-E7/npm-build.log` |
| 9 | Python 3.11 语法检查 | ✅ | `python -m py_compile backend/app/services/report_service.py` → `PY_COMPILE_OK` |
| 10 | 不碰服务器、不部署/重启 | ✅ | 未连接服务器；未执行任何部署/重启命令 |
| 11 | 不推 main、不自行合并 | ✅ | 仅推送 `docs/E7-proposals` 分支 |
| 12 | 交付说明随分支提交 | ✅ | 本文件 `deliveries/task-E7.md` |
| 13 | PROGRESS 收工改 🟡待合并 + commit hash | ✅ | 见本次提交后更新；仅 Edit E7 行 |

## 待人工确认（🧑‍⚖️）

### E7a 嵌套 CV（详见 `docs/proposals/E7a-嵌套CV.md` §7）

1. 新分析是否默认 `nested`？旧历史是否默认 `locked`？
2. 折间入选频率 ≥0.7 是否算"稳定"？还是只展示频率、不做二元判定？
3. 第 3 步是否保留"探索性全数据筛选"（建议保留并强标注）？
4. ALR/CLR 是否接受"变换接口不再筛峰"的破坏性变更，还是先加 `transform_only` 兼容参数？
5. Boruta 嵌套的默认 `maxRuns` 上限、单次请求最长等待时间、是否引入异步任务。
6. 嵌套模式下报告警示语口径是否改为"筛选已在 CV 内完成，但仍需外部验证"。

### E7b 指标修正（详见 `docs/proposals/E7b-指标修正.md` §7）

1. 主报告是否接受"训练折内选 Youden、验证折评估"？是否要求用户指定临床阈值？
2. AUC 用 DeLong 还是患者级 Bootstrap？其他指标是否统一 Bootstrap（1000 次）？
3. 是否同意把"重复间95%CI"改名为"重复间 mean±SD"，仅保留 Bootstrap 作为 95%CI？
4. KNN 默认 `kStrategy="cv"` 还是保持手选 K？内层折数固定 5 还是跟随外层？
5. 是否接受 Logistic 加权杠杆/Cook 距离导致 Top 10 影响点变化？是否保留 OLS 版本对照？
6. Cox 本轮是否包含校准曲线，还是只做测试集 C-index + PH 检验？
7. 旧报告是否同时输出旧/新口径，还是直接切换并标注版本？
8. Bootstrap/DeLong 依赖审批（可基于 numpy/scipy；Cox 校准新依赖需单独批准）。

### E7c EPV 与 TRIPOD+AI（详见 `docs/proposals/E7c-EPV与TRIPOD.md` §7）

1. EPV 阈值：<10 红色是否足够？10–20 是否黄色？生存分析是否同阈值？
2. Riley 参数默认值（shrinkage=0.9、δ=0.05、R²_CS 取值）；是否要求用户输入预期事件率/R²？
3. BH-FDR 校正范围（全部候选变量 vs 单因素表变量）；默认入选规则（q<0.05 / p<0.2 / 仅展示）。
4. 校准指标是否全上（ICI/E50/E90/loess）；再校准默认 Platt 还是等渗？
5. DeLong/Holm 是否只对二分类 OOF 提供？是否报告 ΔAUC CI？
6. NRI/IDI 参照模型是否固定基线 Logistic？连续 NRI 还是分类 NRI？
7. DCA Bootstrap 次数、阈值范围、是否按患者分组重抽样。
8. 是否允许新增 `firthlogist` 依赖，还是仅用 statsmodels 近似。
9. TRIPOD+AI 版本（2024 官方清单）、输出格式（Word 附录 + CSV）、是否逐条证据链接。
10. EPV<10 时仅警告还是禁止运行高参数模型（建议仅警告）。

### E7d ECharts 迁移（详见 `docs/proposals/E7d-ECharts迁移.md` §7）

1. 迁移顺序：ROC → 校准 → DCA → SHAP → 其他？一期只做前三个是否可接受？
2. 报告 Word/PDF 继续 matplotlib（推荐），还是投入服务端 ECharts SSR（需 Node/puppeteer）？
3. SHAP beeswarm 最大点数（500/1000/2000）及是否允许用户调整。
4. 旧 SVG 用 `<img>` 兼容（推荐）还是引入 DOMPurify 内联？历史记录是否也要交互？
5. 导出格式先做 SVG/PNG 还是必须同时 CSV？
6. `supabase-med` 主题由 E6 统一维护还是 E7d 自带（必须同源）。
7. 交互深度：图例筛选/阈值联动/置信带开关，还是先 tooltip+缩放。
8. ECharts 按需引入后的 gzip 预算（如 ≤150KB）与路由懒加载要求。

## 发现但未处理

- **按任务红线未实施**：E7b（指标修正）、E7c（EPV/TRIPOD）、E7d（ECharts）均只出设计文档，未改业务代码。
- `backend/app/services/ml/cox_service.py:56-57`：缺少标准列名时用 `hr*0.8/1.2` 伪造 95%CI，建议在 E7b B5 实施时一并修复（文档已记录）。
- `backend/app/services/ml/eval_service.py:60-88` 与 `backend/app/services/core/metrics.py:61-73` 存在两份 DCA 实现，口径可能漂移；E7c/E7d 文档已标注，未在本分支合并。
- `backend/app/services/ml/utils.py:97-110` 的单模型 `classification_metrics` 不含 PR-AUC/阳性比例，与 OOF 指标口径不一致；已记录在 E7b/E7c。
- `backend/app/services/report_service.py:71-81` 的 `_meta_lines` 不包含 seed/超参数/软件版本，报告不可复现；E7c 已列为改造项。
- 本机 Python 环境未预装 `reportlab`；本次用 `pip --target` 隔离安装到 `D:\agent-workspace\deliveries\task-E7\pydeps` 完成 PDF 渲染验证，未改动项目依赖或用户环境。服务器端 `backend/requirements.txt:21` 已声明 `reportlab==4.2.2`。
- 本分支未新增自动化测试：仓库基线尚无测试目录（E0 脚手架未合并）；本次以 `py_compile`、三种报告格式渲染校验、`npm run build` 和截图作为验收证据。

## 本地交付附件（不入 git）

- `D:\agent-workspace\deliveries\task-E7\npm-build.log`：`npm run build` 完整输出
- `D:\agent-workspace\deliveries\task-E7\result-warning.png`：结果页警示语截图
- `D:\agent-workspace\deliveries\task-E7\pydeps\`：PDF 验证用的隔离依赖（临时）
