# E7c · EPV 预警、统计报告规范与 TRIPOD+AI 设计方案

> 任务：task-E7 · Easy_R_v2 · 分支 `docs/E7-proposals` · 基线 `origin/main@9332500`
> 性质：📐 只出方案，不在本分支实施。
> 对应原文：报告任务四第 2 节第 2–8 条（EPV 预警、单因素 BH-FDR、DeLong+Holm、NRI/IDI、DCA 置信带、临床影响曲线、描述性 OR/Firth、TRIPOD+AI 清单/样本流程图/缺失说明/随机种子与超参数；另含第 4 条校准与第 5 条类别不平衡）。

## 0. 关键结论（3 行以内）

1. 当前代码中完全没有 EPV、TRIPOD+AI、DeLong、NRI/IDI、BH-FDR、Firth、class_weight、ICI/E50/E90 等实现（全仓 grep 无结果）；报告只拼装用户勾选的 `MLResult` 章节，无法回答"样本量是否足够、结果是否经得起审稿"。
2. 建议新增一个"分析质量层"：预检阶段计算 EPV/Riley 最小样本量并给红/黄预警；评估阶段补 BH-FDR、DeLong+Holm、NRI/IDI、DCA Bootstrap 带、临床影响曲线与校准指标；报告阶段自动生成 TRIPOD+AI 对照表、样本流程图、缺失数据处理说明、随机种子与全部超参数。
3. 这些功能应全部是**建议性**的，不阻断建模；MVP（EPV + BH-FDR + TRIPOD+AI 清单骨架）约 2 周，完整实现约 4–5 周。TRIPOD+AI 自动生成只能保证"有据可查"，不能宣称自动满足合规。

---

## 1. 现状（带文件:行号证据）

### 1.1 全仓缺失项

在基线 `9332500` 上执行：

```bash
grep -rn "EPV\|TRIPOD\|DeLong\|IDI\|NRI\|firth\|class_weight\|fdr_bh\|multipletests\|ICI\|E50\|E90" backend/app frontend/src
```

除颜色值 `#1E90FF` 外无任何命中。也就是说，下列能力目前都不存在。

### 1.2 逐项证据

| 条目 | 现状证据 | 缺口 |
|---|---|---|
| EPV 预警 | `backend/app/services/core/metrics.py:76-101` 的 `classification_oof_metrics` 只输出 n、AUC、PR-AUC、Brier 等；没有任何事件数/参数数比 | 无 EPV 计算、无 Riley 2020 最小样本量、无预警 UI |
| 单因素 BH-FDR | `backend/app/services/ml/logistic_service.py:100-130` 逐变量 `sm.Logit` 后直接 `Selected = p_value <= p_threshold`（`:130`）；无 `multipletests` | 无 q 值、无多重比较校正、无"p<0.2 + 临床先验"提示 |
| DeLong + Holm | `backend/app/services/ml/compare_service.py:119-134` 只画 ROC；`:183-195` 只并列 AUC mean±SD；全文件无两两检验 | 无 DeLong 检验、无 Holm 校正、无 p 值矩阵 |
| NRI/IDI | `compare_service.py:98-108` 的结果字典无 NRI/IDI 字段；`:197-203` 校准表也无 | 无基线模型参照、无连续 NRI/IDI、无 CI |
| DCA 置信带 | `backend/app/services/core/metrics.py:61-73` 的 `dca_curve` 只算点估计；`backend/app/services/ml/eval_service.py:60-88` 又实现了一遍 DCA，同样无重抽样 | 无 Bootstrap 带、无临床阈值区间限制 |
| 临床影响曲线 | 全仓无 `clinical impact`/每 1000 人高风险人数相关代码 | 无该图/表 |
| 描述性 OR / Firth | `logistic_service.py:119-130` 已用无惩罚 `sm.Logit` 给出 OR、95%CI、p；`:132-133` 失败时仅标记 `FitFailed` | 无完全分离检测、无 Firth 回退、无"无惩罚模型"标注 |
| 校准（第 4 条） | `metrics.py:51-58` 有校准斜率/截距；`compare_service.py:96-107`、`:197-203` 使用；但 `eval_service.py:40-58` 只画 `calibration_curve` + Brier | 无 CITL、ICI/E50/E90、loess、CV 内 Platt/等渗再校准 |
| 类别不平衡（第 5 条） | `grep class_weight` 无结果；`backend/app/services/ml/utils.py:97-110` 的 `classification_metrics` 不含 PR-AUC/阳性比例 | 无 class_weight 选项、无 PR-AUC 报告（compare 里有 `pr_auc`，单模型没有）、无"加权后必须重新校准"提示 |
| TRIPOD+AI | `backend/app/services/report_service.py:20-29` 只有一段通用 `METHOD_TEXT`；`:31-34` 通用局限性；`:65-81` 章节来自用户勾选；`:84-144`/`:147-192`/`:195-283` 生成 Word/HTML/PDF，均无清单 | 无 TRIPOD+AI 对照表、无样本流程图、无缺失说明、无种子/超参数记录 |
| 缺失数据说明 | `backend/app/models/schemas.py:84-89` 的 `VariableInfo` 有 `missing_count`；但 `report_service.py:71-81` 的 `_meta_lines` 未使用 | 报告无逐变量缺失数量/比例、无处理方式说明 |
| 随机种子/超参数 | `report_service.py:71-81` 仅记录生成时间、数据集、结局、分组、最佳模型；`Step10Report.tsx:20-58` 传入的 reportData 也没有显式 seed/params | 报告不可复现 |
| 向导入口 | `frontend/src/components/Wizard/steps/Step10Report.tsx:88-108` 只有 7 个章节勾选和格式选择 | 无"生成 TRIPOD+AI 清单"选项、无质量预检展示 |

