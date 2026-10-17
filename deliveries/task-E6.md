# task-E6 前端换肤 Phase 0

任务ID / 分支 / 基线提交：**E6 / `fix/E6-reskin` / `c6792f6`（E4 合并后的 origin/main）**。
开工后 `origin/main` 前进到 `b8d9c80`（E5 合并），推送前已 rebase 到最新 `origin/main`；本分支未推 main、未自行合并。

本任务只改外观/主题与图表样式，未改业务逻辑、未改 API 字段、未删除数据。

## 改动文件

### 前端主题与全局样式

- `frontend/src/theme/antdTheme.ts:1-110`（新增）：完整 AntD 5 `ThemeConfig`。`colorPrimary:'#3ecf8e'`；链接/复选框/单选/开关/滑块/步骤条/Tab 指示线改回近黑 `#171717`；文字 `#171717 / #707070 / #9a9a9a`；边框 `#dfdfdf / #ededed`；布局白底、`colorFillAlter:'#fafafa'`；圆角 6/4/12/4；控件高 36/28/44；字体 Inter/PingFang SC/Microsoft YaHei；`components` 覆盖 Button/Checkbox/Radio/Switch/Slider/Steps/Tabs/Menu/Layout/Table/Card/Input/Select/Tag/Tooltip/Progress/Alert/Modal，其中 Button `primaryColor:#171717`、`fontWeight:500`，Card `borderRadiusLG:12`。
- `frontend/src/theme/tokens.css:1-138`（新增）：CSS 变量 `--c-ink/#171717`、`--c-mute/#707070`、`--c-mute-2/#9a9a9a`、`--c-line/#dfdfdf`、`--c-line-cool/#ededed`、`--c-canvas/#ffffff`、`--c-canvas-soft/#fafafa`、`--c-green-500/#3ecf8e`、`--c-green-600/#24b47e`、`--c-magenta/#e2005a`、`--c-indigo/#054cff`、`--c-success-soft/#f0faf6`、`--c-warn/#a16207`、阴影；全局兜底 `.ant-btn-primary{color:#171717!important}`、链接下划线、卡片圆角/边框、pill 标签、`.pill-soft`/`.pill-warn`、横向步骤条当前步 2px 绿色下划线、`.mono-num` 等宽数字。
- `frontend/src/main.tsx:5-17`：引入 `@fontsource-variable/inter`（离线字体，不依赖 Google Fonts）与 `theme/tokens.css`，`<ConfigProvider locale={zhCN} theme={antdTheme}>`。
- `frontend/package.json:13`、`frontend/package-lock.json`：新增依赖 `@fontsource-variable/inter ^5.3.0`。

### 侧栏与写死颜色替换

- `frontend/src/components/Layout/Sidebar.tsx:148-183`：`Sider theme="light"`、背景 `var(--c-canvas-soft)`、右边框 `var(--c-line-cool)`；Logo 由绿色方块 "R" 改为文字标 `Easy R` + 8px 绿色圆点；`Menu theme="light"`；Logo 字重 500（验收“字重不超过 500”）。
- `frontend/src/App.tsx`：`#999/#666` → `var(--c-mute)`，`#fff` → `var(--c-canvas)`，`#f0f0f0` → `var(--c-line-cool)`。
- `frontend/src/components/AlgorithmForm/AlgorithmForm.tsx`：虚线框 `var(--c-line)`、底色 `var(--c-canvas-soft)`、placeholder `var(--c-mute)`。
- `frontend/src/components/VariablePanel/VariablePanel.tsx`：边框 `var(--c-line-cool)`、选中底色 `var(--c-success-soft)`。
- `frontend/src/pages/AuthPage/AuthPage.tsx`：页面底色改纯白 `var(--c-canvas)`。
- `frontend/src/components/Wizard/steps/Step10Report.tsx`：iframe 边框 `var(--c-line-cool)`。
- `frontend/src/components/Wizard/steps/Step1DataPrep.tsx`、`Step3VarFilter.tsx`、`Step4ModelBuild.tsx`、`Step6Visual.tsx`：`#666/#999` 等写死文字色改 CSS 变量；Step3 成功提示、Step6 预测概率块改 AntD `Alert type="success"`（白底浅绿），数字使用 `.mono-num`。

### 向导外壳（最小必做项第 5 项，已完成部分）

