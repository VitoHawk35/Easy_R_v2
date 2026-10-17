# E7b · 指标的统计学修正设计方案

> 任务：task-E7 · Easy_R_v2 · 分支 `docs/E7-proposals` · 基线 `origin/main@9332500`
> 性质：📐 只出方案，不在本分支实施。
> 范围：任务原文列出的五项——Youden 界值、重复间 95% CI、KNN 选 K、Logistic 杠杆值/Cook 距离、Cox 表观 C-index 与 PH 假定。

## 0. 关键结论（3 行以内）

1. 当前多项指标存在"在同一份数据上选择又在同一份数据上评估"或"用错方差公式"的问题：Youden 界值与评估共用 OOF，重复间 CI 用 `SD/√R` 严重低估不确定性，KNN 在测试集上选 K。
2. Logistic 的杠杆值用了 OLS 帽子矩阵，忽略 `p(1-p)` 权重；Cox 只报告训练集表观 C-index，且从未调用 PH 假定检验，即使代码里已经切出了测试集也未使用。
3. 建议统一引入"选择/评估分离"协议：阈值与 K 在外层训练折内选，评估只做一次；CI 改用患者级 Bootstrap/DeLong，重复间只报 mean±SD；Logistic 用 GLM 影响度量；Cox 报告测试集/交叉验证 C-index 与 Schoenfeld 残差 PH 检验。全部改动可作为 `metrics_v2` 开关灰度上线。

---

## 1. B1 · Youden 界值在同一份 OOF 上选择又评估

### 1.1 现状（证据）

- `backend/app/services/core/metrics.py:84-87`：

```python
fpr, tpr, thr = roc_curve(y, p)
youden = float(thr[int(np.argmax(tpr - fpr))])
pred = (p >= youden).astype(int)
tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
```

- 同一函数随后用这组 `pred` 计算灵敏度、特异度、ACC、F1、PPV、NPV（`metrics.py:88-98`），并把 `youden` 一并返回（`:96`）。
- 该函数被 `run_repeated_cv` 对每次重复的 OOF 预测调用（`backend/app/services/core/validation.py:56`），也被 `compare_service.py` 间接使用（`compare_service.py:91-108` 的汇总表使用这些字段）。
- 问题：界值是在**同一份 OOF 预测**上挑选的，而 OOF 本身已经用于报告 AUC；随后又在这份数据上评估灵敏度和特异度，等同于"用验证集选阈值、再用验证集报告阈值相关指标"，产生乐观偏倚。AUC 本身对阈值不敏感，问题主要集中在 sens/spec/ACC/F1/PPV/NPV 与"最佳界值"。

### 1.2 目标做法

1. **阈值来源与评估分离**：
   - 在每个外层训练折内，用内层 CV（或训练折 OOF）选 Youden 界值；
   - 用该界值在对应的外层验证折上评估 sens/spec 等指标；
   - 汇总各折指标，报告均值与患者级 Bootstrap CI。
2. **主指标改为阈值无关指标**：AUC、PR-AUC、Brier、校准斜率作为主要报告；sens/spec 明确标注"在预先指定阈值下"或"在训练折内选择的 Youden 阈值下"。
3. **报告界值的不确定性**：给出各折阈值的均值/范围，或对 OOF 概率做 Bootstrap 后重选阈值的 95% 区间；不要只报一个"最佳界值"。
4. **可选固定临床阈值**：允许用户输入 `threshold`（如 0.2），报告该阈值下的 2×2 表与净获益；与 Youden 结果并列，避免"最佳界值"被误读为临床决策阈值。
5. **净获益一致性**：DCA 的阈值范围与报告的 sens/spec 阈值保持一致。

### 1.3 API / UI 影响

- `MLRequest.params` 新增可选：`threshold`（固定阈值）、`thresholdStrategy`（`"nested_youden" | "fixed" | "train_youden"`，默认 `nested_youden`）。
- `classification_oof_metrics` 返回增加 `threshold_source`、`threshold_mean`、`threshold_low/high`、`sens/spec` 的 CI；旧字段保留。
- `compare_service.py` 的性能表（`:183-195`）拆成"阈值无关指标"与"阈值相关指标"两组，列名标注阈值来源。
- UI：结果页在 sens/spec 旁显示 `阈值=0.xx（训练折内选择）` 的 tooltip；报告方法学段落写明阈值选择协议。

### 1.4 工作量

