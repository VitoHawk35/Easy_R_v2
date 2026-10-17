# task-E4 向导状态

任务ID / 分支 / 基线提交：**E4 / `fix/E4-wizard-state` / `fe41e7ab84bebeff8603ca72400542c7f638d760`**（最新 `origin/main`，包含 E0 `1b7b809`，并已合入 E1/E2/E3/E7）

实现提交：`06f9066`（交付说明随分支追加提交）

## 改动文件（文件:行号范围，按 a–f 分列）

### E4a 切换标签页 / 刷新清空向导
- `frontend/src/App.tsx:28-34, 69-91, 238-260`：`WizardProvider` 提升到 `App` 层；登录后包住整个标签页区域；进入向导用 `RESTORE_SNAPSHOT` dispatch，不再依赖 `restoreSnapshot` prop。
- `frontend/src/components/Wizard/WizardContainer.tsx:1-3, 49-61, 114-120`：删除容器内的 Provider 与恢复 effect，只渲染 `WizardInner`；变量刷新仅在非空时 dispatch。
- `frontend/src/context/WizardContext.tsx:4-21, 22-36, 38-67, 408-446`：新增 `WIZARD_STORAGE_KEY='easyr_wizard_v1'`、`serializeWizardState`（去掉所有 charts/SVG 与 `previewData`）、`deserializeWizardState`、懒加载恢复；Provider `useEffect` 每次状态变化写 sessionStorage；`buildRequest` 复用同一序列化函数。
- `frontend/src/context/AuthContext.tsx:4, 47-52`：主动登出时清空 `easyr_wizard_v1`；刷新导致的强制重登不清空（D8 保留）。
- `frontend/src/types/index.ts:182, 196, 208`：`WizardState` 增加 `idVariables`、`modelFeatures`、`staleSteps`。

### E4b 上游改动使下游失效
- `frontend/src/context/WizardContext.tsx:187-212`：新增纯函数 `invalidateFrom(state, step)`，清空 step 及之后的结果字段和 `completedSteps`。
- `frontend/src/context/WizardContext.tsx:282-409`：`SET_DATASET / SET_Y_VARIABLE / SET_SURVIVAL / SET_GROUP_VARIABLE / SET_ID_VARIABLES` → 从第 1 步失效；`SET_REMOVED_VARS` → 第 2 步；`SET_FILTER_RESULTS`、`SET_FORCED_INCLUDE_VARS` → 第 3 步；`SET_BUILD_MODE / SET_SELECTED_MODEL / SET_COMPARE_MODELS / SET_MODEL_PARAMS / SET_MODEL_FEATURES / SET_BUILD_RESULT / SET_BEST_MODEL` → 第 4 步。值未变化时直接返回原 state。
- `frontend/src/components/Wizard/StepNavigator.tsx:20-45`：使用 `staleSteps`，已清空步骤显示“需重跑”。

### E4c 第 5–9 步使用第 4 步模型
- `frontend/src/types/index.ts:90, 196`: `MLResult.removed_vars`、`WizardState.modelFeatures`。
- `frontend/src/context/WizardContext.tsx:228-247`：`effectiveModelFeatures(state)`：优先 `modelFeatures`，其次 `filterResults.final`（按候选变量过滤），最后回退 `featureCandidates`。
- `frontend/src/components/Wizard/steps/Step4ModelBuild.tsx:25-31, 72-73, 113`：`mergedVars = finalVars ∪ forcedIncludeVars`；单模型与对比分支建模成功后都 dispatch `SET_MODEL_FEATURES`。
- `frontend/src/components/Wizard/steps/Step5Eval.tsx:11-18, 45`：`x_variables = effectiveModelFeatures(state)`；`params.model_params = { [bestModel]: modelParams[bestModel] }`。
- `frontend/src/components/Wizard/steps/Step6Visual.tsx:22-29, 131, 168, 172`：使用 `effectiveModelFeatures`；nomogram 同时传 `modelParams` 与 `model_params`，calibration/dca 传 `model_params`。
- `frontend/src/components/Wizard/steps/Step7Explain.tsx:11-19, 33, 58`：SHAP/PDP 使用 `effectiveModelFeatures` 并传 `model_params`。
- `frontend/src/components/Wizard/steps/Step8AdvDiag.tsx:11-15, 32-37`：高级诊断使用 `effectiveModelFeatures` 并传 `model_params`。
- `frontend/src/components/Wizard/steps/Step9Validate.tsx:11-19, 28, 40, 52`：Bootstrap/外部验证使用 `effectiveModelFeatures` 并传 `model_params`。

