# EasyR 临床数据分析系统 - 需求文档

## 项目概述
构建一个仿照 EasyR 的临床数据分析 Web 系统，专注于机器学习模块。支持常见临床机器学习算法，提供**分步骤向导式**变量选择、参数配置、结果可视化与模型对比能力。覆盖从数据准备到报告导出的完整临床ML工作流。

## 技术栈
- **后端**: Python 3.11, FastAPI, scikit-learn, xgboost, catboost, boruta-py, lifelines, shap, pandas, numpy
- **前端**: React 18, TypeScript, Ant Design 5, ECharts, Axios
- **部署**: Docker, Docker Compose, Nginx

## 核心功能模块

### 1. 左侧导航栏
- 基础统计与画图 (FREE)
- 统计模型
- 临床诊断与决策分析
- **机器学习** (当前重点实现)
  - 分析步骤向导 (10步)
  - Boruta 特征筛选
  - 多个机器学习对比
  - LASSO 回归 / Lasso 预测模型
  - 弹性网络 (Elastic Net)
  - Logistic 回归
  - 贝叶斯核机器回归 (BKM)
  - 决策树 / 随机森林
  - XGBoost / LightGBM
  - 支持向量机 / K-近邻
  - 线性判别分析 (LDA) / 二次判别分析 (QDA)
  - CatBoost
  - 神经网络 (MLP)
  - 朴素贝叶斯
  - Cox 回归

### 2. 分步骤向导流程 (10步)
每个机器学习分析按照以下步骤执行：
1. **数据准备** — 数据集选择、行列预览
2. **变量诊断** — VIF共线性分析、相关系数矩阵、缺失值诊断、自动移除高共线性变量
3. **变量筛选** — 多方法组合筛选（单因素筛选、LASSO、随机森林、Boruta）
4. **模型构建** — 选择算法、设置参数、训练模型
5. **模型评估** — 训练集/测试集/两者对比评估
6. **可视化** — Nomogram列线图、森林图、ROC对比、校准曲线、DCA曲线
7. **模型解释性** — SHAP、PDP、ICE
8. **高级诊断** — 残差分析、影响点检测
9. **模型验证** — Bootstrap内部验证、外部验证（上传独立数据集）
10. **导出报告** — PDF/Word报告生成

### 3. 数据工作区
- **数据范围**: 下拉选择数据集，显示行列信息 (如 300×38)
- **筛选条件**: 创建/管理数据筛选条件
- **变量选择面板 (右侧)**:
  - 全选 / 批量选择 (Shift)
  - 搜索过滤
  - 每个变量显示: 名称、类型(连续/分类/逻辑)、取值范围、缺失数量
  - Checkbox 多选
  - 清除/复制/粘贴已选变量

### 4. 算法配置面板
所有算法共享以下交互模式:
- **响应变量 (Y)**: 下拉单选，必选
- **是否为生存数据**: Toggle 开关，切换后显示时间变量输入
- **特征变量**: 从右侧变量列表多选，已选变量显示在输入框内，支持Tag移除
- **算法专属参数**: 根据算法动态渲染
- **通用参数**:
  - 最大迭代次数 (maxRuns): 数字步进器，默认 100
  - 显著性阈值 (pValue): 数字步进器，默认 0.01
  - 随机数种子: 数字步进器，默认 123
  - 图片格式: SVG/PNG 下拉选择
  - 分类阈值: 数字选择 (0-1)

### 5. 评估指标 (分类问题)
- ROC曲线/AUC
- 混淆矩阵
- 校准曲线 (Calibration Curve)
- DCA曲线 (Decision Curve Analysis)
- Brier分数
- 评估数据集选择: 测试集 / 训练集 / 两者对比

### 6. 可视化选项
- Nomogram列线图
- 变量重要性森林图
- ROC曲线对比（多模型叠加）
- 校准曲线
- DCA曲线
- Web计算器（基于Nomogram的在线预测）

### 7. 模型解释性
- **SHAP** (SHapley Additive exPlanations): 基于博弈论的模型解释，揭示每个特征对预测的贡献
- **PDP** (Partial Dependence Plot): 展示特征与预测结果的平均关系
- **ICE** (Individual Conditional Expectation): 展示每个样本的特征-预测关系

### 8. 模型验证
- **内部验证 (Bootstrap)**: 可设Bootstrap次数（默认200）
- **外部验证 (测试集)**: 上传独立数据集验证泛化能力
- 独立外部验证: 上传CSV文件，使用训练好的模型预测并评估

### 9. VIF共线性诊断
- VIF阈值设置（默认5）
- 相关系数阈值设置（默认0.7）
- 自动移除高共线性变量开关
- VIF分析表格（Variable, VIF, Status）
- 共线性诊断结果文本报告

## 各算法参数详情