- 指标函数与嵌套阈值逻辑：2–3 人日。
- compare/eval/report 接入与前端列调整：1–2 人日。
- 回归测试（固定 seed、构造乐观偏倚数据）：1 人日。
- **合计 4–6 人日**。

### 1.5 风险与回退

- 风险：旧报告数字变化；不同折阈值差异大导致 sens/spec 不稳定；小样本 Bootstrap 失败。
- 回退：`metrics_v2=false` 时保留旧字段；报告中同时给出旧口径和新口径一版；阈值 CI 失败时降级为点估计并标注。

---

## 2. B2 · "重复间 95% CI" 用 SD/√R

### 2.1 现状（证据）

- `backend/app/services/core/metrics.py:104-119` 的 `summarize_repeats`：

```python
out[f"{c}_sd"] = float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
out[f"{c}_ci_low"] = float(vals.mean() - 1.96 * vals.std(ddof=1) / np.sqrt(len(vals)))
out[f"{c}_ci_high"] = float(vals.mean() + 1.96 * vals.std(ddof=1) / np.sqrt(len(vals)))
```

- `compare_service.py:101`、`:183-184` 直接把这些字段作为"重复间95%CI"展示；`validation_service.py:56-58` 每次重复调用 `classification_oof_metrics` 后交给 `summarize_repeats`。
- 问题：
  1. 重复 CV 的各次重复共享同一批患者，**不是独立样本**；把"重复次数 R"当作样本量会低估方差。
  2. `1.96` 假设正态且 R 很大；实际默认 R=5（`compare_service.py:54`），应使用 t 分位数（t₄=2.776），且即使如此也只反映"重复随机性"，不是患者抽样不确定性。
  3. 该 CI 只反映"换一个 CV 划分"的波动，不能解释为"模型性能的 95% 置信区间"。

### 2.2 目标做法

1. **改名**：把"重复间95%CI"改为"重复间波动（mean ± SD）"，避免统计含义误导。
2. **主 CI 用患者级 Bootstrap**：对 OOF 预测按患者（有分组变量时按组）重抽样，重算 AUC 等指标，取 2.5/97.5 百分位。现有 `bootstrap_auc_ci`（`metrics.py:122-138`）已实现"固定预测概率的 Bootstrap"，可扩展为多指标并支持分组重抽样。
3. **AUC 可用 DeLong**：二分类 AUC 的方差用 DeLong 方法（与 E7c 的模型比较共用实现），比 Bootstrap 快且解析。
4. **重复间区间**：若确实要报告重复间区间，用 `t_{R-1}` 而非 1.96，并明确标注"仅反映重复划分的随机性"；建议同时给出 `min/max` 或 2.5/97.5 百分位。
5. **报告层级**：
   - 主要：OOF AUC + 患者级 Bootstrap 95%CI；
   - 次要：重复间 mean ± SD（R 次）；
   - 不再把 `SD/√R` 称为 95%CI。

### 2.3 API / UI 影响

- `summarize_repeats` 输出增加 `*_repeat_sd`、`*_repeat_min/max`、`*_boot_ci_low/high`；保留旧 `*_ci_*` 字段但标记 deprecated。
- `compare_service.py` 表头从"重复间95%CI"改为"重复间 mean±SD"+"Bootstrap 95%CI"（后者已有 `boot_ci` 列，`:183-184`）。
- UI：tooltip 解释两种区间的区别；报告方法学段落说明"重复 CV 的重复不是独立样本"。
- 若分组变量存在，Bootstrap 必须按组重抽样，复用 `validation.py:80-95` 的分组逻辑。

### 2.4 工作量

- 扩展 Bootstrap 多指标/分组：2 人日。
- DeLong AUC 方差（可与 E7c 共用）：1–2 人日。
- 表格/报告/前端改名：1 人日。
- **合计 4–5 人日**。

### 2.5 风险与回退

- 风险：Bootstrap 在极小样本/单一结局时退化；分组重抽样可能产生空折；旧前端依赖列名。
- 回退：保留旧列名并新增列；Bootstrap 失败时回退到 t 区间并标注；分组重抽样失败时回退到按样本并标记 `grouped=False`。

---

## 3. B3 · KNN 在测试集上选 K

### 3.1 现状（证据）

- `backend/app/services/ml/knn_service.py:20`：`k` 来自用户参数，默认 5。
- `:25-30`：用该 `k` 构建模型，`train_test_pipeline` 在训练集拟合。
- `:31-36`：在测试集上计算 `y_pred`/`y_prob` 和最终指标。
- `:38-44`：