---

## 2. 目标做法

### 2.1 EPV 预警与 Riley 2020 最小样本量

#### 定义

- **二分类**：事件数 `E = min(n_positive, n_negative)`（或用户指定"事件"类别）；参数数 `p` 为**预处理展开后**的设计矩阵列数（含截距；哑变量按实际列数计）。`EPV = E / p`。
- **生存数据**：`E` 为事件数（`event==1`），`p` 为 Cox 模型参数数（含截距不适用时按协变量数）。
- **多分类**：按"每类 vs 其余"分别计算，或使用最小类样本数，报告中注明口径。

#### 预警规则（建议）

| EPV | 级别 | 展示 |
|---:|---|---|
| ≥ 20 | 正常 | 中性文字 |
| 10–20 | 注意（黄） | warn pill："EPV=xx，估计可能不稳定" |
| < 10 | 警告（红） | 红色 Alert："EPV=xx < 10，模型过拟合风险高；建议减少参数或扩大样本" |

#### Riley 2020 最小样本量

按 Riley et al. 2020（BMJ 368:m441）的三条准则取最大值：

1. **预测效应估计的乐观度小**（目标 shrinkage S，默认 0.9）：
   `n1 = p / ((S - 1) * ln(1 - R²_CS / S))`
   其中 `R²_CS` 为预期 Cox-Snell R²（可由先验模型/文献给出；无先验时用保守默认值并标注）。
2. **表观与校正 R² 的绝对差小**（默认 δ=0.05）。
3. **总体风险估计足够精确**（默认边际误差 0.05）：
   `n3 = (1.96 / δ)² * prevalence * (1 - prevalence)`。

最终 `n_min = max(n1, n2, n3)`，`E_min = n_min * prevalence`。实现上建议移植 R `pmsampsize` 的 Python 等价逻辑，并保留其默认参数与出处；不要只报一个 EPV 阈值。

#### 展示位置

- 第 3 步（变量筛选）与第 4 步（模型构建）顶部预检卡片；
- 结果页（`ResultDisplay`）顶部 warn pill；
- 报告"样本量与事件数"章节：n、事件数、参数数、EPV、Riley 最小 n、是否达标、所用假设（S、R²_CS、prevalence、δ）。

### 2.2 单因素筛选的 BH-FDR

- 在 `logistic_service.py:100-130` 收集所有可检验变量的 p 值后，调用 `statsmodels.stats.multitest.multipletests(pvals, method="fdr_bh")`，输出 `q_value`、`RejectBH`。
- 表格列：`Variable, Coefficient, OR, CI95_Lower, CI95_Upper, PValue, QValue, SelectedP, SelectedBH, Status`。
- 默认选择规则建议：**不自动用 q<0.05 作为唯一标准**；改为：
  - 展示 q 值；
  - 默认入选 `p < 0.20`（放宽）+ 用户可手动勾选；
  - 提示"不建议只靠单因素 p<0.05 选变量，应结合临床先验"。
- 与 E7a 的关系：BH-FDR 只应在**训练折内**计算；全数据 BH 仅作为探索性展示并标注。