| 算法 | 专属参数 |
|------|---------|
| Boruta特征筛选 | maxRuns, pValue, 随机种子 |
| 多个机器学习对比 | 选择多个模型, 交叉验证折数, 评估指标 |
| LASSO回归 | alpha范围, 交叉验证折数, 标准化开关, lambda选择(min/1se) |
| Lasso预测模型 | 训练集比例, alpha, 标准化开关 |
| 弹性网络 | alpha, l1_ratio, 交叉验证折数, 标准化开关 |
| Logistic回归 | 正则化, C, 求解器, 交叉验证 |
| 贝叶斯核机器回归 | 核函数类型, 迭代次数 |
| 决策树 | 最大深度, 最小分裂样本, 分裂标准 |
| 随机森林 | n_estimators, 最大深度, 最大特征 |
| XGBoost | n_estimators, max_depth, learning_rate, subsample |
| LightGBM | n_estimators, max_depth, learning_rate, num_leaves |
| 支持向量机 | 核函数, C, gamma |
| K-近邻算法 | K值, 距离度量, 权重 |
| LDA | 求解器, 收缩参数 |
| QDA | 正则化参数 |
| CatBoost | iterations, learning_rate, depth |
| 神经网络(MLP) | hidden_layers, activation, alpha, max_iter |
| 朴素贝叶斯 | 平滑参数 |
| Cox回归 | 正则化, alpha, 惩罚 |

## 数据接口规范

### 数据集加载
- `GET /api/datasets` - 列出可用数据集
- `GET /api/datasets/{id}/variables` - 获取变量元数据
- `POST /api/datasets/upload` - 上传数据集
- `POST /api/datasets/{id}/preview` - 预览数据

### 诊断API
- `POST /api/diagnostics/vif` - VIF共线性分析
- `POST /api/diagnostics/missing` - 缺失值诊断
- `POST /api/diagnostics/correlation` - 相关系数矩阵

### 机器学习API
- `POST /api/ml/boruta` - Boruta特征筛选
- `POST /api/ml/compare` - 多模型对比
- `POST /api/ml/lasso` - LASSO回归
- `POST /api/ml/lasso-predict` - Lasso预测模型
- `POST /api/ml/elastic-net` - 弹性网络
- `POST /api/ml/logistic` - Logistic回归
- `POST /api/ml/cox` - Cox回归
- `POST /api/ml/bkm` - BKM
- `POST /api/ml/decision-tree` - 决策树
- `POST /api/ml/random-forest` - 随机森林
- `POST /api/ml/xgboost` - XGBoost
- `POST /api/ml/lightgbm` - LightGBM
- `POST /api/ml/svm` - SVM
- `POST /api/ml/knn` - KNN
- `POST /api/ml/lda` - LDA
- `POST /api/ml/qda` - QDA
- `POST /api/ml/catboost` - CatBoost
- `POST /api/ml/mlp` - 神经网络
- `POST /api/ml/naive-bayes` - 朴素贝叶斯

### 解释性API
- `POST /api/explain/shap` - SHAP分析
- `POST /api/explain/pdp` - PDP分析
- `POST /api/explain/ice` - ICE分析

### 评估与验证API
- `POST /api/eval/calibration` - 校准曲线
- `POST /api/eval/dca` - DCA曲线
- `POST /api/eval/bootstrap` - Bootstrap验证
- `POST /api/eval/external` - 外部验证（上传数据集）

### 报告API
- `POST /api/report/generate` - 生成PDF报告

所有ML接口统一请求体:
```json
{
  "dataset_id": "string",
  "y_variable": "string",
  "is_survival": false,
  "time_variable": "string?",
  "x_variables": ["string"],
  "filters": [],
  "params": {},
  "seed": 123
}
```

统一响应:
```json
{
  "success": true,
  "charts": [{"type": "svg|html", "title": "", "data": ""}],
  "tables": [{"title": "", "headers": [], "rows": []}],
  "summary": "string",
  "download_urls": []
}
```

## 前端架构
- Layout: 左侧固定导航 (200px) + 顶部Tab栏 + 主内容区 + 右侧变量面板 (350px)
- 机器学习页面采用**步骤向导 (Steps)** 组件：
  - 左侧/顶部显示10步进度条
  - 每步对应不同配置面板
  - 支持上一步/下一步/直接跳转
- 状态管理: React Context 管理全局数据集和选中变量
- 路由: React Router
- 主题: 医学/学术风格，白底绿/蓝主色

## 部署架构
```
nginx (80/443)
├── /api → fastapi:8000
├── / → react static files
```

Docker Compose: backend (fastapi), frontend (nginx static)

## 开发顺序 (扩展版)
1. 后端扩展: 新增算法(XGBoost/LightGBM/MLP/NB/弹性网络/Cox/Logistic)
2. 后端新增: VIF诊断、SHAP/PDP/ICE、校准曲线/DCA、Bootstrap验证
3. 前端重构: 步骤向导组件
4. 前端新增: 诊断面板、解释性面板、评估面板、验证面板
5. 前端新增: 报告导出
6. Docker部署与测试
