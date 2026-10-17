# E7a · 变量筛选放进交叉验证（嵌套 CV）设计方案

> 任务：task-E7 · Easy_R_v2 · 分支 `docs/E7-proposals` · 基线 `origin/main@9332500`
> 性质：📐 只出方案，不在本分支实施（E7a 的文案级过渡措施已单独实施，见文末）。
> 目标问题：单因素 Logistic、LASSO、随机森林、Boruta、ALR/CLR 筛峰目前都在全量数据上完成；如何封装成 sklearn Transformer 放进 Pipeline、对向导第 3 步交互的影响、耗时估算。

## 0. 关键结论（3 行以内）

1. 现有"筛选服务 + 把 final 变量传给模型"的流程等价于**用全部样本（含后续验证折）的结局信息选变量**，下游任何 CV/测试集指标都带选择性乐观偏倚。
2. 正确做法是把每种筛选实现为 `fit(X, y)` 学习、`transform(X)` 选择的 sklearn Transformer，放在 `Pipeline(prep → filter → scale → clf)` 中；外层重复 CV 评估、内层 CV 调参/选阈值，天然形成嵌套 CV。
3. 推荐先做 Logistic/LASSO/Boruta 三个包装器 + 选择稳定性表（MVP 约 4–5 人日），ALR/CLR 需要把"确定性变换"与"有监督筛峰"拆开（约再 2–3 人日）；向导第 3 步从"跑一次给出最终变量"改为"探索 + 嵌套模式 + 折间入选频率"。

---

## 1. 现状（带文件:行号证据）

### 1.1 向导把筛选当成一次性的全数据预处理

- `frontend/src/components/Wizard/steps/Step3VarFilter.tsx:47-146`：依次调用 `logistic-screening`、`lasso-screening`、`random-forest`、`boruta` 四个接口，把各自入选变量求并集作为 `results.final`（`:138-146`），再 `dispatch SET_FILTER_RESULTS`（`:148`）。
- `frontend/src/components/Wizard/steps/Step4ModelBuild.tsx:25-27`：模型构建直接使用 `filterResults.final`（再并入强制变量）；`:61`（单模型）与 `:86`（多模型）把它作为 `x_variables` 发给后端。
- 因此，模型服务收到的是**已经看过全部数据结局**的候选变量子集。之后无论做训练/测试划分还是 CV，验证折的结局信息都已经通过"变量选择"进入了建模流程。

### 1.2 各筛选实现的证据

| 方法 | 位置 | 现状问题 |
|---|---|---|
| Logistic 单因素 | `backend/app/services/ml/logistic_service.py:85-130` | `ClinicalPreprocessor(...).fit(X_df)` 在全部数据上拟合（`:92-93`）；逐列 `sm.Logit(y_binary, x_design).fit(...)`（`:119-123`）用的是**全部样本的 y**；`Selected = p_value <= p_threshold`（`:130`）。 |
| LASSO | `backend/app/services/ml/lasso_service.py:80-112` | 注释写"筛选类函数无留出验证，不存在泄漏"（`:80`），但这是指筛选接口自身没有留出集；`:82-94` 全数据预处理+标准化，`:100-104` 全数据 `LogisticRegressionCV/LassoCV`，`:112` 全数据重拟合最终模型，`:120` 以 `|coef|>1e-6` 选变量。下游使用这些变量时，选择过程已经消耗了全部 y。 |
| 随机森林 | `backend/app/services/ml/rf_service.py:29-51` | `train_test_pipeline` 在训练集上拟合（`:29-31`），但特征重要性来自该训练集拟合（`:48-51`）；向导第 3 步用 `r[1] > 0` 选变量（`Step3VarFilter.tsx:101-103`），对多数数据等于"几乎全选"，并非有统计意义的筛选。 |
| Boruta | `backend/app/services/ml/boruta_service.py:22-50` | 代码注释直接写明"全数据特征选择（无留出验证）"（`:22`）；`:24-25` 全数据 `fit + transform`，`:49-50` `boruta.fit(X.values, y.values)` 使用全部样本。 |
| ALR/CLR 筛峰 | `backend/app/services/transform_service.py:86-107` | `_screen_peaks` 对每个峰用**全部数据的 y** 计算 p 值（`:96`）与 CV，`final_pass` 决定保留（`:98-106`）；在 `_run_alr`（`:165-166`）和 `_run_clr`（`:209`）中先筛峰、再用保留峰生成变换变量。被筛掉的峰不会进入后续模型，这一步同样是全数据有监督选择。 |