### 2.3 校准：斜率、CITL、ICI/E50/E90、loess、CV 内再校准

- 在 `core/metrics.py` 增加：
  - `calibration_slope_intercept` 已存在（`:51-58`），但需明确"无惩罚 Logistic 校准模型"，并输出 CI；
  - `citl`（calibration-in-the-large）：`logit(y) ~ offset(logit(p))` 的截距；
  - `ici`（integrated calibration index）：`mean(|p - loess(y~p)|)`；
  - `e50`/`e90`：预测概率与校准曲线差的绝对值的 50%/90% 分位；
  - `loess` 平滑：用 `statsmodels.nonparametric.lowess` 或 `lowess`，输出网格点供前端绘图。
- `eval_service.py:40-58` 接入上述指标；报告表格增加这些列。
- **再校准**：在外层训练折内做 Platt（Logistic 校准）或等渗回归（`sklearn.isotonic.IsotonicRegression`），在验证折评估；报告"再校准前/后"的斜率、ICI、Brier。注意：再校准本身也是模型拟合，必须在 CV 内。
- UI：校准图叠加 loess 曲线与 45° 线；指标卡显示斜率、CITL、ICI、E50、E90；明确"无惩罚估计"。

### 2.4 类别不平衡

- 为支持的分类器增加 `class_weight` 参数（`"balanced"` 或用户字典）；向导参数面板增加开关/下拉。
- 报告：
  - 阳性比例、阴性比例；
  - PR-AUC（单模型也补上，当前只有 `classification_oof_metrics` 有，`utils.classification_metrics` 没有）；
  - 敏感性/特异性/PPV/NPV 与阈值；
  - 固定提示："使用 class_weight 后预测概率不再校准，必须重新校准/重新报告校准指标"。
- 不建议默认开启；仅在用户选择时启用，并在结果中标记 `class_weight_used=true`。

### 2.5 模型比较：DeLong + Holm、NRI/IDI、DCA 置信带、临床影响曲线

#### DeLong + Holm

- 对二分类模型两两做 DeLong 检验（比较相关 ROC 曲线，考虑同一批患者上的相关性）；实现可用快速 DeLong 算法（基于 AUC 的结构分量），避免暴力重采样。
- 用 `multipletests(pairs, method="holm")` 校正；输出：
  - 下三角 p 值矩阵（原始 p）；
  - Holm 校正 p 矩阵；
  - 每对 `ΔAUC` 与 95%CI。
- 仅对二分类、且有 OOF 概率的模型可用；多分类暂不提供。
- 建议在 `compare_service.py:183-195` 的性能表旁新增"模型比较"表，不要把所有 p 值塞进主表。

#### NRI/IDI

- 以基线 Logistic（或用户指定的参照模型）为 reference，计算：
  - 连续 NRI：`P(up|event) - P(down|event) + P(down|non-event) - P(up|non-event)`；
  - IDI：`(IS_new - IS_ref) - (IP_new - IP_ref)`，其中 IS/IP 为事件/非事件的预测概率均值差；
  - 分类 NRI 若使用阈值，需明确阈值。
- 用患者级 Bootstrap 给 95%CI；报告 NRI/IDI 点估计、CI、方向解释。
- 注意：NRI 对阈值和模型尺度敏感，报告中必须写明参照模型与阈值；不要把 NRI 当作唯一优越性证据。

#### DCA 置信带

- 对 OOF 预测按患者（分组时按组）Bootstrap `B=500–1000` 次，每次重算净获益曲线，取 2.5/97.5 百分位形成带。
- 阈值范围限制在临床合理区间（默认 0.05–0.95，可由用户/参数指定），避免接近 0/1 时的数值爆炸。
- `eval_service.py:60-88` 与 `compare_service.py:150-165` 统一调用 `core/metrics.dca_curve`，不要两份实现。
- 图上同时画 treat-all、treat-none；置信带只画模型曲线，避免图过密。

#### 临床影响曲线（Clinical Impact Curve）

- 对每个阈值 t 计算：
  - 每 1000 人中判为高风险人数：`1000 * P(p >= t)`；
  - 其中真阳性人数：`1000 * P(p >= t, y=1)`；
  - 可再加"每 1000 人净获益"。
- 输出为 ECharts/图表数据；与 DCA 并列展示。
- 需注明"基于 OOF 预测，未做外部验证"。

