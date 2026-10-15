# Easy_R v2 统计内核改造说明

> 2026-10-12。内核与"临床模型工作流模板"（桌面\临床模型工作流模板）同源。

## 新增：统计内核包 `backend/app/services/core/`

| 文件 | 作用 |
|---|---|
| `preprocessing.py` | `ClinicalPreprocessor`：中位数填补/哑变量水平全部只在训练折学习（修复旧版全数据 fillna(mean) 的泄漏）；`encode_y` |
| `models.py` | 统一模型注册表，长短 key 别名归一（修复 REPAIR_LOG #3），`create_model(key, params, seed)` |
| `metrics.py` | OOF 全套指标：AUC/PR-AUC/Brier/H-L/校准斜率截距/Youden/DCA 净获益；重复间 mean±SD/95%CI；固定预测的 bootstrap AUC CI |
| `validation.py` | `run_repeated_cv`：重复 Stratified(Group)KFold + OOF；`optimism_bootstrap`：重抽样后**重新训练**的乐观度校正 Bootstrap |

## 重写的服务

- **`ml/compare_service.py`**：单次 train_test_split → 重复分组 CV + OOF 汇总。
  新参数：`params.group_variable`（患者分组列）、`params.repeats`（默认5）、`params.cvFolds`。
  表格新增：重复间 95%CI、Bootstrap 95%CI、训练-外检乐观度；图全部基于平均 OOF。
- **`ml/validation_service.py`**（Bootstrap）：旧版只重抽测试集预测值（假验证）→
  现在按患者/样本重抽样并每次重新训练，输出表观 AUC、平均乐观度、校正 AUC、OOB AUC(95%CI)。
- **`routers/eval.py` 外部验证**：预处理 Pipeline 在训练集 fit、外部数据仅 transform；
  新增外部校准曲线 + DCA + AUC bootstrap CI；模型走注册表（修复 #5）。
- **`transform_service.py`**：新增 `method="clr"`（闭合+CLR，半最小正值乘性替换零值），
  与 ALR 共用 CV/p 值筛选流程。CLR 坐标共线，建模建议剔除一列或用正则化/树模型。
- **`data_service.get_data_for_ml`**：新增 `extra_cols` 参数（保留分组列）。
- **`ml/utils.py`**：中文字体 fallback 加 Noto CJK（服务器无 SimHei）。

## 前端对接 TODO

1. 向导第 1 步（数据准备）：加"分组变量（患者 ID，可选）"下拉 → 传 `params.group_variable`；
   第 4 步模型对比：加"重复次数"输入 → `params.repeats`。
2. 数据转换页：方法选项加 CLR（无需基准峰，前端隐藏基准峰选择）。
3. 报告导出：接模板式 Word 报告（后端 report_service 待升级，预览用现有 charts）。

## 启动

```bash
cd ~/Easy_R_v2/backend
~/miniconda3/envs/easyr/bin/uvicorn app.main:app --host 0.0.0.0 --port 8011
```

（端口 8011 为测试用；正式部署改 docker-compose / nginx 指向。）

## 已验证

- demo.csv 全流程：compare（普通+分组两种模式）、bootstrap、CLR 变换、REST 端到端（注册/登录/compare 200）。
- 已知限制：单模型 service（lasso_service 等 20 个）仍用旧 prepare_xy（全数据填补），
  建议逐步迁到 core.ClinicalPreprocessor；compare/bootstrap/external 三个主入口已是新内核。

## 第二轮改造（2026-10-12 晚，三项任务全部完成）

### 任务3：单模型服务全量迁移防泄漏内核
- 22 个服务文件、24 个入口函数全部弃用旧 `prepare_xy`（全数据 fillna/get_dummies 泄漏）。
- 有 train/test 划分的走新辅助函数 `core.validation.train_test_pipeline`（Pipeline 预处理只在训练折 fit）；
  筛选/诊断类（无留出验证）用 `ClinicalPreprocessor` 全数据 fit，编码一致。
- 顺带修复：knn/svm/mlp 划分前标准化泄漏、logistic 的 cross_val_score 二次泄漏、
  SHAP 新版三维返回值、cox 时间/事件列与特征重叠时的报错、中文字体 fallback（Noto Sans CJK JP）。
- 冒烟测试：demo.csv 上 24 个函数全部通过；REST 端到端（注册→上传→compare→bootstrap→报告）通过。

### 任务1：前端
- 向导第 1 步：分组变量（患者ID，可选）下拉；峰值转换加 CLR 选项（选 CLR 时隐藏基准峰选择器）。
- 第 4 步多模型对比：加"重复次数"输入，传 `cvFolds`/`repeats`/`group_variable`；修最佳模型正则适配新 summary。
- 第 9 步 Bootstrap 传 `group_variable`；第 10 步报告带分组变量。
- tsc 类型检查 + vite build 通过，dist 已部署到 ~/Easy_R_v2/frontend/dist。

### 任务2：模板式报告
- report_service 重写：封面元信息（含分组变量）→ 方法与评价协议（固定方法学段落）→
  编号章节（01、02…）→ 结论与局限性，对齐模板 make_report 结构。
- cairosvg 已装，SVG 图表转 PNG 嵌入 Word；`/api/report/generate` 新增 `preview_html` 返回，
  前端第 10 步 iframe 内联预览 + 下载按钮（预览/下载均满足）。

## 第三轮：正式部署与浏览器实测（2026-10-13）

### 部署
- 后端 8006（uvicorn，conda 环境 easyr），前端 8091（npx serve dist --cors）；
  `~/Easy_R_v2/start.sh / stop.sh / status.sh` 仿照 ~/Easy_R，全启停循环验证通过。
- 前端 `.env.production` 指向 8006（曾误指 8005 旧后端，重建 dist 修正）。
- 8006 上 10/10 接口测试通过（含 CLR、分组 compare、SHAP、报告下载）。

### 浏览器全程向导实测（CDP Chrome）
- 注册→上传 demo.csv→第1步选 Y=结局Y1、分组=id→VIF→单因素筛选→
  第4步 LR+RF 对比（"按 id 分组，5次×5折"，LR AUC=0.658±0.012）→
  评估/可视化/SHAP/高级诊断→第9步 Bootstrap（200次按患者分组重抽样，
  表观0.6951/校正0.6761/OOB 0.6502）→第10步报告预览 iframe 正常。

### 实测发现并修复
- **报告下载 401**：第10步"下载报告"用裸 `<a href target=_blank>`，不带
  Authorization 头。改为 axios blob 下载（`downloadReportFile`）+ objectURL，
  验证 200/922KB docx。dist 已重建重部署。
- 已知 UX 问题（v1 遗留，未改）：切走"机器学习向导"标签页会向导致状态重置；
  变量筛选可能把分组变量(id)选入特征（随机森林重要性法），需手动注意。