### 1.3 现有 CV 为什么不能自动修复这个问题

- `backend/app/services/core/validation.py:21-27` 的 `make_pipeline` 只包含 `prep → [scale] → clf`，没有筛选步骤；`:36-69` 的 `run_repeated_cv` 每折重新拟合的是"给定变量集上的模型"，不会重新选变量。
- `backend/app/services/core/preprocessing.py:18-78` 的 `ClinicalPreprocessor` 已经正确做到"预处理只在训练折 fit"，可以作为筛选 Transformer 的前置步骤复用。
- 结论：现有代码解决了**预处理泄漏**，但没有解决**变量选择泄漏**；两者需要分开处理。

---

## 2. 目标做法

### 2.1 统一抽象：筛选即 Transformer

新增 `backend/app/services/core/feature_selection.py`（建议路径），所有筛选器实现 sklearn 接口：

```python
class BaseFilter(BaseEstimator, TransformerMixin):
    def fit(self, X, y): ...          # 只在训练折上学习入选集合
    def transform(self, X): ...       # 按 self.selected_ 子集返回
    def get_feature_names_out(self, input_features=None): ...
```

建议的四个包装器：

| 包装器 | 内部实现 | 关键参数 | 输出 |
|---|---|---|---|
| `UnivariateLogitFilter` | 逐列 `statsmodels.Logit`（或 sklearn 单变量 LR），可加 BH-FDR | `p_threshold`、`p_adjust="none"/"bh"`、`min_nonmissing` | `selected_`、`p_values_`、`q_values_` |
| `LassoFilter` | `LogisticRegressionCV(penalty="l1", solver="saga")` / `LassoCV`，内部 CV 只在训练折内 | `cv`、`C_grid`/`alphas`、`threshold` | `selected_`、`coef_`、`best_alpha_` |
| `BorutaFilter` | `BorutaPy(RandomForest...)`，可关闭为 RF importance fallback | `max_runs`、`alpha`、`n_estimators` | `selected_`、`support_`、`support_weak_` |
| `ALRCLRPeakFilter` | 先做确定性 ALR/CLR 变换，再按 y 做 CV/p 筛峰 | `method`、`reference`、`cv_threshold`、`p_threshold` | `selected_`、`screening_rows_` |

实现要点：

1. **顺序必须是 `prep → filter → scale → clf`**。筛选器需要数值矩阵，因此放在 `ClinicalPreprocessor` 之后；标准化放在筛选之后，避免筛选器自己重复标准化。
2. **`transform` 只做列选择**，不做任何需要 y 的统计；所有统计量（p 值、系数、support）只存在于 `fit` 结果中。
3. **特征名要可追踪**：`get_feature_names_out` 返回入选后的列名；分类变量哑变量展开后仍能映射回原始变量（保留 `orig_var` 映射，用于稳定性统计和报告）。
4. **空选择保护**：若某折没有变量入选，应回退到"该折使用全部候选变量"或抛出可读错误；不能静默产出空模型。建议默认回退并在结果中记录 `fallback_used=True`。
5. **确定性**：所有随机过程使用请求中的 `seed`；Boruta/RF 的 `random_state` 固定，保证同一折可复现。

### 2.2 嵌套 CV 的执行结构

现有 `run_repeated_cv` 已经是"外层重复 CV"的骨架（`validation.py:36-69`）。改造后：

