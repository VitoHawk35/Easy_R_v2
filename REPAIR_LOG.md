# EasyR 逻辑错误修复执行清单

> 生成时间: 2026-05-17
> 按严重程度降序排列，逐条执行。

---

## 🔴 严重（功能错误或数据流断裂）

### 修复1: 外部验证逻辑完全错误
- **文件**: `backend/app/routers/eval.py`
- **问题**: 外部验证时直接用外部数据集 `fit` 训练模型，违背外部验证目的。
- **方案**: 改为先用原始 dataset_id 训练模型，再在外部数据上 `predict`/`predict_proba`。

### 修复2: 变量筛选最终结果是"交集"
- **文件**: `frontend/src/components/Wizard/steps/Step3VarFilter.tsx`
- **问题**: 代码注释写 union，实际代码是 `reduce((a,b) => a.filter(x => b.includes(x)))`（交集）。不同方法选出不同变量时，final 极易为空。
- **方案**: 改为并集 `Array.from(new Set(sets.flat()))`。

### 修复3: 多模型对比后 `bestModel` 格式不一致
- **文件**: `frontend/src/components/Wizard/steps/Step4ModelBuild.tsx`
- **问题**: 单模型模式 bestModel = 原始 key（如 `'xgboost'`）；多模型对比时 bestModel = 缩写（如 `'GBDT'`）。后续步骤作为 `modelType` 传给后端时格式不统一，导致后端服务报错。
- **方案**: 统一保留原始 key；后端服务内部自行做必要的 key->class 映射。

### 修复4: 模型评估的 `evalDataset` / `threshold` 完全未使用
- **文件**: `frontend/src/components/Wizard/steps/Step5Eval.tsx`
- **问题**: 用户界面提供数据集切换、指标勾选、分类阈值，但 `runEval` 中完全没有消费这些值。
- **方案**: 根据勾选指标调用对应 API；根据 `evalDataset` 调整 payload；根据 `threshold` 重新计算混淆矩阵（或传入后端）。

---

## 🟡 中等（功能缺失或边界情况处理不当）

### 修复5: 外部验证 `_get_model` 支持的模型太少
- **文件**: `backend/app/routers/eval.py`
- **问题**: 仅支持 6 种模型。Step4 选择的 LightGBM/CatBoost/MLP/Lasso/ElasticNet/LDA/QDA/Cox 在外部验证时会抛异常。
- **方案**: 扩展 `_get_model` 覆盖全部模型；或前端做可用性校验。

### 修复6: Nomogram 中 Lasso/ElasticNet 用于分类问题的类型不匹配
- **文件**: `backend/app/services/ml/nomogram_service.py`
- **问题**: Lasso/ElasticNet 是回归模型，用于二分类时 coef_ 对应连续值，Probability 轴的 sigmoid 映射无意义。
- **方案**: 分类场景限制 Nomogram 仅对 Logistic 可用；或改用 `LogisticRegression(penalty='l1')`。

### 修复7: `model_info` 仅在 2 个服务返回
- **文件**: `backend/app/services/ml/lasso_service.py`, `elastic_net_service.py`, `cox_service.py` 等
- **问题**: 仅 logistic / nomogram 返回了 `model_info`。Step6 Web 计算器对 Lasso/ElasticNet/Cox 显示"暂不可用"，但这些模型实际有系数。
- **方案**: 在各线性模型服务中统一返回 `model_info`（含 coefficients, intercept, feature_names）。

### 修复8: 报告下载存在路径遍历风险
- **文件**: `backend/app/routers/report.py`
- **问题**: `download_report` 直接拼接用户传入的 `filename`，存在路径遍历风险。
- **方案**: `filename = os.path.basename(filename)`。

### 修复9: Step6 可视化选项 "森林图" 和 "ROC" 未实现
- **文件**: `frontend/src/components/Wizard/steps/Step6Visual.tsx`
- **问题**: 勾选了 forest/roc 但 runVisual 中未处理。
- **方案**: 复用 Step4 已生成的结果，或补充 API 调用。

### 修复10: Step3 单因素筛选是空实现
- **文件**: `frontend/src/components/Wizard/steps/Step3VarFilter.tsx`
- **问题**: `results.univariate = availableVars`，完全忽略用户设置的 P 值阈值。
- **方案**: 前端增加简单 t-test / chi-square 筛选逻辑，或调用后端 API。

### 修复11: Step3 LASSO/RF 表格解析失败时静默回退
- **文件**: `frontend/src/components/Wizard/steps/Step3VarFilter.tsx`
- **问题**: 表格标题不匹配时回退到 `availableVars`，用户以为已筛选实际没有。
- **方案**: 解析失败时给出 `message.warning` 提示，而不是静默使用全部变量。

---

