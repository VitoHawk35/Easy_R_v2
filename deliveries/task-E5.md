# task-E5 · Easy_R_v2 安全与健壮性 — 交付说明

## 任务ID / 分支 / 基线提交

- 任务 ID：task-E5（安全与健壮性，P1–P2）
- 分支：`fix/E5-hardening`
- 基线：`origin/main` @ `34ba9da8f02d9e252a1155b38dca4534ab5a4d0e`（已包含 E0；分支创建时为 `1b7b809`，收工前已 rebase 到最新 main，含 E2/E7 合并）
- 工作目录：`D:\agent-workspace\worktrees\task-E5`
- 测试环境：Python 3.11.7（隔离 venv：`D:\agent-workspace\.venv-E5`，按 `backend/requirements-dev.txt` 固定 `httpx==0.27.0`；Node 22 / npm 10）

## 改动文件（文件:行号范围）

| 文件 | 行号 | 改动 |
|---|---|---|
| `backend/app/main.py` | 1–25 | CORS 白名单改为 `EASYR_CORS_ORIGINS`（逗号分隔，默认空）；移除 `allow_origins=["*"]` |
| `backend/app/routers/datasets.py` | 13–40, 78–81 | 分块复制上传内容并累计字节；超过 `EASYR_MAX_UPLOAD_MB`（默认 50）返回 413 |
| `backend/app/services/auth_service.py` | 19–30, 49–120, 187–208 | `users.json.lock` 排他锁包住注册“读—改—写”（Linux `fcntl.flock`，Windows 测试 `msvcrt`）；原子写临时文件名加 pid + 线程号 |
| `backend/app/services/data_service.py` | 213–230 | `assert_dataset_access` 确认权限后顺带加载数据到进程内缓存，修复重启后 `get_data_for_ml` 路径 |
| `backend/tests/test_e5_hardening.py` | 新增 | 5 个验收测试（413、20 线程并发注册、重启后 ML、CORS 默认/环境变量） |
| `frontend/src/utils/sanitizeSvg.ts` | 新增 | DOMPurify SVG profile 清洗封装 |
| `frontend/src/utils/sanitizeSvg.test.ts` | 新增 | vitest：`<script>` / `onload=` / `onclick=` 被清除，正常 SVG 保留 |
| `frontend/src/components/ResultDisplay/ResultDisplay.tsx` | 5, 35 | SVG 经 `sanitizeSvg()` 后再 `dangerouslySetInnerHTML` |
| `frontend/vitest.config.ts` | 新增 | vitest + jsdom 配置 |
| `frontend/package.json` | scripts / deps | 新增 `dompurify`；devDeps `vitest`、`jsdom`；`test` 脚本 |
| `frontend/.env.production` | 1 | `VITE_API_BASE_URL` 由 `http://10.39.15.238:8006/api` 改为 `/api`（同源经 nginx） |
| `frontend/nginx.conf` | 7–8 | 新增 `client_max_body_size 50m;` |
| `REPAIR_LOG.md` | 末尾追加 | task-E5 记录 |

## 测试：新增了哪些测试

- `backend/tests/test_e5_hardening.py`
  - `test_upload_60mb_returns_413`：默认 50MB 限制下上传 60MB CSV → 413。
  - `test_concurrent_registration_keeps_all_20_users`：20 个线程并发注册不同用户，`users.json` 精确增加 20 条（连续跑 5 次均通过）。
  - `test_ml_succeeds_after_cache_clear`：上传 → 清空 `_datasets`/`_dataset_meta` → 调 `GET /api/datasets`（只恢复 meta，复现真实路径）→ `POST /api/ml/logistic` 返回 200。
  - `test_cors_origins_default_is_empty` / `test_cors_origins_read_from_env`：D2 环境变量行为。
- `frontend/src/utils/sanitizeSvg.test.ts`（vitest + jsdom）：含 `<script>`、`onload=`、`onclick=` 的 SVG 清洗后不再包含它们，正常 `<rect>/<text>` 保留。

### pytest -q 输出

```text
11 passed, 5795 warnings in 18.34s
```

（完整输出：`D:\agent-workspace\deliveries\task-E5\pytest.txt`）

### npm run build 输出

```text
> easyr-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 3109 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.40 kB │ gzip:   0.32 kB
dist/assets/index-b28o9tcm.js 1,300.59 kB │ gzip: 413.12 kB
(!) Some chunks are larger than 500 kB after minification. ...
✓ built in 8.03s
```

