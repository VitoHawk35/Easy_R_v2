# EasyR 临床数据分析系统

仿照 EasyR 的临床数据分析 Web 系统，专注于机器学习模块。

## 技术栈
- **后端**: Python 3.11, FastAPI, scikit-learn, catboost, boruta
- **前端**: React 18, TypeScript, Ant Design 5, Vite
- **部署**: Docker, Docker Compose, Nginx

## 功能模块
- 数据集管理与变量浏览
- 12种机器学习算法:
  - Boruta特征筛选
  - 多个机器学习对比
  - LASSO回归 / Lasso预测模型
  - 贝叶斯核机器回归 (BKM)
  - 决策树 / 随机森林
  - 支持向量机 / K-近邻
  - LDA / QDA
  - CatBoost

## 快速启动

### 方式一: Docker Compose (推荐)
```bash
docker-compose up --build
```
访问 http://localhost

### 方式二: 本地开发

**后端:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**前端:**
```bash
cd frontend
npm install
npm run dev
```
访问 http://localhost:5173

## 目录结构
```
/
├── CLAUDE.md          # 需求文档
├── docker-compose.yml # Docker编排
├── backend/           # FastAPI后端
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   ├── services/
│   │   └── models/
│   └── data/
└── frontend/          # React前端
    ├── src/
    └── nginx.conf
```

## 部署到服务器
1. 将代码上传到服务器
2. 确保 Docker 和 Docker Compose 已安装
3. 运行 `docker-compose up -d`
4. 配置 Nginx 反向代理 (如果需要 HTTPS)

### 签名密钥配置与轮换（安全必读）
- 生产环境必须通过环境变量 `EASYR_AUTH_SECRET` 提供登录 token 的签名密钥（至少 32 字节的随机值）。未设置时回退到文件方式：`EASYR_SECRET_FILE` 指定路径，默认 `DATA_DIR/../secrets/auth_secret.txt`（位于 `DATA_DIR` 之外，首次启动自动生成并 `chmod 600`）。
- **部署本版本后必须更换密钥**：旧版本把 `auth_secret.txt` 放在可下载的 `DATA_DIR` 内，可能已泄露。更换后所有已签发的 token 立即失效，用户需重新登录，这是预期行为。
- 旧的 `DATA_DIR/auth_secret.txt` 可在确认不再使用后删除；新代码不会读取它。

## API文档
启动后端后访问: http://localhost:8000/docs