```
for repeat r in 1..R:
  for outer fold (train_o, test_o):
    pipe = Pipeline([
      ("prep", ClinicalPreprocessor(variable_types)),
      ("filter", filter_factory()),          # fit 只用 train_o 的 y
      ("scale", StandardScaler()),
      ("clf", model_factory()),
    ])
    # 若模型有超参数：在外层 train_o 内再做 inner CV
    pipe = GridSearchCV(pipe, param_grid, cv=inner_cv, scoring="roc_auc")
    pipe.fit(X[train_o], y[train_o])
    p_oof[test_o] = pipe.predict_proba(X[test_o])[:, 1]
    record selected_ per fold
```

- **外层**：重复分层（分组）K 折，负责性能估计；`run_repeated_cv` 继续复用 `StratifiedGroupKFold/StratifiedKFold`（`validation.py:30-33`）。
- **内层**：超参数搜索、LASSO 的 λ、Boruta 的迭代、单因素阈值（若需要数据驱动）都在外层训练折内部完成；`GridSearchCV` 的内层 CV 与 `LogisticRegressionCV` 的内部 CV 都满足这一要求。
- **固定超参数**：若用户显式指定超参数，可跳过内层搜索，但筛选仍在每折内 fit；这仍是"筛选嵌套"，只是没有超参数嵌套。
- **选择稳定性**：记录每个原始变量在 `R × K` 个外层训练折中被选中的次数/比例。建议输出：
  - `selection_frequency`（0–1）；
  - `selected_in_all_folds`；
  - 默认"稳定入选"阈值建议 0.7（待拍板，见 §7）。

### 2.3 ALR/CLR 的特殊处理

当前 `transform_service.py` 把"确定性对数比变换"和"有监督筛峰"绑在一个接口里（`:151-233`）。建议拆成两层：

- **确定性层（无 y）**：ALR/CLR 的闭合、对数、几何均值、伪计数/零值处理都不依赖 y，可以作为普通预处理，在训练折上学习参考峰/伪计数后应用到验证折。
- **有监督层（用 y）**：`_screen_peaks` 的 CV/p 筛选必须变成 `ALRCLRPeakFilter`，放进 Pipeline。

两种落地方式：

1. **推荐（彻底）**：`/api/data/transform` 只产出确定性变换后的数据集（不再筛峰）；筛峰作为模型 Pipeline 的一步。这样 Step2/3 仍然可以预览变换结果，但变量选择不再提前固化。
2. **兼容（渐进）**：保留现有"变换并筛选"接口，但新增 `transform_only=true` 参数；向导在嵌套模式下调用 transform-only，在旧模式下调用现有接口并显示偏乐观警告。

### 2.4 耗时估算

设样本 n=300、候选变量 p=30、二分类、5 次重复 × 5 折：

| 方案 | 计算量 | 估算 |
|---|---|---|
| Logistic/LASSO 嵌套（LR 每折 1 次拟合 + 内层 5 折） | 25 个外层折 × (1 次筛选 + 内层≤5 次) | 秒级（<10 s） |
| 单因素 Logit 嵌套 | 25 × p 次单变量拟合 | 秒级（<5 s） |
| Boruta 嵌套（maxRuns=100，200 棵树） | 25 × 100 × 200 棵树 | 分钟到数十分钟，取决于 CPU/变量数 |
| RF importance 嵌套 | 25 × 200 棵树 | 十秒到数分钟 |
| ALR/CLR 筛峰嵌套 | 25 × p 次检验 + 变换 | 秒级 |

Boruta 是主要瓶颈。建议：
- 嵌套模式下默认 `maxRuns` 上限（如 50）或提供"快速模式"；
- 复用 `n_jobs=-1`，但避免在容器内超线程导致内存峰值；
- 在 API 返回 `estimated_cost`/进度状态（若后续引入任务系统），向导显示"预计 5–15 分钟"；
- 对 p 很大（>100）时，先做无监督方差/共线性过滤，再做有监督筛选。

---

## 3. 对 API 的影响

### 3.1 请求

建议在 `MLRequest`（`backend/app/models/schemas.py:33-43`）中新增可选字段，保持向后兼容：