构建退出码 0。已核对产物：不再包含 `10.39.15.238`，`VITE_API_BASE_URL=/api` 生效，DOMPurify 已打包。
（完整输出：`D:\agent-workspace\deliveries\task-E5\npm-build.txt`）

### npm test（vitest）输出

```text
 ✓ src/utils/sanitizeSvg.test.ts (2 tests) 12ms
 Test Files  1 passed (1)
      Tests  2 passed (2)
```

（完整输出：`D:\agent-workspace\deliveries\task-E5\vitest.txt`）

## 验收逐条核对

- [x] 测试：上传 60MB 文件返回 413。`test_upload_60mb_returns_413` 通过。
- [x] 测试：20 个线程并发注册不同用户，最终 users.json 里有 20 个用户。`test_concurrent_registration_keeps_all_20_users` 通过（断言 `len(users) == before + 20` 且用户名全部存在）。
- [x] 测试：上传数据集 → 清空进程内缓存（模拟重启：清空 `_datasets`/`_dataset_meta`）→ 调用 ML 接口仍成功。`test_ml_succeeds_after_cache_clear` 通过。
- [x] 测试（vitest）：含 `<script>` 和 `onload=` 的 SVG 经过清洗后不再包含它们。`sanitizeSvg.test.ts` 2 项通过。
- [x] `npm run build` 通过。
- [x] 修完在 `REPAIR_LOG.md` 追加记录。

## 部署操作步骤（供人执行）

1. 确认后端环境变量（按 D2 结论最终确定）：
   - `EASYR_CORS_ORIGINS`：生产经 nginx 同源访问可留空；若确有跨域来源，逗号分隔填写（不要用 `*`，因为 `allow_credentials=True`）。
   - `EASYR_MAX_UPLOAD_MB`：默认 50；若调整，务必同步修改 `frontend/nginx.conf` 的 `client_max_body_size`。
2. 重新构建前端（`VITE_API_BASE_URL` 构建时烧死，改 `.env.production` 后必须重建）：
   ```bash
   cd frontend && npm ci && npm run build
   # 或在仓库根目录：docker compose build frontend
   ```
3. 上传/替换 `dist` 或重建 frontend 镜像。
4. 重启后端与 nginx（由人操作；本 agent 未触碰服务器，未重启任何服务）。
5. 冒烟：`/api/health`；上传 60MB 文件应被 nginx/后端拒绝；正常小文件上传及 ML 流程可用。

## REPAIR_LOG 追加记录：已贴

见 `REPAIR_LOG.md` 末尾「2026-10-17 · task-E5 安全与健壮性」。

## 待人工确认（🧑‍⚖️）

**D2：Easy_R_v2 生产端口与 CORS 白名单取值（未拍板）**

- 生产实际端口待确认：任务文件写服务器 `~/Easy_R_v2` 为 **8006/8091**；仓库内 `docker-compose.yml` 为 backend `8005:8000`、frontend `8090:80`；`frontend/nginx.conf` 上游为 `backend:8000`（容器内）。本次**未改动任何端口**，也未把端口/域名写死；前端改为同源 `/api` 后不再依赖外部端口。
- CORS 白名单取值待确认：`EASYR_CORS_ORIGINS` 默认空（同源部署适用）。若生产/联调需要跨域（例如 `http://<生产IP>:8091` 或独立 API 域名），请给出确切 origin 列表，再通过环境变量注入。
- 本次按默认建议实现为环境变量可配置，没有擅自选择“不留白名单”或“全部放开”。

## 发现但未处理

- `frontend/.env.production` 改动只有重新构建才生效（已在部署步骤强调）。
- `users.json` 的锁只覆盖 `auth_service` 的注册/读取路径；`data_service` 的用户数据集 registry（`datasets.json`）仍是“读—改—写”，不在本任务范围，未改动。
- token 仍存于 localStorage（报告问题清单中的相关项），本任务只处理 SVG 注入；如需迁移到 HttpOnly Cookie，建议单独立项。
- 本机 Anaconda 基础环境为 pydantic 1.10 / httpx 0.28，与仓库固定的 pydantic 2.7 / httpx 0.27 不一致；验收使用隔离 venv 运行，未修改用户基础环境。生产 Docker 按 `requirements.txt` 安装，不受影响。
