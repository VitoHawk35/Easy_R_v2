# task-E0 交付说明

## 任务ID / 分支 / 基线提交

- 任务ID：`task-E0`
- 分支：`fix/E0-test-scaffold`
- 基线提交：`9332500ccbe9d07bf11c8d5e17b0914565b168dd`（`origin/main`）

## 改动文件（文件:行号范围）

- `backend/app/settings.py:1-8`：新增集中路径配置；`EASYR_DATA_DIR` / `EASYR_DEMO_PATH` 可覆盖默认值，默认仍为原 `backend/data/` 与 `backend/data/demo.csv`。
- `backend/app/services/data_service.py:9-12,100-114`：改为从 `app.settings` 导入 `DATA_DIR` / `DEMO_DATA_PATH`；`load_demo_data` 读取 `DEMO_DATA_PATH`。
- `backend/app/services/report_service.py:14-19`：改为从 `app.settings` 导入 `DATA_DIR`。
- `backend/tests/conftest.py:1-62`：新增 pytest 脚手架；在导入 app 前设置隔离数据目录、测试密钥占位和 `MPLBACKEND=Agg`；提供 `client`、`auth_headers`、`ml_request` fixtures。
- `backend/tests/test_smoke.py:1-16`：新增 `/api/health` 与登录后 `/api/ml/logistic` 冒烟测试。
- `backend/requirements-dev.txt:1-2`：新增 `pytest`、`httpx` 开发依赖。
- `REPAIR_LOG.md:101-107`：追加 E0 修复记录。

## 测试

新增测试：

- `test_health`：GET `/api/health` 返回 200 与 `{"status": "ok"}`。
- `test_logistic_smoke`：注册并登录测试用户后，POST `/api/ml/logistic` 返回 200 且 `success=True`；demo 的数值 0/1 结局在测试中显式标记为 `logical`，以匹配当前 `encode_y` / logistic 服务的既有约定。

后端命令：`cd backend && pytest -q`（在本地隔离 venv 中执行）

```text
..                                                                       [100%]
2 passed, 1124 warnings in 5.37s
```

完整 pytest 输出：`D:\agent-workspace\deliveries\task-E0\pytest.log`。

`backend/data/` 污染检查：`git status --short -- backend/data` 输出为空。记录文件：`D:\agent-workspace\deliveries\task-E0\backend-data-status.log`。

前端命令：`cd frontend && npm ci && npm run build`

```text
npm ci:
added 168 packages in 15s

npm run build:
> easyr-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
✓ 3107 modules transformed.
dist/index.html                   0.40 kB │ gzip:  0.32 kB
dist/assets/index-DQ-r64vn.js  1,268.69 kB │ gzip: 400.32 kB
✓ built in 6.21s
```

完整前端输出：

- `D:\agent-workspace\deliveries\task-E0\npm-ci.log`
- `D:\agent-workspace\deliveries\task-E0\npm-build.log`

## 验收逐条核对

- [x] `cd backend && pytest -q` 通过，且运行后 `git status` 显示 `backend/data/` 无新文件。
- [x] `cd frontend && npm ci && npm run build` 在基线前端代码上通过（仅有 Vite chunk >500 kB 的既有提示，非构建错误）。

## 待人工确认（🧑‍⚖️）

- 🧑‍⚖️ `backend/requirements.txt` 中的 `boruta-py==0.3.1` 在 PyPI 与清华镜像均无可用发行版；本次仅为了完成本地验收，在隔离 venv 的安装清单中改用可提供 `from boruta import BorutaPy` 的 `boruta==0.3`，**未修改仓库锁定依赖**。是否更正锁文件包名/版本，建议后续单独确认。
- 🧑‍⚖️ 当前基线把数值型 0/1 响应变量经 `encode_y` 转成 float 后，`run_logistic` 会判定为“非分类”；E0 测试通过 `variable_types={"结局Y1": "logical"}` 绕过并保持现有产品逻辑不变。是否应在统计任务中把数值 0/1 默认识别为分类，留给 E3 等后续任务确认。

## 发现但未处理

- pytest 的 1124 条 warning 主要来自既有依赖/代码：pydantic `model_` protected namespace、matplotlib/pyparsing deprecation、shap 对 `np.inexact` 的弃用提示；不影响本次冒烟结果，未在 E0 范围内处理。
- 前端构建提示单个 chunk 超过 500 kB，属于既有打包体积优化事项，未处理。
- 未触碰服务器；未重启任何服务；未提交用户数据、密钥或大数据文件。