### E4d 分组/ID 变量排除；RF 按 Top-K 入选
- `frontend/src/context/WizardContext.tsx:214-226`：新增 `featureCandidates(state)`，排除 Y、时间变量、分组变量、用户标记的 `idVariables`，以及列名大小写不敏感等于 `id` 的列；`effectiveModelFeatures` 复用该候选集。
- `frontend/src/components/Wizard/steps/Step1DataPrep.tsx:16, 384-401`：新增“ID 变量（可选）”多选，dispatch `SET_ID_VARIABLES`，说明标记后不作为模型特征、名为 `id` 的列自动排除。
- `frontend/src/components/Wizard/steps/Step2Diagnostics.tsx:15-16`：诊断 X 变量改用 `featureCandidates(state)`。
- `frontend/src/components/Wizard/steps/Step3VarFilter.tsx:10-14, 101-109, 209-221`：可用变量改用 `featureCandidates`；RF 由“重要性 > 0”改为按重要性降序取前 `rfTopK`（默认 10，输入框可配置），页面增加规则说明。
- `frontend/src/components/Wizard/steps/Step4ModelBuild.tsx:26-31`：候选变量、`finalVars`、`forcedVars` 全部经 `featureCandidates` 过滤。

### E4e VIF 自动移除可靠返回
- `backend/app/models/schemas.py:32`：`MLResult.removed_vars: List[str]`。
- `backend/app/services/ml/diagnostics_service.py:92-98`：自动移除时写 `removed_vars` 并同步到 `model_info.removed_vars`；未移除时返回空数组。
- `frontend/src/components/Wizard/steps/Step2Diagnostics.tsx:44-48`：删除正则解析，直接读取 `res.removed_vars ?? res.model_info?.removed_vars`。

### E4f 其他
- `frontend/src/components/Wizard/steps/Step9Validate.tsx:61-71`：新增 `didRunAny`，未运行任何验证时 warning 并 return，不再 `markComplete(8)`。
- `frontend/src/context/WizardContext.tsx:22-36, 441-446`：持久化与每个请求的 `wizard_snapshot` 共用 `serializeWizardState`，去掉所有 SVG/图表及 `previewData`。
- `frontend/package.json:9, 26-27`：新增 `"test": "vitest run"` 与 devDependency `vitest ^3.2.7`；`frontend/package-lock.json` 同步。
- `frontend/src/context/WizardContext.test.ts:1-248`：新增 13 个 vitest 用例。

## 测试

### `npm run test`

```
> easyr-frontend@1.0.0 test
> vitest run

 RUN  v3.2.7 D:/agent-workspace/worktrees/task-E4/frontend

 ✓ src/context/WizardContext.test.ts (13 tests) 5ms

 Test Files  1 passed (1)
      Tests  13 passed (13)
   Start at  00:02:31
   Duration  1.07s (transform 59ms, setup 0ms, collect 144ms, tests 5ms, environment 0ms, prepare 490ms)
```

覆盖点：`featureCandidates` 排除 Y/时间/分组/用户 ID/`id`；`invalidateFrom` 清空下游结果与完成标记并标记 stale；改 Y 清空 1–9 步；同值不失效；`SET_REMOVED_VARS` 从第 2 步失效；筛选/强制纳入从第 3 步失效；模型参数从第 4 步失效；`MARK_STEP_COMPLETE` 清除 stale；序列化去掉 charts 与 `previewData`。

### `npm run build`