- `frontend/src/components/Wizard/StepNavigator.tsx:19-56`（重写）：10 步竖向 Steps 改为横向步骤条，`labelPlacement="vertical"`；近黑数字圆圈；当前步下方 2px 绿色指示条（CSS）；四种展示状态：完成（✓ `finish`）、过期（`error` + `pill-warn`「需重跑」）、当前（`process`）、未开始（`wait` 灰）。点击仅允许跳到已完成或当前步（沿用 E4 行为，未改业务逻辑）。
- `frontend/src/components/Wizard/WizardContainer.tsx:1-195`（重写外壳）：顶部白色卡片 = 横向步骤条 + 分隔线 + 常驻配置摘要 pill（数据集 / 结局 / 分组 / 特征数 / 模型），pill 可点击跳到对应步骤；内容区独立滚动；底部固定操作栏：白底、上边 1px `#ededed`、L1 阴影、高 64，左侧白底「上一步」、中间 12px `#707070`「已完成 N/10 步」、右侧唯一绿色主按钮「运行并继续」。特征数用 `effectiveModelFeatures(state)` 计算，未改状态逻辑。
- 为容纳 10 步，`tokens.css` 中步骤项 `flex:1 1 0; min-width:0`、标题 12px 省略号，实测 10 项各 109px，全部可见（1440 宽、200px 侧栏 + 350px 变量面板）。

### 后端 matplotlib 样式

- `backend/app/assets/supabase-med.mplstyle:1-31`（新增）：按附录实现，另加文件头说明两处必要偏差：`.mplstyle` 中 `#` 为行内注释，故标量颜色用灰度浮点（`edge 0.8745`、`label 0.4392`、`grid 0.9294`），`prop_cycle` 的十六进制省略 `#`（matplotlib 自带样式同一写法）。Inter 字体族、字号 9/11、标题 fontweight medium + 左对齐、y 向网格、去上/右脊线、图例无框、figure.dpi 150 / savefig.dpi 300、tight bbox、SVG 文本可编辑、负号正常显示。
- `backend/app/services/ml/utils.py:20-65`：新增 `COLOR_INK/#171717`、`COLOR_MUTED/#707070`、`COLOR_GREEN/#3ecf8e`、`COLOR_PURPLE/#644fc1`、`COLOR_UP/#e2005a`、`COLOR_DOWN/#054cff`、`COLOR_WARN/#a16207`、`DATA_COLORS`；`PLOT_STYLE_PATH`；`apply_plot_style()` 先用 `rc_params_from_file(..., fail_on_error=True)` 严格校验，再 `plt.style.use`，任何异常都 `warning` + 回退 `plt.style.use('default')` 并返回 `False`，模块导入时调用；删除 `sns.set_style("whitegrid")`（样式统一由 mplstyle 提供）；CJK 字体回退链保留。
- `backend/app/services/ml/compare_service.py`：删除 `MODEL_COLORS`，模型曲线改用 `DATA_COLORS` 轮转；基准线/误差条改主题色；中文化 ROC/校准/决策曲线/区分度比较标题。
- `backend/app/routers/diagnostics.py`、`backend/app/routers/eval.py`：上调/下调固定品红 `COLOR_UP` / 靛蓝 `COLOR_DOWN`；外部验证等标题中文化。
- `backend/app/services/ml/adv_diag_service.py`、`bkm_service.py`、`boruta_service.py`、`catboost_service.py`、`cox_service.py`、`diagnostics_service.py`、`elastic_net_service.py`、`eval_service.py`、`explain_service.py`、`knn_service.py`、`lasso_service.py`、`lda_qda_service.py`、`lightgbm_service.py`、`logistic_service.py`、`mlp_service.py`、`naive_bayes_service.py`、`nomogram_service.py`、`rf_service.py`、`svm_service.py`、`tabpfn_service.py`、`tree_service.py`、`validation_service.py`、`xgboost_service.py`：删除写死红绿配色，改用主题常量（正/负系数与上调/下调用品红/靛蓝，分类柱用紫色，参考线用灰）；图标题中文化。LDA/QDA 热图由绿-红 `RdYlGn` 改发散 `coolwarm`，避免绿色承载数据含义。
- `backend/app/services/report_service.py`：HTML/DOCX 标题、表头、边框、斑马纹改 `#171717 / #dfdfdf / #fafafa / #707070`，去掉旧绿色品牌色。
- `backend/tests/test_plot_style.py:1-61`（新增，4 个用例）：导入后样式生效（DPI 150/300、y 向网格、去上/右脊线、负号）；样式文件缺失 → 返回 False + warning 含“回退默认样式” + 默认 DPI 100；样式文件含非法颜色 → 同样降级不崩溃；中文标题图可渲染出 SVG。

