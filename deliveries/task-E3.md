# task-E3 · Easy_R_v2 统计正确性交付说明

任务ID / 分支 / 基线提交：task-E3 / `fix/E3-stats-correctness` / `1b7b809`（origin/main，含 E0）

## 改动文件（按 a–h）

- **E3a**
  - `backend/app/services/ml/predict_service.py`（新增，整文件）：训练集拟合 + 原始尺度系数还原 + LRU(16) + `POST /api/ml/predict`
  - `backend/app/services/ml/nomogram_service.py`（整文件重写，`draw_nomogram:40`、`run_nomogram:126`）
  - `backend/app/routers/ml.py:204`（`/predict`）
  - `backend/app/models/schemas.py:84`（`VariableInfo` 新增 `levels/min_value/max_value`，默认值兼容）
  - `backend/app/services/data_service.py:224`（variables 返回水平/范围）
  - `frontend/src/components/Wizard/steps/Step6Visual.tsx`（计算器改表单，`CALCULATOR_MODELS:10`，`/predict` 调用）
  - `frontend/src/services/api.ts`（`predict()`）
- **E3b** `backend/app/services/core/metrics.py:53`
- **E3c** `backend/app/services/ml/catboost_service.py:25,48`；`backend/app/services/core/models.py:110`；`frontend/src/types/index.ts:427`
- **E3d** `backend/app/services/core/models.py:63`；`frontend/src/types/index.ts:333`
- **E3e** `backend/app/routers/diagnostics.py:13-45`；`backend/app/services/data_service.py:279`
- **E3f** `backend/app/services/data_service.py:293,317`；`backend/app/routers/ml.py:34`
- **E3g** `backend/app/services/ml/eval_service.py`（整文件）；`backend/app/services/ml/explain_service.py`（整文件）；`backend/app/routers/ml.py`（422 分支）
- **E3h** `backend/app/services/ml/eval_service.py:50`；`frontend/src/components/Wizard/steps/Step5Eval.tsx:41`

## 符号/统计约定

- **列线图 points**：`points_j(x) = 100·|β_j|·(x − x_min)/max_k(|β_k|·range_k)`；β<0 时轴反向（`points_j(x)=100·|β_j|·(x_max − x)/D`）。`D = max_k(|β_k|·range_k)`。
- **原始尺度还原**：`β_raw = β_scaled/σ`，`b0_raw = b0 − Σ β_scaled·μ/σ`；哑变量是预处理后的 0/1 设计列，同样按 scaler 反变换，保证 `sigmoid(b0_raw + Σβ_raw·x)` 与 `pipe.predict_proba` 一致。
- **概率轴**：`lp = b0_raw + Σ β_j·(β_j≥0 ? x_min_j : x_max_j) + (D/100)·TotalPoints`，按 `logit(p)` 反解刻度，不再线性近似。
- **CITL**：`sm.GLM(y, ones, Binomial(), offset=logit_p)` 的常数项；**校准斜率**：`sm.GLM(y, add_constant(logit_p), Binomial())` 的 logit(p) 系数；均无惩罚。完全分离/不收敛 → `nan`。
- **Youden 界值选择集合**：仅训练集；测试集不参与阈值选择。`threshold` 未传时才回退到训练集 Youden，传了则直接使用。
- **缺失值处理**：只删除结局（及生存时间）缺失行；X 缺失由 `ClinicalPreprocessor` 用训练集中位数/参照水平填补。

## 测试

新增 `backend/tests/test_stats_correctness.py`（19 个 E3 测试 + 原有 2 个冒烟测试 = 21）：