```json
{
  "x_variables": ["候选变量全集"],
  "feature_selection": {
    "mode": "nested",              // nested | locked | none
    "methods": ["univariate", "lasso", "boruta"],
    "p_threshold": 0.05,
    "p_adjust": "bh",
    "stability_threshold": 0.7,
    "max_runs": 50
  }
}
```

- `mode="locked"`：沿用当前行为（`x_variables` 已是最终变量），用于复现旧分析；结果中必须标记 `selection_scope="all_data"`。
- `mode="none"`：不筛选，直接用 `x_variables`。
- `mode="nested"`：`x_variables` 是候选集，筛选在每折内完成。

### 3.2 响应

`MLResult`（`schemas.py:25-31`）新增可选字段（全部有默认值，旧前端不受影响）：

```json
{
  "selection_meta": {
    "mode": "nested",
    "outer_folds": 25,
    "inner_folds": 5,
    "methods": ["lasso"],
    "stability_threshold": 0.7
  },
  "selection_stability": {
    "headers": ["Variable", "SelectedFreq", "SelectedCount", "Stable"],
    "rows": [["AGE", 0.96, 24, true]]
  }
}
```

也可以把稳定性表直接放进 `tables`，但独立字段更利于前端做 pill 和报告章节。

### 3.3 受影响端点

- `/api/ml/logistic`、`/api/ml/lasso`、`/api/ml/lasso-predict`、`/api/ml/random-forest`、`/api/ml/boruta`、`/api/ml/compare`（`backend/app/routers/ml.py:47-124`）。
- `/api/data/transform`（`transform_service.py:236-249`）增加 `transform_only` 参数（若采用 §2.3 方案 2）。
- 历史记录：`history_service` 保存 request/result，新增字段自然进入快照；旧记录缺少字段时前端按 `mode="locked"` 显示。

---

## 4. 对向导 UI 的影响（第 3 步为主）

### 4.1 第 3 步的新交互

建议把第 3 步从"运行一次筛选并锁定 final 变量"改为三块：

1. **模式选择（单选）**
   - 「嵌套 CV（推荐）」：默认。说明"筛选会在每个训练折内重新做，验证结果更可信"。
   - 「锁定当前变量集」：兼容旧流程，显示黄色提示"该变量集由全数据筛选得到，后续内部验证偏乐观"。
   - 「不筛选」：直接用候选变量。
2. **探索性筛选（可选，仅展示）**
   - 保留现有四个方法的运行按钮，但结果标注为"探索性（全数据）"，只用于帮助用户理解变量，不自动写入最终变量集。
   - 每个方法的结果增加 `q 值`（BH-FDR）与"入选频率"占位；在嵌套模式实际运行后由模型返回真实频率。
3. **最终变量集**
   - 嵌套模式下不再显示单一"最终变量"清单，而是显示"候选变量集"；模型运行结束后显示稳定性表：变量、入选频率、是否稳定入选。
   - 允许用户把某些变量设为"强制纳入"（`forcedIncludeVars` 已存在，`Step4ModelBuild.tsx:27`），强制变量不参与筛选剔除。

### 4.2 第 4 步的提示

- 在模型参数区顶部加一个 pill：
  - 嵌套：`筛选：嵌套 CV（外 5×5）`
  - 锁定：`筛选：全数据（内部验证偏乐观）`（黄色）
- 运行结果页沿用 E7a 已加的固定警示语（`frontend/src/components/ResultDisplay/ResultDisplay.tsx:73-79`）；嵌套模式可把警示语替换为"筛选已在交叉验证内完成"的绿色/中性说明。

### 4.3 第 10 步报告

- 报告方法学说明需要记录：
  - 筛选是否在 CV 内完成（是/否）；
  - 外层/内层折数、重复次数、随机种子；
  - 每种筛选方法的参数与版本；
  - 稳定性阈值与稳定入选变量列表。
- 这与 E7c 的 TRIPOD+AI 清单（"变量选择方法""数据泄漏控制"）直接对应，建议共用一份 `selection_meta`。

---

## 5. 实现工作量估算