## 测试与核对

### `npm run build`

```
vite v5.x building for production...
✓ 3110 modules transformed.
dist/assets/inter-*.woff2 ...（Inter 字体分片本地打包）
dist/assets/index-*.css    4.04 kB │ gzip:   1.41 kB
dist/assets/index-*.js 1,278.21 kB │ gzip: 403.28 kB
(!) Some chunks are larger than 500 kB after minification.（既有体积告警，非本次引入）
✓ built in 6.07s
```

退出码 0（最终代码含字重修正后复跑通过；rebase 到 E5 合并后的 `origin/main` 后再次 `npm install`（补 `dompurify`/`jsdom`）并复跑，`✓ built in 6.92s`，退出码 0）。

### 后端 `pytest`

rebase 前（基线 E4）：

```
38 passed, 7194 warnings in 15.83s
```

rebase 到 E5 合并后的 `origin/main`（`b8d9c80`）后复跑：

```
43 passed, 7431 warnings in 23.20s
```

退出码 0（新增 5 个用例来自 E5）。环境说明：本机基础 conda 环境为 pydantic 1.10.12，而项目 requirements 固定 pydantic==2.7.0，直接跑会报 `'MLRequest' object has no attribute 'model_dump'`。**未改动共享环境**，而是用 `pip --target D:\agent-workspace\deliveries\task-E6\testdeps` 安装 `pydantic==2.7.0` 与 `catboost==1.2.5 --no-deps`，以 `PYTHONPATH` 指向该目录运行；测试依赖目录在交付目录，未提交。服务器未重启、未改动。

### 验收 grep

```
$ grep -rn --include=*.py --include=*.ts --include=*.tsx --include=*.css \
    -E "#2ecc71|#e74c3c|#2f855a" backend/app frontend/src
NO_MATCH
```

### 手工截图（`D:\agent-workspace\deliveries\task-E6\`，未入 git）

- `e6-01-login.png`：登录页纯白背景、12px 圆角表单卡片、绿色「登录」按钮 + 近黑字、Tab 指示线近黑。
- `e6-02-shell.png`：应用外壳；浅灰 `#fafafa` 侧栏（像素采样 250,250,250）、`Easy R` + 绿点文字标、白色顶栏、pill 标签、变量面板浅色选中。
- `e6-03-wizard.png`：向导页；10 步横向步骤条全部可见（各 109px）、当前步近黑圆圈 + 绿色 2px 下划线、5 个配置摘要 pill、白色内容卡片、底部固定操作栏（上一步 / 已完成 0/10 步 / 绿色主按钮）。
- 本地联调：后端 `127.0.0.1:8000`、Vite 5175；演示账号 `e6demo`。

## 3.7 验收清单逐条结果