```python
k_range = range(1, min(21, len(X_train)))
for ki in k_range:
    p = clone(pipe).set_params(clf__n_neighbors=ki)
    p.fit(X_train, y_train)
    scores.append(p.score(X_test, y_test))
```

- 问题：候选 K 的评分使用的是**测试集**；如果用户根据这张图/分数选择 K，测试集信息就进入了模型选择，最终测试指标偏乐观。即使用户不选，图中展示的"最佳 K"也来自测试集，报告读者会误以为这是无偏的调参结果。

### 3.2 目标做法

1. **内层 CV 选 K**：只在外层训练集上做 `GridSearchCV(KNeighborsClassifier(), param_grid={"n_neighbors": range(1,21)}, cv=StratifiedKFold(5), scoring="roc_auc")`；用内层 CV 均值 ± SE 选 K（可选 one-SE 规则）。
2. **测试集只评估一次**：选定 K 后在外层训练集重拟合，在测试集评估一次；测试集不再参与任何 K 的选择。
3. **若用户固定 K**：明确标注"K 为预先指定"，此时不展示"最佳 K"曲线，或把曲线明确标为"训练集内 CV"。
4. **分组数据**：若存在患者 ID，内层 CV 也要用 `StratifiedGroupKFold`，避免同一患者跨折。
5. **报告**：给出 K 的 CV 曲线（均值±SE）、选中 K、测试集最终指标；说明选择协议。

### 3.3 API / UI 影响

- `MLRequest.params` 增加 `kStrategy: "cv" | "fixed"`（默认 `cv`）；`k` 在 `fixed` 时生效。
- 响应图（`ChartData` "K值选择"）改为"训练集内 CV AUC（mean±SE）"，并标注选中 K；不再画测试集分数。
- UI：K 参数旁显示"默认由训练集内 5 折 CV 选择"；结果表增加 `k_selected`、`k_cv_auc`。
- 报告方法学段落记录 K 的选择协议。

### 3.4 工作量

- 1 人日（逻辑 + 图 + 表）。
- 加上分组 CV 与测试：1.5–2 人日。
- **合计 2 人日**。

### 3.5 风险与回退

- 风险：内层 CV 在小样本/多分类时不稳定；计算量增加（21 个 K × 5 折，仍很小）。
- 回退：`kStrategy="fixed"` 完全保留旧行为；内层 CV 失败时回退到默认 K 并标注。

---

## 4. B4 · Logistic 杠杆值使用 OLS 帽子矩阵

### 4.1 现状（证据）

- `backend/app/services/ml/adv_diag_service.py:33-36`：用训练集拟合后的 Logistic 模型得到 `y_prob`。
- `:50-52`：

```python
X_design = np.column_stack([np.ones(n), X_train_s])
H = X_design @ np.linalg.inv(X_design.T @ X_design + np.eye(p+1)*1e-6) @ X_design.T
leverage = np.diag(H)
```

- `:54-57` 用该 `leverage` 计算 Cook's D；`:59-60` 计算标准化 Pearson 残差；`:97-111` 画杠杆值-残差图；`:113-130` 输出 Top 10 影响点。
- 问题：这是 **OLS 的帽子矩阵** `X(X'X)⁻¹X'`。Logistic 回归的观测信息量随预测概率变化，正确杠杆值应使用加权矩阵：

```
W = diag(p_i(1-p_i))
H = W^{1/2} X (X' W X)^{-1} X' W^{1/2}
h_ii = w_i x_i' (X' W X)^{-1} x_i
```

忽略权重会把高/低预测概率区域的观测误判为高杠杆，影响 Top 10 排序和 Cook 距离。此外 `:51` 对 `X'X` 加 `1e-6` 岭项是为了数值稳定，但会轻微改变杠杆值；应改为 `pinv` 或明确的广义逆。

### 4.2 目标做法

1. **用 GLM 影响度量**：
   - 用 `statsmodels.GLM(y, X, family=Binomial()).fit()` 或复用已拟合的 Logistic 模型；
   - 计算 `h_ii`（加权杠杆）、Pearson 残差 `r_i`、标准化 Pearson 残差 `r_i/√(1-h_ii)`；
   - Cook's D 采用 Logistic 版本：`D_i = r_i² h_ii / (p (1-h_ii)²)`（p 为参数个数，含截距），或使用 `statsmodels` 的 `get_influence()` 给出的 `cooks_distance`。
