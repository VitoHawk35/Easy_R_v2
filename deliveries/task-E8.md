# E8 Easy_R 安装修复（R10）— 交付说明

- 任务ID：E8（R10：Easy_R 装不起来）
- 分支：`fix/E8-install`
- 基线：`origin/main` @ `b3c6ae9`
- 改动文件：仅 `backend/requirements.txt`（2 处）
- `frontend/package-lock.json` 无变化（见下"npm 部分"说明）。

## 改动摘要

| 项目 | 位置 | 改动前 → 改动后 |
|---|---|---|
| Boruta 改名 | backend/requirements.txt:14 | `boruta-py==0.3.1` → `Boruta==0.3`（PyPI 上 boruta-py 已更名为 Boruta，同一作者同一包；模块名仍为 `boruta`，`backend/app/services/ml/boruta_service.py:10` 的 `from boruta import BorutaPy` 不受影响，实测可导入） |
| lightgbm 注释 | backend/requirements.txt:18 | 新增注释 `# On macOS arm64, run \`brew install libomp\` before installing lightgbm` |

注意：requirements.txt 保持纯 ASCII。曾尝试中文注释，在本机（zh-CN，GBK locale）会导致 pip 读文件时 `UnicodeDecodeError: 'gbk' codec ...`——Windows 中文 locale 下 pip 按 GBK 解码 requirements 文件，任何非 ASCII 字符都会炸，故注释一律用英文。

## npm 部分（package-lock.json）

- `frontend/` 下执行 `npm install`（registry 为 npmmirror）：**lock 文件与 package.json 无偏差，npm install 未产生任何 diff**（`git status` / `git diff` 均为空），符合任务卡"若 lock 无偏差则验证 npm ci 现状即可"的约定。
- 删除 `node_modules` 后 `npm ci` → 成功（added 247 packages in 15s，exit 0）。日志：`D:\agent-workspace\deliveries\task-E8\npm-ci.log`。

## 自测验收

1. **干净 Python 3.11 venv 安装** ✅：新建 venv（`D:\mine_Anaconda3\python.exe -m venv`，Python 3.11.7，此前从未安装任何包）执行 `pip install -r backend/requirements.txt` → **exit 0**，单次 `Successfully installed` 行包含全部 21 项依赖（含 `Boruta-0.3`）。导入冒烟：`from boruta import BorutaPy; import lightgbm, xgboost, catboost, shap, fastapi` → OK。完整日志：`D:\agent-workspace\deliveries\task-E8\pip-install.log`。
2. **npm ci** ✅：见上。

环境备注（复现时的坑，非仓库问题）：本机 pip 全局配置的 tuna 镜像当时不可达；aliyun/腾讯镜像下 xgboost 等大 wheel 反复 Hash 校验失败（网络截断污染缓存，需 `pip cache purge`）；最终用官方 PyPI 走 `127.0.0.1:7897` 代理一次通过（`--proxy http://127.0.0.1:7897 -i https://pypi.org/simple`）。

## 主agent验收命令

```bash
# Easy_R_v2 仓库 fix/E8-install 分支
grep -nE 'Boruta|libomp' backend/requirements.txt     # 期望 Boruta==0.3 + libomp 注释
D:\mine_Anaconda3\python.exe -m venv <新目录> && <新目录>\Scripts\python.exe -m pip install -r backend/requirements.txt
# ↑ 期望 exit 0；若镜像不可达加 --proxy http://127.0.0.1:7897 -i https://pypi.org/simple
cd frontend && npm ci                                  # 期望 added ... packages, exit 0
```

## 待人工确认项

- 无。

## 发现但未处理项

- `Boruta==0.3`（2019 年的 sdist）在 pip 新 resolver 下可正常构建安装；若未来升级 Python 3.12+ 需复验（本次按任务卡只验证 3.11）。