### 2.6 描述性 OR 与 Firth 回归

- 现状 `logistic_service.py:119-130` 已给出无惩罚 OR、95%CI、p，这是正确的描述性做法；需要：
  - 在表头/摘要明确"无惩罚 Logistic，OR 为描述性关联，不代表因果"；
  - **完全分离检测**：若某变量在某水平上事件全为 0/1，或 `sm.Logit` 报 PerfectSeparation、系数爆炸（|coef| > 10 或 SE > 10），标记 `Separation`；
  - 对分离变量自动/可选改用 Firth 惩罚 Logistic（Python 可用 `firthlogist` 包，或 `statsmodels` 的 `Logit.fit_regularized` 作为近似；推荐 Firth 并保留 OR/CI/p）。
- 输出列：`Method`（`ML`/`Firth`）、`OR`、`CI95`、`PValue`、`Separation`、`Status`。
- 不建议把 Firth 结果混入预测模型；它仅用于描述性 OR 表。

### 2.7 报告：TRIPOD+AI 清单、样本流程图、缺失说明、种子与超参数

#### TRIPOD+AI 清单自动生成

- 建立一份版本化的模板（建议 `backend/app/services/report/tripod_ai.py` 或 JSON/YAML 数据文件），条目以官方 TRIPOD+AI 2024 checklist 为准；每个条目包含：
  - `item_id`、`section`、`requirement`、`report_location`（本报告章节/表/图）、`status`（满足/部分/不适用/待补）、`evidence`（自动填入的值）。
- 自动映射示例：
  - 研究对象与数据来源 → `_meta_lines` 的数据集/样本量/中心；
  - 结局定义 → `y_variable`；
  - 预测因子 → `x_variables`/筛选方法；
  - 样本量 → EPV/Riley 结果；
  - 缺失数据 → 新增缺失统计；
  - 模型开发 → `model_type`、超参数、seed；
  - 模型性能 → AUC/校准/DCA 表；
  - 公平性/亚组 → 若未做，标"待补"（不伪造）；
  - 可解释性 → SHAP/PDP 章节；
  - 开放科学 → 代码/数据可用性（由用户填写）。
- 输出格式：Word 附录表格 + HTML 预览 + 可下载 CSV/Markdown。清单是"对照表"，不是合规证书；报告中必须写明"自动生成，需作者核对"。

#### 样本流程图

- 统计节点：原始数据行数 → 应用筛选条件后 → 缺失/异常排除后 → 分析样本 → 训练/测试（或 CV 外层）→ 事件数/非事件数。
- 后端返回结构化节点与计数，前端用 ECharts/SVG 或报告用 matplotlib 画流程图；报告中同时给出文字说明。
- 需与 `get_data_for_ml` 的实际过滤逻辑一致（`backend/app/services/data_service.py`），避免"流程图数字与结果不一致"。

#### 缺失数据处理说明

- 数据准备阶段已有 `VariableInfo.missing_count`（`schemas.py:84-89`），但报告未用；新增：
  - 逐变量缺失数量/比例表；
  - 处理方式：连续变量中位数填补、分类变量 `__MISSING__` 水平、Cox 完整病例删除（`cox_service.py:25-28`）；
  - 建模后缺失机制说明（MCAR/MAR/MNAR 不可自动判定，只能说明假设）。
- 报告中明确"中位数/哑变量在训练折内学习"（与 `preprocessing.py:37-56` 一致）。

#### 随机种子与超参数

- 报告元信息增加：`seed`、各算法全部参数（`request.params`）、CV 折数/重复数、筛选参数、软件版本（Python/scikit-learn/lifelines 等）。
- 当前 `report_service.py:71-81` 没有这些字段；`Step10Report.tsx:20-26` 也没有传。需要在 `reportData` 中增加 `reproducibility` 对象，由向导状态生成。
- 建议报告附录输出一张"可复现性"表；与 TRIPOD+AI 的"模型开发/超参数"条目共用数据。

---

## 3. 对 API 的影响

### 3.1 预检端点（建议新增）

`POST /api/ml/quality-check` 或在现有模型端点返回前附加：

```json
{
  "n": 300,
  "events": 60,
  "parameters": 12,
  "epv": 5.0,
  "epv_level": "red",
  "riley_min_n": 480,
  "riley_assumptions": {"shrinkage": 0.9, "r2_cs": 0.15, "prevalence": 0.2, "margin": 0.05},
  "missing": [{"variable": "AGE", "missing": 3, "percent": 1.0}],
  "warnings": ["EPV < 10：建议减少参数或扩大样本"]
}
```