## 🟢 轻微（代码异味、UX 不一致、潜在隐患）

### 修复12: WizardContainer 向所有步骤传递未声明的 props
- **文件**: `frontend/src/components/Wizard/WizardContainer.tsx`
- **方案**: 条件传递或改为只传 Step1。

### 修复13: StepNavigator 与底部 Next 按钮跳转规则不一致
- **文件**: `frontend/src/components/Wizard/StepNavigator.tsx`
- **方案**: 统一为只有已完成步骤才能跳转。

### 修复14: Step2 缺失值诊断结果会重复累积
- **文件**: `frontend/src/components/Wizard/steps/Step2Diagnostics.tsx`
- **方案**: 合并时先移除旧的缺失值结果，再追加新结果。

### 修复15: Step9 Form.Item 缺少 Form 包裹
- **文件**: `frontend/src/components/Wizard/steps/Step9Validate.tsx`
- **方案**: 用普通 `<div>` + `<label>` 替换，或包一层 `<Form>`。

### 修复16: Step1 自动 markComplete 无法撤销
- **文件**: `frontend/src/components/Wizard/steps/Step1DataPrep.tsx`
- **方案**: 条件不满足时从 completedSteps 中移除第0步。

### 修复17: api.ts 中 `import.meta` 类型断言
- **文件**: `frontend/src/services/api.ts`
- **方案**: 在 `vite-env.d.ts` 中正确声明 ImportMetaEnv。

### 修复18: diagnostics.py 变量类型判断过于简化
- **文件**: `backend/app/routers/diagnostics.py`
- **方案**: 结合 unique_count 判断逻辑型变量。

---

## 2026-10-17 · task-E0 测试脚手架

- 新增 `backend/app/settings.py`，通过 `EASYR_DATA_DIR` / `EASYR_DEMO_PATH` 配置数据目录与演示数据路径，默认保持原 `backend/data/` 行为。
- `data_service.py` 与 `report_service.py` 改为从 settings 读取路径，避免测试写入仓库数据目录。
- 新增 `backend/tests/` 冒烟测试脚手架、`backend/requirements-dev.txt`；测试覆盖 `/api/health` 与登录后的 `/api/ml/logistic`。

## 2026-10-17 · task-E2 Bootstrap 有放回抽样修复

- **文件**: `backend/app/services/core/validation.py`（`optimism_bootstrap`）
- **问题**: `rng.choice(..., replace=True)` 后紧接 `np.isin(groups, chosen)` / `np.isin(arange, chosen)`，把重复抽中的单位压成一次；实际训练集退化为约 63% 的不重复子样本，`auc_boot`（表观）乐观度偏小、校正 AUC 有偏。
- **方案**: 直接构造含重复的样本下标 `idx`——有分组时按 `chosen` 拼接各组全部样本下标（`pos_by_unit` 循环外预计算），无分组时 `idx = chosen`；`X.iloc[idx]` / `y[idx]` 训练，重复样本保留。OOB 定义为 `np.setdiff1d(arange(n), idx)`（从未被抽中的样本；分组时即整组未被抽中）。表观 AUC 改用 `Xb, yb`，`auc_test` 仍在原始全样本上计算，OOB 用 `X.iloc[oob]`。
- 返回字典新增 `"resampling": "with_replacement"`；`validation_service.py` 表格与 summary 同步注明"有放回重抽样、重复单位保留"。
- **测试**: 新增 `backend/tests/test_bootstrap.py`（4 项：无分组训练行数恒为 n；分组训练行数=被抽中组样本数之和且组集合一致；OOB 组与 chosen 不相交；demo+logistic+B=50 满足 `corrected_auc ≤ apparent_auc` 且 `n_boot ≥ 45`）。全量 `pytest -q`: 6 passed。

## 2026-10-17 · task-E3 统计正确性（a–h）

### E3a 网页计算器与列线图概率
- **文件**: `backend/app/services/ml/predict_service.py`（新增）、`nomogram_service.py`、`backend/app/routers/ml.py`、`frontend/src/components/Wizard/steps/Step6Visual.tsx`
- **改动**: 新增 `POST /api/ml/predict`（MLRequest + `params.input`），后端按 Step4 同模型同参数在训练集拟合 Pipeline，LRU(16) 缓存，返回 `probability` 与原始尺度 `linear_predictor`；前端计算器改为表单（连续 InputNumber / 分类 Select，水平取自 `/datasets/{id}/variables` 新增的 `levels`），删除前端直接乘系数。
- **统计约定**: 系数还原 `β_raw=β_scaled/σ`、`b0_raw=b0−Σβ·μ/σ`（哑变量列同样按 scaler 反变换）；列线图 `points_j(x)=100·|β_j|·(x−x_min)/max_k(|β_k|·range_k)`（β<0 轴反向）；概率轴由 `sigmoid(lp)` 反解总分位置，不使用线性近似。仅支持 logistic/lasso/elastic-net。