- E3a：20 名患者 `/predict` vs `pipe.predict_proba` 最大差 <1e-9；logistic/lasso/elastic-net 原始系数 `sigmoid(lp)` vs Pipeline <1e-6；分类变量换水平概率变化。
- E3b：n=5000 真实斜率 0.6 ±0.08；完美校准斜率≈1、CITL≈0（±0.1）。
- E3c：打桩 CatBoost.fit 断言无 `eval_set`；解析 `types/index.ts` 断言 catboost=`learningRate`、DT 含 `minSamplesSplit`+`minSamplesLeaf`。
- E3d：工厂 DT 同时读取两个参数。
- E3e：`/api/diagnostics/missing` 返回 200 且“中性粒细胞” MissingCount>0。
- E3f：X 缺失行保留；summary 含“删除了 n 行结局缺失；X 缺失用训练集中位数/参照水平填补”。
- E3g：`modelType="svm"` 实际构造 `SVC`；未知 `"foo"` 返回 422；非树分类 SHAP 预测函数输出概率。
- E3h：`train` 200 且仅训练集；`both` 返回训练集+测试集两组；threshold 0.3/0.7 灵敏度不同。

`pytest -q` 输出（完整日志见 `D:\agent-workspace\deliveries\task-E3\pytest.log`）：

```
21 passed, 1140 warnings in 21.85s
```

`npm run build` 输出（完整日志见 `D:\agent-workspace\deliveries\task-E3\npm-build.log`）：

```
> easyr-frontend@1.0.0 build
> tsc && vite build
vite v5.4.21 building for production...
✓ 3107 modules transformed.
dist/index.html                   0.40 kB
dist/assets/index-tg8iSokc.js 1,269.43 kB
✓ built in 23.44s
```

## 验收逐条核对（按 a–h）

- [x] E3a-1 demo+logistic 任取 20 名患者，`/predict` 与直接 `pipe.predict_proba` 最大差 <1e-9。
- [x] E3a-2 列线图 `(β_raw,b0_raw)` 对原始 X 的 `sigmoid(lp)` 与 Pipeline 最大差 <1e-6（logistic/L1/弹性网）。
- [x] E3a-3 分类变量（教育程度）改变取值概率变化。
- [x] E3b-1 真实斜率 0.6、n=5000，估计在 0.6±0.08。
- [x] E3b-2 完美校准数据斜率≈1、CITL≈0（±0.1）。
- [x] E3c-1 打桩断言 CatBoost.fit 无 `eval_set`（或 eval_set 不在 X_test）。
- [x] E3c-2 注册表参数名与工厂读取键一致（采用解析 `types/index.ts` 的测试方案）。
- [x] E3d 工厂读 `minSamplesSplit`+`minSamplesLeaf`，注册表补 `minSamplesLeaf`。
- [x] E3e demo 缺失数据 `/api/diagnostics/missing` 200 且“中性粒细胞”MissingCount>0。
- [x] E3f 只删结局缺失，X 缺失交由 Pipeline；summary 写明删除行数与填补方式。
- [x] E3g-1 `modelType="svm"` 构造 `SVC`（非 LogisticRegression）。
- [x] E3g-2 未知 `modelType="foo"` 返回 422。
- [x] E3h-1 `evalDataset="train"` 200；`both` 含训练集与测试集两组指标。
- [x] E3h-2 `threshold=0.3` 与 `0.7` 灵敏度不同。

## REPAIR_LOG 追加记录

已贴，八条（`REPAIR_LOG.md` 末尾“2026-10-17 · task-E3”段）。

## 待人工确认（🧑‍⚖️）

- **E3f 数值变化发布说明**：X 缺失不再整行删除（改为训练集中位数/参照水平填补），已有分析结果会变化；合并上线前需在发布说明中告知用户。
- 计算器仅支持 logistic/lasso/elastic-net；其余模型前端显示“暂不可用”原因。
- `/api/datasets/{id}/variables` 新增 `levels/min_value/max_value` 字段（只加不删，旧前端兼容）。

## 发现但未处理

- `frontend/src/types/index.ts` 中 `random-forest` 注册了 `maxFeatures`，但 `core/models.py` 的 RF 工厂未读取；`mlp` 的 `activation` 等也未读取。属于参数未接线，不在 E3 a–h 范围，未改动。
- `logistic_service.py` 允许任意 `penalty`/`solver` 组合（如 l1+lbfgs），前端可选出不兼容组合；E3a 的 predict 复刻了同样行为，未额外修正。
- 数据集变量水平 `levels` 最多返回前 100 个分类水平（防止超大类别列撑爆响应）。
