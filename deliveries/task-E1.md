# task-E1 交付说明 · 报告下载安全（P0）

## 任务ID / 分支 / 基线提交

- 任务：task-E1 报告下载可泄露签名密钥 → 可伪造任意用户
- 分支：`fix/E1-report-security`
- 基线：`origin/main` @ `1b7b809`（E0 测试脚手架）；完成后已 rebase 到最新 `origin/main` @ `34ba9da`（E2/E7 已合并）
- 仓库：Easy_R_v2

## 改动文件（文件:行号范围）

- `backend/app/services/auth_service.py:20-32, 35-38, 72-95`
  - 密钥优先读 `EASYR_AUTH_SECRET`；否则读 `EASYR_SECRET_FILE`（默认 `DATA_DIR/../secrets/auth_secret.txt`，在 `DATA_DIR` 之外），不存在时生成并 `chmod 600`。
  - `_ensure_storage()` 不再在 `DATA_DIR/auth_secret.txt` 创建密钥。
- `backend/app/services/report_service.py:23-39, 103, 161, 214, 246`
  - 新增文件名正则 `REPORT_FILENAME_RE`、`get_user_reports_dir()`、`_new_report_path()`。
  - `generate_word_report(report_data, user_id)` / `generate_pdf_report(report_data, user_id)` 输出到 `DATA_DIR/users/{user_id}/reports/report_{yyyymmddHHMMSS}_{secrets.token_urlsafe(12)}.{docx|pdf}`。
- `backend/app/routers/report.py:6-10, 21, 23, 37-49`
  - 生成接口传入 `current_user.id`；下载接口先校验文件名正则，再用 `os.path.realpath` 限定在本用户 `reports/` 目录下，否则 404。
- `frontend/src/services/api.ts:87-102`
  - 新增 `downloadReportFile(filename)`：带 `Authorization` 的 axios blob 请求 → `URL.createObjectURL` → 临时 `<a download>` 点击 → `revokeObjectURL`。
- `frontend/src/components/Wizard/steps/Step10Report.tsx:5, 14, 62, 73-85, 121-128, 137`
  - 下载按钮改为 `onClick` 调用 `downloadReportFile`；移除直接 `href` 打开（浏览器不会带 token，必然 401）；预览 iframe 增加 `sandbox=""`。
- `backend/tests/test_report_security.py`（新增）
- `REPAIR_LOG.md:109` 追加本次记录
- `README.md:70` 增加签名密钥配置与轮换说明

## 测试

新增 `backend/tests/test_report_security.py`，覆盖：

- 登录用户请求 `auth_secret.txt`、`../auth_secret.txt`、`%2e%2e%2fauth_secret.txt` 均 404；
- `DATA_DIR/auth_secret.txt` 不存在、默认密钥路径在 `DATA_DIR` 之外；
- `EASYR_AUTH_SECRET` 生效：该密钥可验签，换密钥后旧 token 401；
- 未设置 env 时按 `EASYR_SECRET_FILE` 生成并复用密钥文件；
- 用户 A 的报告 B 下载 404、A 下载 200 且 Content-Type 正确、落盘在 A 的 `reports/`；
- DATA_DIR 根目录旧式可猜文件名不再可下载。

### pytest -q

```text
15 passed, 5561 warnings in 12.44s
```

完整输出：`D:\agent-workspace\deliveries\task-E1\pytest-output.txt`

运行环境（本地容器/环境与仓库 pin 对齐）：`fastapi 0.111.0 / pydantic 2.7.0 / starlette 0.37.2 / httpx 0.27.0`。

### npm run build

```text
> easyr-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
✓ 3107 modules transformed.
dist/index.html                   0.40 kB │ gzip: 0.32 kB
dist/assets/index-CVNQmoT_.js 1,269.11 kB │ gzip: 400.41 kB
✓ built in 15.64s
```

完整输出：`D:\agent-workspace\deliveries\task-E1\npm-build-output.txt`

### 页面手工下载（截图）

通过真实页面登录（e1demo）→ 分析历史 → 恢复向导（第 10 步）→ 生成报告 → 点击"下载报告"，浏览器实际下载成功：

```text
DOWNLOAD {"suggested":"report_20261017234005_TSiVVe78mvtQccvx.docx","size":37883}
NETWORK [{"url":".../api/report/download/report_20261017234005_TSiVVe78mvtQccvx.docx","status":200,
          "contentType":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}]
MANUAL UI DOWNLOAD PASSED
```

截图（本地 deliveries，不入 git）：

- `D:\agent-workspace\deliveries\task-E1\step10-report-ready.png`
- `D:\agent-workspace\deliveries\task-E1\step10-after-download.png`
- 实际下载文件：`D:\agent-workspace\deliveries\task-E1\downloaded-report_20261017234005_TSiVVe78mvtQccvx.docx`

## 验收逐条核对

- [x] 登录用户请求 `/api/report/download/auth_secret.txt`、`../auth_secret.txt`、`%2e%2e%2fauth_secret.txt` 均返回 404（pytest 参数化用例 + 运行中服务 curl 复核 404）。
- [x] `DATA_DIR` 下不存在 `auth_secret.txt`；设置 `EASYR_AUTH_SECRET` 后 token 用它签名（该密钥可验签，换密钥则 401）。
- [x] 用户 A 生成的报告，用户 B 带自己的 token 下载 → 404；A 自己下载 → 200，`Content-Type` 为 `application/vnd.openxmlformats-officedocument.wordprocessingml.document`。
- [x] 前端 `npm run build` 通过；页面点击"下载报告"文件成功下载（截图见上）。

## 部署操作步骤（供人执行）

1. 生成新密钥（示例，不写入仓库）：`python -c "import secrets; print(secrets.token_urlsafe(48))"`。
2. 在 Easy_R_v2 生产环境设置 `EASYR_AUTH_SECRET=<新密钥>`（推荐；配置文件/进程环境均可）。若选择文件方式，则改设 `EASYR_SECRET_FILE=/绝对路径/auth_secret.txt`，该文件必须在 `DATA_DIR` 之外，首次启动会自动生成并 `chmod 600`。
3. 重启 Easy_R_v2 服务（由人执行；本任务未重启任何生产服务）。
4. **旧 token 全部失效**：旧密钥可能已泄露，所有用户需要重新登录，这是期望行为。
5. 确认新密钥工作后，删除旧密钥文件 `backend/data/auth_secret.txt`（新代码不再读取；确认无回滚需求后再删）。

## REPAIR_LOG 追加记录

已追加：`## 2026-10-17 · task-E1 报告下载安全（P0）`。

## 待人工确认（🧑‍⚖️）

- **D2 密钥存放方式**：当前实现两者皆可——优先环境变量 `EASYR_AUTH_SECRET`，回退文件 `EASYR_SECRET_FILE`（默认 `DATA_DIR/../secrets/auth_secret.txt`）。生产最终采用哪一种请确认；无论哪种，上线都必须轮换密钥。

## 发现但未处理

- `DATA_DIR` 根目录下历史报告文件未自动清理（已不可下载，避免越权删数据）；建议人工确认后删除。
- PDF 生成路径已同步改为按用户目录存放，但本地测试环境未安装 `reportlab`，手工下载验证使用 Word 格式；代码路径与 Word 完全一致。
- 前端无自动化测试框架（E0 仅后端脚手架），本次下载验证采用真实浏览器手工流程 + 截图。
- 生成接口响应仍保留 `download_url` 字段（API 只加字段不删不改名）；前端已改用 `filename` + `downloadReportFile`。