2. **阈值**：杠杆值参考 `2p/n`、`3p/n`；Cook's D 参考 `4/n` 或 `1`；在图上标注并说明。
3. **残差类型**：同时给出 Pearson 与 deviance 残差；Q-Q 图对二分类残差的正态性意义有限，建议改为半正态/模拟包络或明确标注"参考用途"。
4. **样本量与稀疏性提示**：当事件数/参数比（EPV）低时，影响点诊断本身不稳定，应在图上加提示（与 E7c 联动）。
5. **数值稳定**：用 `np.linalg.pinv` 或 `statsmodels` 的稳定实现，避免手写 `inv`；对完全分离给出警告。

### 4.3 API / UI 影响

- 图表结构不变（残差-拟合、Q-Q、Cook、杠杆-残差），但数值与 Top 10 排序会变化；需在报告和 UI 中标注"Logistic 加权杠杆/Cook 距离"。
- 表格增加 `Leverage` 的阈值列、`Cook's D` 阈值列；`Status` 按新阈值判定。
- 无需新 API 字段；可在 `summary`/`model_info` 中加 `influence_method="weighted_logit"`。
- UI：图注说明"基于 Logistic 信息矩阵，不是 OLS 帽子矩阵"。

### 4.4 工作量

- 重写影响度量与图/表：2 人日。
- 单元测试（与 statsmodels 结果对齐）：1 人日。
- **合计 3 人日**。

### 4.5 风险与回退

- 风险：新旧影响点列表差异大，用户质疑；完全分离时数值不稳定；Q-Q 解释争议。
- 回退：保留旧实现作为 `influence_method="ols_hat"` 选项（仅用于对照），默认新方法；报告中注明方法变更。

---

## 5. B5 · Cox 只报训练集表观 C-index，且无 PH 假定检验

### 5.1 现状（证据）

- `backend/app/services/ml/cox_service.py:38-41`：已经生成随机排列并切出 `train_idx/test_idx`。
- `:43-46`：`ClinicalPreprocessor` 只在训练集 fit，构造 `train_df`；**测试集 `test_idx` 之后没有再被使用**。
- `:48-49`：`CoxPHFitter(...).fit(train_df, ...)`。
- `:70`：`concordance = round(cph.concordance_index_, 4)`——这是训练集表观 C-index。
- `:74`：summary 只报告该值与事件数。
- 全文件没有 `check_assumptions`、Schoenfeld 残差、时间依赖 AUC 或校准；`grep -n "check_assumptions"` 在仓库中无结果。
- 另外 `:56-57` 在缺少标准列名时用 `hr * 0.8` / `hr * 1.2` 伪造 95%CI，这会在列名变化时静默输出错误区间，应一并修正或至少显式报错。

### 5.2 目标做法

1. **报告测试集/交叉验证 C-index**：
   - 用训练好的 `cph` 在 `test_df` 上计算 `cph.score(test_df, scoring_method="concordance_index")`；
   - 更稳健：重复分层 CV（外层 5×5），每次在训练折拟合、验证折计算 C-index，报告 mean±SD 与 Bootstrap CI；
   - 训练集表观 C-index 仅作为对照，明确标注 "apparent"。
2. **PH 假定检验**：
   - `cph.check_assumptions(train_df, p_value_threshold=0.05, show_plots=False)` 获取全局与逐变量检验；
   - 或基于 `cph.compute_residuals(train_df, "scaled_schoenfeld")` 做时间交互检验；
   - 输出表格：变量、Schoenfeld 残差检验 p、是否违反；全局检验 p；
   - 违反时给出建议：分层 Cox、时变系数、或改用 AFT/RSF，并在报告中警告。
3. **校准**：至少报告 1–2 个临床时间点的校准（预测生存 vs Kaplan-Meier），或使用 `lifelines` 的 `predict_survival_function` 做校准曲线；若工作量大，作为后续增量。
4. **事件数与 EPV**：报告事件数、候选参数数、EPV；Cox 的 EPV 同样适用（与 E7c 联动）。
5. **CI 伪造修复**：删除 `hr*0.8/1.2` 回退；列名不匹配时抛错或从 `summary_df` 的 `coef lower 95%` 明确取值，并加列名兼容映射。

### 5.3 API / UI 影响

- Cox 结果表增加：`test_c_index`、`cv_c_index_mean/sd/ci`、`ph_global_p`、逐变量 PH 检验表。
- `summary` 改为"训练表观 C-index=…；验证 C-index=…；PH 全局 p=…"。
- UI：Cox 结果页增加"比例风险假定"卡片/表格；PH p<0.05 时红色警示；报告方法学段落记录。
- 参数：`testSize` 已存在（`:34`），新增 `phTest: true`、`cvFolds`、`repeats` 可选。