- [x] **页面背景纯白、无渐变**：登录页、外壳内容区、向导内容区均纯白；侧栏按设计为 `#fafafa`（非渐变）。已截图核对。
- [x] **每个视图最多 1 个绿色实心按钮，绿底近黑字**：登录页仅「登录」；向导页仅「运行并继续」（禁用态显示为灰绿，启用后为 `#3ecf8e`）。主题 + `.ant-btn-primary{color:#171717!important}` 双重保证近黑字。其余按钮为白底描边。
- [ ] **承载信息文字不浅于 #707070，对比度 ≥4.5**：主题把 `colorTextSecondary/Tertiary` 固定为 `#707070`（`#9a9a9a` 仅用于非信息性的 quaternary/占位层级）；**尚未用 axe DevTools / Lighthouse 全站跑对比度**，需人工复核（🧑‍⚖️）。
- [x] **按钮圆角 6、卡片圆角 12、无胶囊形按钮**：主题 `borderRadius:6`、`Card.borderRadiusLG:12`；未发现胶囊按钮。Tag/pill 为标签形态（设计明确使用 pill-soft/pill-warn），不是按钮。
- [x] **字重不超过 500**：主题 `fontWeightStrong:500`、Button 500；已 `grep` 并修正侧栏 Logo 的 600 → 500，当前 `frontend/src` 无 600+ 字重。
- [x] **绿色不表达数据含义；上调/下调固定品红/靛蓝**：品牌绿仅用于主按钮、当前步指示、进度条和 logo 圆点；后端上调 `#e2005a`、下调 `#054cff`（系数正负、指标升降一致），分类系列用近黑/紫/靛蓝/品红/棕/灰；旧 `#2ecc71/#e74c3c/#2f855a` 已无命中。
- [ ] **每张图一句解读 + 可导出 SVG 和 CSV**：未在本任务实现。结果区仍是旧的“一图一卡/Tab”结构，图后解读、批量 SVG/CSV 导出属于结果展示改版（E6b，见下）。
- [ ] **所有数字等宽**：部分完成。已提供 `.mono-num`（tabular-nums）并用于向导底部计数、Step6 预测概率；表格、Statistic、结果指标尚未全局启用，留 E6b。
- [x] **内网断网字体与图表正常加载**：Inter 通过 `@fontsource-variable/inter` 打进 dist（woff2 本地分片），无 Google Fonts/外链；图表由后端 matplotlib 生成 PNG/SVG，不经 CDN。构建产物可证。

## E6b 拆分说明（未做，建议单独排期）

本任务已完成最小必做项 1–4 与第 5 项中的“横向步骤条 + 四态展示 + 配置摘要 pill + 底部固定操作栏”。以下按任务允许留作 **E6b**：

1. 每一步参数区改两列表单（左标签说明、右控件，统一 36px，不用 `size="small"`）。
2. 右侧 350px VariablePanel 改 Drawer（宽 400、L3 阴影，向导页默认收起，由 AppNav「变量」按钮打开）；顶部 48px AppNav + 面包屑。
3. 结果展示：ChartCard 纵向列表、每图一句白话结论、`<Statistic>` 28px 等宽指标、EPV/单中心/未外部验证的 warn pill、深色 CodeBlock 方法学说明。
4. 登录页左右分栏（左侧产品名 display-lg + 说明 + 叠放示例卡片，右侧 400px 表单卡）。
5. 交互图 ECharts 化（ROC/校准/DCA/SHAP 蜂群，属 E7d 方案）。
6. 全站数字等宽与每图 SVG/CSV 导出。

## 待人工确认（🧑‍⚖️）

- `#9a9a9a` 作为 quaternary/占位/禁用文字是否可接受：验收要求“承载信息的文字不浅于 #707070”，本实现仅将 `#9a9a9a` 用于非信息层级；请确认边界。
- 步骤条“错误（品红圆点）”与“过期（需重跑）”目前合并为 `stale` 一种数据状态（E4 状态机无独立 error 字段）。新增 error 字段属于业务逻辑/状态机改动，本任务未动；如需视觉上区分，建议在 E6b 或后续任务补状态字段。
- pill 形标签是否算“胶囊形按钮”：本实现按设计保留 pill 标签（pill-soft/pill-warn），按钮均为 6px 圆角。
- 绿色 `#3ecf8e` 保留在 matplotlib 分类色环（附录指定 `prop_cycle`）中，仅作品牌/系列色之一，不用于涨跌或好坏含义；请确认可接受。
- 对比度需在真实页面用 axe/Lighthouse 复核（本任务只做代码与截图核对，未跑自动化无障碍工具）。

## 发现但未处理

- 结果区“每图一句解读 + SVG/CSV 导出”、全站等宽数字、两列表单、Drawer、AppNav、ChartCard 列表、登录分栏、ECharts：均未做，见 E6b。
- 基础 conda 环境 pydantic 版本与 requirements 不一致（1.10.12 vs 2.7.0），本次用隔离 `--target` 依赖绕开；未改共享环境，建议后续统一环境。
- 前端 bundle 主 chunk 1.28 MB（gzip 403 kB）触发 Vite >500 kB 告警，为既有问题，未在换肤任务中处理。
- 未逐页手工走完所有 10 个向导步骤的图片渲染与导出（仅以构建、后端 pytest、样式单测与 3 张关键页截图验证）。