预检只读、不训练模型，适合在第 3/4 步即时调用。

### 3.2 模型结果字段

`MLResult` 增加可选：

```json
{
  "quality": {
    "epv": 5.0,
    "epv_level": "red",
    "riley_min_n": 480,
    "calibration": {"slope": 0.91, "citl": -0.12, "ici": 0.04, "e50": 0.03, "e90": 0.08},
    "class_imbalance": {"positive_rate": 0.2, "pr_auc": 0.55, "class_weight": null},
    "model_comparison": {"delong_holm": [...], "nri": [...], "idi": [...]},
    "dca_band": {"thresholds": [...], "low": [...], "high": [...]},
    "clinical_impact": {"thresholds": [...], "high_risk_per_1000": [...], "true_positive_per_1000": [...]}
  }
}
```

全部可选，旧前端忽略即可。

### 3.3 报告请求

`report_data` 增加：

```json
{
  "reproducibility": {"seed": 123, "params": {...}, "cv": {...}, "versions": {...}},
  "quality": {...},
  "tripod_ai": {"enabled": true, "items": [...]},
  "sample_flow": {"nodes": [...]},
  "missing_data": [...]
}
```

`/api/report/generate`（`routers/report.py:11-29`）无需改路由，只扩展字典；三种格式（Word/PDF/HTML，`report_service.py:84/147/195`）都要输出清单和附录。

---

## 4. 对向导 UI 的影响

### 4.1 第 3/4 步

- 顶部新增"分析质量预检"卡片：
  - EPV 红/黄/绿 pill；
  - 事件数、参数数、Riley 最小样本量；
  - 缺失数据摘要（可展开）；
  - 若 EPV<10，显示"减少变量/扩大样本/使用惩罚模型"三条建议。
- 变量筛选结果表增加 `QValue` 列与 tooltip；提供"按 p<0.2 选择"按钮（可选）。
- 模型参数区增加 `class_weight` 开关（分类模型）。

### 4.2 结果页

- 顶部沿用 E7a 固定警示语（`ResultDisplay.tsx:73-79`）；若 EPV<10，再叠加一条红色 Alert。
- 校准卡片增加斜率/CITL/ICI/E50/E90；模型比较增加 DeLong/Holm 表、NRI/IDI 表；DCA 增加置信带；新增临床影响曲线。
- 所有新图/表都要有一句白话解读（E6 的 ChartCard 规范，见 `tasks/task-E6-前端换肤.md:156-161`）。

### 4.3 第 10 步报告

- 新增勾选项：
  - 「生成 TRIPOD+AI 对照清单」；
  - 「生成样本流程图」；
  - 「附缺失数据处理说明」；
  - 「附可复现性信息（种子/超参数/版本）」。
- 报告预览中新增"报告质量附录"章节；清单表格支持下载 CSV。
- 默认全部勾选（清单不影响正文长度太多），但允许用户取消。

---

## 5. 实现工作量估算

| 工作项 | 人日 | 备注 |
|---|---:|---|
| EPV + Riley 2020（含预检端点） | 3–4 | 公式、边界、生存/多分类口径 |
| BH-FDR 单因素表 | 1 | statsmodels 已有 |
| 校准扩展（CITL/ICI/E50/E90/loess） | 2–3 | 与 E7b 的校准斜率共用 |
| class_weight + PR-AUC/阳性比例 | 1–2 | 多模型参数透传 |
| DeLong + Holm | 2–3 | 快速 DeLong、相关 ROC |
| NRI/IDI（Bootstrap CI） | 2–3 | 参照模型定义 |
| DCA Bootstrap 带 + 临床影响曲线 | 2–3 | 统一 DCA 实现 |
| 描述性 OR + Firth | 2–3 | 依赖选择 |
| TRIPOD+AI 模板与自动映射 | 4–5 | 条目映射、三种格式输出 |
| 样本流程图 | 2 | 计数一致性测试 |
| 缺失数据说明 + 可复现性附录 | 2 | |
| 前端预检/结果/报告 UI | 4–5 | 卡片、表、图、勾选项 |
| 测试与文档 | 3–4 | 固定夹具、边界、回归 |
| **合计** | **29–38 人日** | MVP（EPV + BH + TRIPOD 骨架 + 可复现性）约 9–11 人日 |

