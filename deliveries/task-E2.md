# task-E2 交付说明

## 任务ID / 分支 / 基线提交

- 任务ID：`task-E2`
- 分支：`fix/E2-bootstrap-resample`
- 基线提交：`1b7b809849a2753b1eadc58d0358e949435e506b`（`origin/main`，含 E0 合并 `1b7b809`）

## 改动文件（文件:行号范围）

- `backend/app/services/core/validation.py:72-143`：重写 `optimism_bootstrap` 的抽样/训练/OOB 下标构造。
  - `:91-98`：有分组时循环外预计算 `pos_by_unit`；无分组时 `units=np.arange(n)`。
  - `:107-113`：`chosen = rng.choice(units, size=len(units), replace=True)`；有分组时 `idx = np.concatenate([pos_by_unit[u] for u in chosen])`（保留重复组），无分组时 `idx = chosen`（保留重复样本）；`oob = np.setdiff1d(np.arange(len(X)), idx)`；`Xb, yb = X.iloc[idx], y[idx]`。
  - `:114-124`：训练与表观 AUC 改用 `Xb, yb`；`auc_test` 仍在原始全样本上计算；OOB AUC 改用 `X.iloc[oob]` / `y[oob]`。
  - `:142`：返回字典新增 `"resampling": "with_replacement"`。
- `backend/app/services/ml/validation_service.py:83,90-94`：结果表格新增“重抽样方式=有放回（重复抽中的单位保留重复样本）”，summary 文字同步注明有放回重抽样与重复样本保留。
- `backend/tests/test_bootstrap.py:1-204`：新增 4 个回归测试。
- `REPAIR_LOG.md:109-117`：追加 E2 修复记录。

## 符号/统计约定

- **抽样单位**：有 `groups` 时为患者组，否则为单条样本；每次有放回抽 `n` 个单位（`n` = 单位总数）。
- **训练集**：被抽中单位包含的全部原始样本；**重复抽中的单位/样本在训练集中保留重复**（标准 bootstrap）。有分组时训练行数 = 被抽中各组样本数之和（含重复抽中的组），因此可能大于原始样本量。
- **OOB（out-of-bag）**：原始数据中**从未被抽中**的样本；有分组时即所属组整体未被抽中的样本。OOB 下标为 `setdiff1d(arange(n), idx)`。
- **表观 AUC（apparent）**：全样本拟合模型在原始全样本上的 AUC（`res["apparent_auc"]`）。
- **auc_boot**：本次重抽样训练集上的表观 AUC（在含重复样本的训练集上评估）。
- **auc_test**：本次重抽样模型在原始全样本上的 AUC（乐观度校正的标准做法，不作 OOB 替代）。
- **乐观度**：`optimism = auc_boot - auc_test`；**校正 AUC**：`corrected_auc = apparent_auc - mean(optimism)`。
- **OOB AUC**：每次重抽样模型在未抽中样本上的 AUC；均值与 95%CI 仅统计满足 `len(oob) >= 10` 且 OOB 内两类齐全的有效重复。若某次所有单位都被抽中，则该次无 OOB，不参与 OOB 汇总。

## 测试

新增 `backend/tests/test_bootstrap.py`：

- `test_no_group_trains_on_n_rows_every_bootstrap`：打桩 `make_pipeline`，无分组时每次 `fit` 训练行数恒为 `n`（明确排除旧实现约 0.63n 的去重结果）。
- `test_grouped_fit_rows_equal_sum_of_chosen_group_sizes`：打桩记录 `rng.choice` 的 `chosen`，断言每次训练行数 = 被抽中组样本数之和（组样本量 5~10 不等），且训练集的组集合 = `chosen` 去重集合。
- `test_grouped_oob_groups_are_never_chosen`：从每次 `predict_proba` 输入恢复 OOB 集合，断言 OOB 组与 `chosen` 不相交，且恰为“所有组 − 被抽中组”。
- `test_demo_logistic_corrected_le_apparent_and_n_boot`：demo 数据 + logistic + `B=50`，断言 `corrected_auc <= apparent_auc`、`n_boot >= 45`、`resampling == "with_replacement"`。

命令：`cd backend && pytest -q`（本地隔离 venv：Python 3.11.7，按 `requirements.txt` 固定 fastapi 0.111.0 / pydantic 2.7.0 / starlette 0.37.2，`requirements-dev.txt` 固定 httpx 0.27.0）

```text
......                                                                   [100%]
6 passed, 5560 warnings in 22.67s
```

完整输出：`D:\agent-workspace\deliveries\task-E2\pytest.log`。

数据目录污染检查：`git status --short -- backend/data` 输出为空。

## 验收逐条核对

- [x] 打桩 `make_pipeline` 记录每次 `fit` 训练集行数：无分组时每次都等于 n（测试 1）；有分组时等于被抽中单元样本数之和（含重复，测试 2，使用不等组样本量以区分旧实现）。
- [x] 有分组时，OOB 样本所属的组都不在 `chosen` 中（测试 3，并验证 OOB = 全组 − chosen）。
- [x] demo 数据、logistic、B=50：`corrected_auc ≤ apparent_auc`，`n_boot ≥ 45`（测试 4，实测 `n_boot=50`）。
- [x] 返回字典新增 `"resampling": "with_replacement"`，报告表格与 summary 文字同步。
- [x] 全量 `pytest -q`：6 passed。

## REPAIR_LOG 追加记录

已追加（`REPAIR_LOG.md:109-117`，2026-10-17 · task-E2）。

## 待人工确认（🧑‍⚖️）

- 🧑‍⚖️ **分组重抽样训练集规模**：按患者整组有放回抽样时，重复抽中的组会整组重复进入训练集，训练行数可大于原始样本量（这是“按患者 bootstrap”的直接推论，已按任务原文实现）。若产品希望改为“按组重抽样但训练集去重”，需要另立统计决策。
- 🧑‍⚖️ **校正 AUC 的边界**：`corrected_auc = apparent - mean(optimism)` 不保证永远 ≤ apparent（个别弱模型/小样本可出现负乐观度），也不保证落在 [0,1]；当前不做截断，沿用原文公式。是否需要在报告层截断或提示，请确认。
- 🧑‍⚖️ **OOB AUC 的用途**：当前 OOB AUC 仅作参考汇总，不作为校正 AUC 的替代；若希望把 OOB AUC 作为主要内部验证指标（如 0.632+ bootstrap），属于后续统计方案（E3/报告规范）范围。

## 发现但未处理

- 基线环境（Anaconda 全局）为 pydantic 1.10.12 / httpx 0.28.1 / fastapi 旧版，与 `requirements.txt` / `requirements-dev.txt` 的锁定版本不一致：初始全量测试出现 `Client.__init__() got an unexpected keyword argument 'app'` 与 `'MLRequest' object has no attribute 'model_dump'`。本次未改仓库依赖，改为在本地隔离 venv 安装锁定版本后验收（全绿）。建议后续统一开发环境或补 `starlette` 锁定。
- pytest 的 5560 条 warning 均为既有依赖/代码的弃用提示（pandas/sklearn deprecation、matplotlib 字体等），不属于本任务范围。
- 未触碰服务器；未重启服务；未提交大数据、密钥或用户数据。