### E3b 校准斜率与 CITL
- **文件**: `backend/app/services/core/metrics.py:53`
- **改动**: 校准斜率改为 statsmodels 无惩罚 GLM `y ~ logit(p)` 的系数；CITL 改为 `y ~ 1` 且 `offset=logit(p)` 的常数项；完全分离/不收敛返回 `nan`，并在校准 summary 中提示。
- **约定**: 返回顺序保持 `(slope, intercept=CITL)`。

### E3c CatBoost eval_set 与参数名
- **文件**: `backend/app/services/ml/catboost_service.py:25`、`backend/app/services/core/models.py:110`、`frontend/src/types/index.ts:427`
- **改动**: 删除用 `X_test` 作 `eval_set` 的二次 fit；早停如需要只能从 `X_train` 内部再切验证集。参数统一为 `learningRate`，后端兼容旧名 `learning_rate`。

### E3d 决策树参数名
- **文件**: `backend/app/services/core/models.py:63`、`frontend/src/types/index.ts:333`
- **改动**: 工厂同时读取 `minSamplesSplit`（`min_samples_split`）与 `minSamplesLeaf`（`min_samples_leaf`）；前端注册表补 `minSamplesLeaf`。

### E3e 缺失值诊断
- **文件**: `backend/app/routers/diagnostics.py:13`、`backend/app/services/data_service.py:279`
- **改动**: 新增 `get_raw_data()`（应用筛选、不删行）；缺失诊断改用原始数据；百分比直接用数值 `pct`，不再 `int("12.5%")`。

### E3f 缺失值处理与报告一致
- **文件**: `backend/app/services/data_service.py:293,317`、`backend/app/routers/ml.py`
- **改动**: `get_data_for_ml` 只删除结局（及生存时间）缺失行，X 缺失保留给 Pipeline 内 `ClinicalPreprocessor` 的中位数/参照水平填补；每个 `/api/ml/*` 结果 summary 追加“删除了 n 行结局缺失；X 缺失用训练集中位数/参照水平填补”。

### E3g 模型 key 静默替换与 SHAP 硬标签
- **文件**: `backend/app/services/ml/eval_service.py`、`explain_service.py`、`backend/app/routers/ml.py`
- **改动**: 两处改用 `canonical_key + create_model + needs_scale`，未知 key 返回 422，不再回退 LR/RF；非树模型分类的 SHAP 用 `predict_proba(X)[:,1]`。

### E3h 评估参数
- **文件**: `backend/app/services/ml/eval_service.py:50`、`frontend/src/components/Wizard/steps/Step5Eval.tsx:41`
- **改动**: 前端始终传 `testSize=0.3`；后端读取 `evalDataset∈{train,test,both}` 选择评估集合，`both` 返回两组指标；`threshold` 用于混淆矩阵、灵敏度、特异度，未传时用训练集 Youden 界值（不在测试集选界值）。

## 2026-10-17 · task-E1 报告下载安全（P0）

- `backend/app/services/auth_service.py`：签名密钥优先读取环境变量 `EASYR_AUTH_SECRET`；未设置时读取 `EASYR_SECRET_FILE`（默认 `DATA_DIR/../secrets/auth_secret.txt`，已移出 `DATA_DIR`），不存在则生成并 `chmod 600`。`DATA_DIR/auth_secret.txt` 不再创建或读取。
- `backend/app/services/report_service.py`：`generate_word_report` / `generate_pdf_report` 增加 `user_id` 参数，报告输出到 `DATA_DIR/users/{user_id}/reports/report_{yyyymmddHHMMSS}_{secrets.token_urlsafe(12)}.{docx|pdf}`。
- `backend/app/routers/report.py`：生成接口传入 `current_user.id`；下载接口先按 `^report_[0-9]{14}_[A-Za-z0-9_-]{16}\.(docx|pdf)$` 校验文件名，再用 `os.path.realpath` 限定在 `DATA_DIR/users/{current_user.id}/reports/` 下，否则一律 404。
- `frontend/src/services/api.ts`：新增 `downloadReportFile(filename)`，用带 `Authorization` 的 axios blob 请求 + 临时 `<a download>` 下载；`Step10Report.tsx` 下载按钮改为 `onClick`，预览 iframe 增加 `sandbox=""`。
- 新增 `backend/tests/test_report_security.py`（密钥不可下载、env 密钥签名/轮换、密钥文件位置、报告属主校验、旧式文件名拒绝）。
- 上线必须更换 `EASYR_AUTH_SECRET`：旧密钥可能已泄露，所有已发 token 失效属预期行为。