按 1 人全职约 6–8 周；建议拆成两个迭代：
- 迭代 1（2 周）：EPV/Riley、BH-FDR、缺失说明、种子/超参数、TRIPOD+AI 清单骨架；
- 迭代 2（3–4 周）：校准扩展、DeLong/Holm、NRI/IDI、DCA 带、临床影响、Firth、样本流程图、完整 UI。

---

## 6. 风险与回退方案

| 风险 | 影响 | 缓解/回退 |
|---|---|---|
| Riley 公式参数（R²_CS/S/δ）无先验 | 最小样本量不可信 | 给出默认值与敏感性分析（多组假设）；报告中标注"基于假设" |
| EPV 按展开后参数计 | 分类变量多时 EPV 骤降 | 同时显示"按原始变量"和"按展开参数"两种口径 |
| TRIPOD+AI 自动映射被误读为合规 | 学术/合规风险 | 明确"自动生成、需作者核对"；不自动填"满足"；不确定项标"待补" |
| DeLong 实现错误/小样本 | 错误的显著性 | 与已知库/模拟数据对齐测试；小样本加警告 |
| Bootstrap 置信带计算慢 | 请求超时 | 默认 B=500；异步/任务化；缓存 OOF |
| Firth 依赖新增 | 部署复杂度 | 优先用 statsmodels 近似；Firth 作为可选依赖，缺失时降级并提示 |
| 旧报告/前端不兼容 | 报错 | 新字段全部可选；按存在性渲染；报告模板版本化 |
| 多重比较范围争议 | 结果解释冲突 | 明确"对全部候选变量做 BH"；同时展示未校正 p |
| 类别权重后概率未校准 | 临床决策误导 | 强制显示"必须重新校准"；报告同时给校准指标 |

**总回退**：所有质量功能由 `quality.enabled` 开关控制；关闭后完全回到当前报告/结果，不改变既有字段。

---

## 7. 🧑‍⚖️ 待用户拍板的决策点

1. **EPV 阈值**：<10 红色警告是否足够？是否把 10–20 也设为黄色？生存分析是否用同一阈值？
2. **Riley 参数**：默认 shrinkage=0.9、δ=0.05、R²_CS 取多少？是否要求用户输入预期事件率/R²？
3. **BH-FDR 范围**：对全部候选变量校正，还是只对"进入单因素表"的变量校正？默认入选规则用 q<0.05、p<0.2，还是仅展示不自动选？
4. **校准指标**：ICI/E50/E90 是否都上？loess 平滑带宽用默认还是可调？再校准默认 Platt 还是等渗？
5. **DeLong/Holm**：是否只对二分类、OOF 模型提供？是否同时报告 ΔAUC CI？
6. **NRI/IDI**：参照模型固定为基线 Logistic，还是允许用户选择？连续 NRI 还是分类 NRI？
7. **DCA 带**：Bootstrap 次数（500/1000）、阈值范围（0.05–0.95 还是 0.01–0.99）、是否按患者分组重抽样？
8. **Firth**：是否允许新增 `firthlogist` 依赖？还是仅用 statsmodels 近似？
9. **TRIPOD+AI 版本**：以 TRIPOD+AI 2024 官方清单为准？输出 Word 附录 + CSV 是否够？是否需要逐条"证据链接"到报告章节？
10. **是否阻断**：EPV<10 时仅警告，还是禁止运行某些高参数模型？（建议仅警告。）

---

## 8. 发现但未在本方案展开的相关问题

- `backend/app/services/ml/eval_service.py:60-88` 与 `backend/app/services/core/metrics.py:61-73` 存在两份 DCA 实现，口径可能漂移；建议统一到 `core/metrics.py`。
- `backend/app/services/ml/utils.py:97-110` 的单模型 `classification_metrics` 不含 PR-AUC/阳性比例，与 `core/metrics.py:76-101` 的 OOF 指标不一致。
- `backend/app/services/report_service.py:71-81` 的 `_meta_lines` 不包含 seed/超参数/软件版本，导致报告不可复现；这是 E7c 报告部分的直接输入。
- `backend/app/services/ml/cox_service.py:25-28` 用完整病例删除处理缺失；报告需要说明该策略及其样本量影响。
- TRIPOD+AI 的"公平性/亚组"条目需要亚组分析支持，当前代码没有亚组性能表；建议在迭代 2 评估是否纳入。