```
> easyr-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
✓ 3107 modules transformed.
dist/index.html                   0.40 kB │ gzip:   0.33 kB
dist/assets/index-BwTNDNhJ.js 1,274.36 kB │ gzip: 402.00 kB
(!) Some chunks are larger than 500 kB after minification. ...
✓ built in 12.41s
```

`tsc` 与 `vite build` 均通过；仅有既有的 chunk > 500 kB 警告，无类型错误。

### 手工验收

1. **切标签页保留状态**：完成到第 5 步（模型评估已完成）→ 切到“Logistic回归”标签页（向导 DOM 消失，`.ant-steps` 数量 0）→ 切回“向导式分析”，步骤条仍为第 5 步“已完成”，评估结果（校准/DCA）仍在。截图：`D:\agent-workspace\deliveries\task-E4\evidence\e4-back-to-wizard2.png`。
2. **刷新 + 重新登录恢复**：F5 后 `localStorage.easyr_token` 为 null、显示登录页，`sessionStorage.easyr_wizard_v1` 长度 9499 未被清除；重新登录后进入向导，恢复到第 5 步且评估结果仍在。截图：`e4-after-refresh-login.png`、`e4-restored-step5.png`。
3. **强制纳入变量进入 Step5 请求**：Step4 将“性别”加入“强制纳入变量”，Step5 评估请求 `POST /api/ml/calibration` 与 `/api/ml/dca` 的 `x_variables` 均包含 `...\"年龄\",\"性别\"`，且 `params.model_params` 存在。浏览器 Network → Payload 截图：`D:\agent-workspace\deliveries\task-E4\evidence\e4-network-payload-xvariables.png`（展开 `x_variables`，第 12 项为 `\"性别\"`）；请求列表截图：`e4-devtools-real-network.png`。
4. **复验（rebase 到 `fe41e7a` 后）**：重新执行刷新→重登→向导恢复、切标签页、Step5 评估；两条请求都包含 `性别` 与 `model_params`。截图/日志：`e4-final-step5.png`、`npm-test-after-rebase.log`、`npm-build-after-rebase.log`。

后端编译检查：`python -m py_compile backend/app/models/schemas.py backend/app/services/ml/diagnostics_service.py` 通过。

## 验收逐条核对（按 a–f + 整体）

- [x] E4a Provider 提升到 App 层；切标签页/刷新重登后状态恢复；登出清空；持久化不含 SVG/previewData。
- [x] E4b `invalidateFrom` + reducer 接入；上游变更清空下游结果；导航显示“需重跑”。
- [x] E4c Step4 保存 `modelFeatures`/`modelParams`；Step5–9 统一 `x_variables` 与 `model_params`；强制纳入变量进入评估请求。
- [x] E4d `featureCandidates` 排除 Y/时间/分组/用户 ID/`id`；RF 改为 Top-K（默认 10，可配置）。
- [x] E4e `MLResult.removed_vars` + 后端写入；前端直接读取，正则已删除。
- [x] E4f Step9 未运行任何验证不标完成；请求体与持久化共用精简序列化。
- [x] 整体：`npm run build` 通过；13 个 vitest 用例通过；手工验收 1–3 项通过，rebase 后复验通过。

## 待人工确认（🧑‍⚖️）

- **D8 已保留**：每次刷新强制重新登录的行为不变；向导状态存 `sessionStorage['easyr_wizard_v1']`，重新登录后恢复；主动登出清空。
- 前端 API 响应新增字段 `removed_vars` 属于只加字段，不删不改名。
- 未自行部署/重启服务器；未推送 `main`；未合并。

## 发现但未处理

- 无新增阻塞项。E3 合并后后端 `eval_service/explain_service/predict_service/compare_service/validation_service` 已兼容 `model_params`，E4c 的统一传参可直接使用。
- RF 的 \(K\) 默认 10 为经验值（任务允许“前 k 个，k 可配”）；如需按数据规模自适应，可后续调整默认值。
- 生产环境端口/服务未触碰；本机验收使用的 FastAPI 8000 + Vite 5174 仅用于本地验证。