### 5.4 工作量

- 测试集/CV C-index：2 人日。
- PH 检验与表格/图：2 人日。
- 校准（可选）：2–3 人日。
- CI 修复与测试：1 人日。
- **合计 7–8 人日（不含校准约 5 人日）**。

### 5.5 风险与回退

- 风险：`check_assumptions` 在小样本/少事件时可能报错或功效低；删掉 CI 回退会暴露一些数据列名问题；旧报告 C-index 变低。
- 回退：PH 检验失败时显示"无法检验（样本/事件不足）"而不是中断；保留 `c_index_apparent` 旧字段；CI 回退改为显式错误。

---

## 6. 跨项 API / UI / 报告汇总

### 6.1 API

建议新增一个统一的 `analysis_protocol` 元信息（可选）：

```json
{
  "threshold": {"strategy": "nested_youden", "value": 0.18, "ci": [0.12, 0.25]},
  "ci": {"method": "patient_bootstrap", "n_boot": 1000, "grouped": true},
  "knn": {"k_strategy": "cv", "k_selected": 9, "inner_folds": 5},
  "influence": {"method": "weighted_logit"},
  "cox": {"c_index_apparent": 0.71, "c_index_test": 0.66, "ph_global_p": 0.03}
}
```

旧字段全部保留，新增字段可选；前端按字段存在性渐进展示。

### 6.2 UI

- 结果页：每个指标卡片的 tooltip 显示"来源/选择协议/CI 方法"；对"表观""测试集""OOF""重复间"使用统一术语。
- 报告：方法学说明章节（`report_service.py` 的 `METHOD_TEXT`）增加一段"阈值、K、CI、影响度量、PH 检验"的协议描述；结论与局限性章节引用 E7a 固定警示语。
- 对比页：性能表拆分为"区分度（阈值无关）""阈值相关指标""校准"三块，避免把不同口径混在一张表。

### 6.3 工作量总表

| 项 | 人日 |
|---|---:|
| B1 Youden | 4–6 |
| B2 重复间 CI | 4–5 |
| B3 KNN K | 2 |
| B4 Logistic 影响度量 | 3 |
| B5 Cox | 5–8 |
| 统一协议/API/UI/报告 | 3–4 |
| **合计** | **21–28 人日** |

可分批：B1+B2+B3（约 10–13 人日）先上线，B4/B5 随后。

---

## 7. 🧑‍⚖️ 待用户拍板的决策点

1. **阈值策略**：主报告是否接受"训练折内选 Youden、验证折评估"？还是要求用户必须指定临床阈值？
2. **CI 方法**：AUC 用 DeLong 还是患者级 Bootstrap？其他指标是否统一用 Bootstrap（1000 次是否可接受）？
3. **重复间区间**：是否同意把"重复间95%CI"改名为"重复间 mean±SD"，仅保留 Bootstrap 作为 95%CI？
4. **KNN 默认**：默认 `kStrategy="cv"` 还是保持用户手选 K？内层折数固定 5 还是跟随外层？
5. **影响度量**：是否接受 Logistic 加权杠杆/Cook 距离导致 Top 10 影响点变化？是否保留 OLS 版本作为对照？
6. **Cox 范围**：本轮是否包含校准曲线，还是只做测试集 C-index + PH 检验？
7. **旧报告兼容**：是否需要同时输出旧口径与新口径，还是直接切换并在报告中注明版本？
8. **依赖审批**：Bootstrap/DeLong 可基于现有 numpy/scipy 实现；Cox 校准若引入新依赖，需要单独批准。

---

## 8. 发现但未在本方案展开的相关问题

- `backend/app/services/ml/cox_service.py:56-57` 在缺少标准列名时伪造 95%CI（`hr*0.8/1.2`），应在 B5 中一并修复。
- `backend/app/services/ml/utils.py:97-110` 的 `classification_metrics` 使用 weighted precision/recall/F1，且无 CI；与 OOF 指标口径不一致。建议后续统一到 `core/metrics.py`。
- `backend/app/services/ml/eval_service.py:40-58` 的校准曲线只报告 Brier，没有校准斜率/截距/ICI；属于 E7c 附录第 4 条，未在 E7b 重复展开。
- `backend/app/services/ml/adv_diag_service.py:79-83` 对二分类残差做正态 Q-Q 图，解释力有限；建议改为半正态或模拟包络（B4 可选）。