| 工作项 | 估算（人日） | 说明 |
|---|---:|---|
| `BaseFilter` + 单因素/ LASSO / Boruta 三个包装器 | 3–4 | 含单元测试、空选择/常量列/分类变量边界 |
| 接入 `make_pipeline`/`run_repeated_cv`/`compare` | 2 | 保持旧 `mode="locked"` 兼容 |
| 选择稳定性统计与 API 字段 | 1 | 折间计数、原始变量映射 |
| ALR/CLR 拆分（transform-only + 筛峰 Transformer） | 2–3 | 涉及 `transform_service` 与数据工作区 |
| 向导第 3/4 步交互与结果展示 | 2–3 | 模式切换、稳定性表、提示 |
| 报告方法学段落与测试 | 1 | 与 E7c 共用 |
| 回归测试（旧流程快照、性能基准） | 1–2 | 需要固定 seed 的小数据夹具 |
| **合计** | **12–16 人日** | MVP（仅 LR/LASSO/Boruta + 稳定性，不改 ALR/CLR）约 6–8 人日 |

> 任务路线图写的"1 周"更适合 MVP；完整方案建议按 3 周排期（1 人）。

---

## 6. 风险与回退方案

| 风险 | 影响 | 缓解/回退 |
|---|---|---|
| Boruta 嵌套耗时爆炸 | 请求超时、用户体验差 | 默认上限/快速模式；异步任务化（与 L7f 任务系统方案对齐）；必要时回退到 RF importance |
| 折间选择不稳定 | 用户困惑"为什么每次变量不同" | 以稳定性表呈现，不承诺单一变量集；文档解释 |
| 空选择或常量列 | 某折模型失败 | 回退全变量 + `fallback_used` 标记；预检常量/缺失 |
| 旧分析无法复现 | 历史报告数字变化 | 保留 `mode="locked"`，旧记录默认 locked；报告标注模式 |
| 前后端接口不兼容 | 旧前端报错 | 新字段全部可选；按 `selection_meta` 是否存在降级 |
| 分类变量展开导致变量数膨胀 | 计算变慢、EPV 下降 | 先做共线性/方差预过滤；按原始变量计 EPV 与稳定性 |

**总回退开关**：`feature_selection.mode` 默认值可配置；服务端环境变量 `E7A_NESTED_DEFAULT=0` 可一键回到旧行为。所有新字段保持可选，回退不需要改数据库。

---

## 7. 🧑‍⚖️ 待用户拍板的决策点

1. **默认模式**：新分析是否默认 `nested`？还是先默认 `locked`、让用户主动选择？（建议默认 nested，旧历史 locked。）
2. **稳定性阈值**：折间入选频率 ≥ 0.7 算"稳定"是否合适？还是只展示频率、不做二元判定？
3. **第 3 步是否保留"探索性全数据筛选"**：保留会带来误用风险，但有助于用户理解变量；建议保留并强标注。
4. **ALR/CLR 是否拆分**：是否接受"变换接口不再筛峰"的破坏性变更？还是先加 `transform_only` 兼容参数？
5. **计算预算**：Boruta 嵌套的默认 `maxRuns` 上限、单次请求最长等待时间（是否引入异步任务/进度条）。
6. **报告口径**：嵌套模式下是否仍需保留"内部验证偏乐观"警示语？（建议改为"筛选已在 CV 内完成，但仍需外部验证"。）

---

## 8. E7a 过渡措施（已实施，文案级）

按任务附录二，已在同分支完成，不涉及本方案的代码实施：

- 结果页：`frontend/src/components/ResultDisplay/ResultDisplay.tsx:73-79` 顶部新增 `Alert type="warning"`，文案为「变量筛选在全部数据上完成，内部验证结果偏乐观」。
- 报告方法学说明：`backend/app/services/report_service.py:36-40` 新增 `E7A_WARNING_TEXT`，并在 Word（`:104-106`）、PDF（`:246-247`）、HTML 预览（`:173-174`）的「方法与评价协议」章节各输出一句「注意：变量筛选在全部数据上完成，内部验证结果偏乐观；内部验证不等于外部验证，结果不能直接用于临床决策。」
- 提交信息将注明 "E7a 过渡措施（不需方案确认）"。
