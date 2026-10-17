# E7d · 交互图表迁移到 ECharts 设计方案

> 任务：task-E7 · Easy_R_v2 · 分支 `docs/E7-proposals` · 基线 `origin/main@9332500`
> 性质：📐 只出方案，不在本分支实施。
> 目标：交互图（ROC、校准、DCA、SHAP）后端改返回 JSON；与报告任务三 3.6 的图表规范对齐；彻底去掉 SVG 注入。

## 0. 关键结论（3 行以内）

1. 当前所有图都是 matplotlib 生成的 SVG/PNG 字符串，前端用 `dangerouslySetInnerHTML` 注入 SVG；`echarts`/`echarts-for-react` 已在 `package.json` 声明但源码零引用，图表不可交互、样式与报告 3.6 规范不一致，并存在 SVG 注入面。
2. 建议新增 `type="echarts"` 的图表契约：后端只返回数据与 option JSON，前端用 ECharts + `supabase-med` 主题渲染；Word/PDF 报告暂时保留 matplotlib 渲染（同一份数据规格双渲染），网页端彻底移除 `dangerouslySetInnerHTML`。
3. 分两期：一期 ROC/校准/DCA + 主题 + 去注入（约 10–12 人日）；二期 SHAP/PDP/森林图等（约 10–14 人日）。所有端点用 `chartFormat` 开关灰度，旧 SVG 路径可随时回退。

---

## 1. 现状（带文件:行号证据）

### 1.1 后端只产生位图/矢量字符串

- `backend/app/services/ml/utils.py:20-39`：
  - `fig_to_svg`（`:20-26`）把 matplotlib figure 存成 SVG 字符串；
  - `fig_to_png_base64`（`:28-34`）存成 base64 PNG；
  - `encode_figure`（`:36-39`）按 `fmt` 二选一。
- `backend/app/models/schemas.py:15-18`：`ChartData` 只有 `{type, title, data}`，`data` 是字符串，没有结构化 option/数据点。
- 各服务直接把图塞进 `ChartData`，例如：
  - `backend/app/services/ml/compare_service.py:119-134`（ROC）、`:136-167`（校准+DCA）、`:169-180`（AUC 条形图）；
  - `backend/app/services/ml/eval_service.py:40-58`（校准）、`:60-88`（DCA）；
  - `backend/app/services/ml/explain_service.py:59-76`（SHAP bar/beeswarm）、`:96-123`（PDP/ICE）；
  - `backend/app/services/ml/logistic_service.py:49-68`（系数/OR 图）。

### 1.2 前端用 HTML 注入渲染 SVG

- `frontend/src/components/ResultDisplay/ResultDisplay.tsx:28-40`：把 `result.charts` 映射为 Ant Design Tabs；
- `:33-37`：

```tsx
{chart.type === 'svg' ? (
  <div dangerouslySetInnerHTML={{ __html: chart.data }} ... />
) : (
  <img src={`data:image/png;base64,${chart.data}`} ... />
)}
```

- `dangerouslySetInnerHTML` 直接把后端字符串当 HTML 插入 DOM。即使 matplotlib 当前会转义文本，SVG 本身仍可包含脚本/事件属性；任何上游注入（变量名、标题、未来新增图表）都可能变成 XSS。彻底去掉它是 E7d 的硬性收益之一。
- 图表不可缩放、不可悬停、不可筛选；每个图一个 Tab，阅读体验与报告 3.6 的"每图一句解读"不一致。

### 1.3 ECharts 已声明但未使用

- `frontend/package.json:17-18`：`"echarts": "^5.5.0"`、`"echarts-for-react": "^3.0.2"`。
- `grep -rn "echarts" frontend/src` 无结果：依赖已安装但零引用，说明迁移不需要新增依赖（只需按需引入模块以控制体积）。

### 1.4 报告侧

- `backend/app/services/report_service.py:37-48`：Word 用 `cairosvg.svg2png` 把 SVG 转 PNG；
- `:51-62`：HTML 预览把 SVG 转 base64 后放进 `<img>`；
- `:195-283`：PDF 用 reportlab 嵌入 PNG。
- 报告侧目前依赖 matplotlib 的输出，迁移网页图表时不能直接删掉这条链路，否则 Word/PDF 会失去图。

### 1.5 与报告 3.6 规范的差距

报告 3.6（原文见 `tasks/task-C4-前端换肤.md:52-82`；样式另见 `tasks/task-E6-前端换肤.md:101-129`）要求：

- 主题 `supabase-med`：多系列颜色 `['#171717', '#3ecf8e', '#644fc1', '#054cff', '#e2005a', '#707070']`；
- 发散色 `DIV = ['#054cff', '#7da0fa', '#f5f5f5', '#eb7aa7', '#e2005a']`，显著性序列 `SEQ`；
- 无边框、无背景色、无 3D、无渐变；网格只画 y 方向，颜色 `#ededed`；
- 标题左对齐、字号 16/500；正文颜色 `#707070`；tooltip 深色 `#1c1c1c`；
- 每张图上方一句解读；导出 SVG 用 `renderer: 'svg'`、白色背景；数字等宽。

当前 matplotlib 图由各服务自己写死颜色（如 `compare_service.py:36-41` 的 `MODEL_COLORS`、`eval_service.py:44-53` 的蓝色/灰色），标题多为英文（`compare_service.py:130`、`:146`、`:163`），与上述规范不一致。

---

## 2. 目标做法

### 2.1 新图表契约（向后兼容）

扩展 `ChartData`（`schemas.py:15-18`）：

```python
class ChartData(BaseModel):
    type: str = "svg"                 # "svg" | "png" | "echarts"
    title: str
    data: str = ""                    # 旧字段：SVG/PNG 字符串
    option: Optional[Dict[str, Any]] = None   # 新：ECharts option
    meta: Dict[str, Any] = Field(default_factory=dict)  # 解读、单位、样本量、阈值
    fallback: Optional[Dict[str, Any]] = None  # 可选：{"type":"png","data":"..."}
```

前端类型同步（`frontend/src/types/index.ts:62-66`）：

```ts
export interface ChartData {
  type: 'svg' | 'png' | 'echarts' | string;
  title: string;
  data?: string;
  option?: Record<string, any>;
  meta?: Record<string, any>;
  fallback?: { type: string; data: string };
}
```

兼容策略：
- `type="echarts"` 时前端读 `option`；
- `type="svg"` 时不再注入 HTML，改为 `<img src={"data:image/svg+xml;base64," + btoa(...)}>`（`img` 上下文不执行脚本）；或后端直接返回 `fallback` PNG；
- 旧历史记录（数据库/JSON 快照）没有 `option`，按 SVG 兼容路径渲染。

### 2.2 后端：图数据与渲染分离

建议新增 `backend/app/services/core/chart_specs.py`（或按图族拆分），每个图返回**纯数据规格**：

```python
def roc_spec(y, p, model_name="Model") -> dict:
    fpr, tpr, _ = roc_curve(y, p)
    auc = roc_auc_score(y, p)
    return {
        "series": [{"name": model_name, "fpr": fpr.tolist(), "tpr": tpr.tolist(), "auc": auc}],
        "meta": {"auc": auc, "n": len(y)},
    }
```

然后：
- 网页端点：`spec → ECharts option`；
- 报告端点：`spec → matplotlib figure → PNG/SVG`（复用现有 `encode_figure`）。

这样同一份统计结果只算一次，避免"网页图和报告图数字不一致"。迁移顺序建议：

| 图 | 数据规格 | ECharts 形式 | 保留 matplotlib |
|---|---|---|---|
| ROC | `fpr/tpr/auc/CI` 多模型 | `line`，45° 参考线，tooltip 显示阈值 | 是（报告） |
| 校准 | `mean_pred/obs_rate/loess/ICI` | `line` + `scatter` + 45° 线 | 是 |
| DCA | `thresholds/nb_model/nb_all/band_low/high` | `line` + 置信带（`line` areaStyle 或两条边界线） | 是 |
| SHAP bar | `feature/mean_abs_shap` | 横向 `bar` | 是 |
| SHAP beeswarm | `shap_value/feature_index/feature_value` | `scatter` + `visualMap` | 是 |
| PDP/ICE | `grid/average/individual[]` | `line` + 多条浅色线 | 是 |
| 森林图 | `variable/estimate/lower/upper` | `scatter` + `markLine`（OR=1） | 是 |
| 混淆矩阵 | `tn/fp/fn/tp` | `heatmap` | 是 |

### 2.3 ECharts option 生成（后端）

建议在 `backend/app/services/core/echarts_options.py` 统一生成：

- 注册主题 `supabase-med`（值见 §2.4），所有 option 使用 `theme` 渲染；
- 通用配置：
  - `backgroundColor: "transparent"`（网页）/`"#fff"`（导出）；
  - `grid: {left: 8, right: 16, top: 40, bottom: 32, containLabel: true}`；
  - `xAxis/yAxis` 按 3.6 规范：仅 y 网格、`#ededed`、`#707070` 标签；
  - `tooltip` 深色、等宽数字；`legend` 小方块、无边框；
  - `animation: false` 或短动画（报告/打印稳定）；
  - `renderer` 由前端初始化时指定（导出用 SVG）。
- series 数据点直接来自 §2.2 的 spec；不要在 option 里放 SVG/HTML 字符串。
- 对多模型 ROC/校准/DCA，用 `series[]` 叠加，颜色按 `MODEL_COLORS` 映射到主题色板（保留模型可区分性，但仍受 `supabase-med` 约束）。

### 2.4 前端：ChartCard + ECharts

新增 `frontend/src/components/Charts/EChartCard.tsx`（或 `ChartCard.tsx`）：

```
<ChartCard
  title="ROC 曲线"
  interpretation="模型区分度良好（AUC 0.82，95% CI 0.76–0.88）。"
  option={...}
  meta={...}
  exportName="roc"
/>
```

功能：
- 使用 `echarts-for-react` + 按需引入（`echarts/core`、`LineChart`、`ScatterChart`、`BarChart`、`HeatmapChart`、`GridComponent`、`TooltipComponent`、`LegendComponent`、`VisualMapComponent`、`DataZoomComponent`、`SVGRenderer`/`CanvasRenderer`）；
- 注册 `supabase-med` 主题（`echarts.registerTheme`），主题文件放 `frontend/src/components/Charts/supabaseMed.ts`；
- 每张图上方显示一句 `interpretation`（来自后端 `meta.interpretation` 或前端按指标生成）；标题左对齐；
- 导出：ECharts `getDataURL({type:'svg', backgroundColor:'#fff'})` / `getDataURL({type:'png'})`；同时支持 CSV 导出底层数据（如果 `meta.data_table` 存在）；
- 响应式：`ResizeObserver` 或 `echarts-for-react` 的 `opts={{renderer:'svg'}}` + `notMerge`；容器高度固定/可配置；
- 错误边界：option 解析失败时显示 `fallback` PNG 或文本；
- 可访问性：图下方提供"查看数据表"折叠表（`meta.table`），供屏幕阅读器/打印；
- 主题与 E6 换肤共用 token，避免两套颜色。

`ResultDisplay.tsx` 改造：
- `chartItems` 不再用 Tabs，可改为纵向 ChartCard 列表（与 E6 报告 3.6 的"结果展示"一致；E6 已建议 `ResultDisplay` 从 Tab 改 ChartCard 列表，见 `tasks/task-E6-前端换肤.md:156-161`）；
- `type === 'echarts'` → `<EChartCard option={chart.option} ... />`；
- `type === 'svg'` → `<img src={dataUri} />`（**删除** `dangerouslySetInnerHTML`，`ResultDisplay.tsx:33-37`）；
- `type === 'png'` → 现有 `<img>`；
- 无 option 且无 data 时显示"图表数据不可用"。

### 2.5 报告侧策略

Word/PDF 仍需要静态图。两条路线：

- **推荐（低风险）**：报告继续用 matplotlib，但启用 `supabase-med.mplstyle`（E6 附录二，`tasks/task-E6-前端换肤.md:101-129`），并把图标题改成中文；网页 ECharts 与报告 matplotlib 共用 §2.2 的 spec，保证数据一致。
- **可选（高成本）**：服务端用 ECharts SSR（Node/puppeteer）渲染 PNG；当前服务器无 node（README §4 的部署约束），且会增加依赖与运维成本，不建议本期做。

报告 HTML 预览可以复用同一份 ECharts option，在 iframe 中加载 ECharts（离线打包），实现"预览可交互"；但这会把前端 bundle 带进报告预览，建议作为二期可选项。

### 2.6 彻底去掉 SVG 注入

1. `ResultDisplay.tsx` 删除 `dangerouslySetInnerHTML`（`:34`）。
2. 旧 SVG 用 `<img>` 的 data URI 渲染；`img` 中的 SVG 不执行脚本，且不继承页面样式。
3. 若必须内联 SVG，使用 DOMPurify（`dompurify` + `@types/dompurify`）白名单清洗；但推荐直接不用内联。
4. 后端不返回任何用户可控的 HTML；图表标题/变量名在 option 中作为纯文本/数据，由 ECharts 转义。
5. 增加一条前端 lint/测试：搜索 `dangerouslySetInnerHTML` 应无命中（除明确的静态内容）。
6. 若报告 HTML 预览仍内联 SVG，改为 `<img>`（`report_service.py:51-62` 已经是 `<img>` + base64，保持即可）。
7. 安全回归：构造含 `<script>`/`onload` 的变量名，确认页面不执行。

---

## 3. 对 API 的影响

### 3.1 请求

- `MLRequest.params.chartFormat`: `"echarts" | "svg" | "png"`，默认在灰度期用 `"svg"`，全量后改 `"echarts"`；与现有 `format` 参数（各路由 `request.params.get("format","svg")`，`routers/ml.py:47-194`）兼容。
- 可选 `chartOptions`: `{maxPoints, theme, includeTable}`；SHAP 下采样上限等。

### 3.2 响应

`MLResult.charts[]` 扩展 `option/meta/fallback`（§2.1）。示例：

```json
{
  "type": "echarts",
  "title": "ROC 曲线（OOF）",
  "option": {
    "xAxis": {"type": "value", "min": 0, "max": 1, "name": "1 - 特异度"},
    "yAxis": {"type": "value", "min": 0, "max": 1, "name": "灵敏度"},
    "series": [{"type": "line", "name": "LR", "data": [[0, 0], [0.1, 0.4], [1, 1]]}]
  },
  "meta": {
    "interpretation": "AUC 0.82（95% CI 0.76–0.88），区分度良好。",
    "auc": 0.82,
    "n": 300,
    "table": {"headers": ["模型", "AUC"], "rows": [["LR", 0.82]]}
  },
  "fallback": {"type": "png", "data": "<base64>"}
}
```

### 3.3 端点

- `/api/ml/compare`、`/api/ml/calibration`、`/api/ml/dca`、`/api/ml/shap`、`/api/ml/pdp`、`/api/ml/logistic`、`/api/ml/random-forest`、`/api/ml/knn` 等所有返回 `charts` 的端点。
- 建议先改 `compare/calibration/dca/shap` 四个（任务点名），其余按 §2.2 表逐步。
- 历史记录：`history_service` 保存的 `MLResult` 新增字段可选；旧记录按 SVG 渲染。

---

## 4. 对向导 UI 的影响

### 4.1 结果展示

- 第 4/5/6/7/8/9 步的所有 `ResultDisplay` 自动受益；从 Tabs 改为 ChartCard 列表（与 E6 设计一致）。
- 每张图上方一句解读；指标用 `Statistic` 等宽数字（E6 规范）；EPV/校准/外部验证提示用 warn pill。
- 图表容器高度：折线/散点 360–420px，SHAP beeswarm 480px；移动端横向滚动或高度自适应。

### 4.2 交互

- ROC：悬停显示阈值、sens/spec；图例可点击隐藏模型。
- 校准：悬停显示 bin 均值/观测率/n；可切换 loess/identity。
- DCA：悬停显示阈值、净获益、treat-all；置信带可开关。
- SHAP：bar 与 beeswarm 切换；beeswarm 悬停显示特征值/贡献；下采样提示。
- 所有图支持"导出 SVG/PNG"和"查看数据表"。

### 4.3 报告

- 第 10 步预览：短期仍用后端 HTML（matplotlib SVG→img）；二期可嵌入 ECharts。
- 报告正文：图标题中文、每图一句解读（E7c 报告规范）；图表编号与正文引用一致。

---

## 5. 实现工作量估算

| 工作项 | 人日 | 说明 |
|---|---:|---|
| 图表契约 + 类型 + 兼容层 | 1–2 | Pydantic/TS、旧 SVG `<img>` |
| `chart_specs` 与 ECharts option（ROC/校准/DCA） | 4–5 | 含多模型、CI、置信带 |
| SHAP bar/beeswarm + 下采样 | 3–4 | 数据量、visualMap、性能 |
| PDP/ICE、森林图、混淆矩阵 | 2–3 | 可选/二期 |
| 前端 `EChartCard` + 主题 + 响应式 | 4–5 | 按需引入、ResizeObserver、错误边界 |
| 导出 SVG/PNG/CSV + 数据表 | 2 | 打印/报告一致性 |
| 删除 SVG 注入 + 安全回归 | 1 | lint + XSS 测试 |
| 报告 matplotlib 主题对齐（supabase-med.mplstyle） | 2 | 与 E6 共用 |
| 回归/快照/跨浏览器测试 | 3–4 | 固定数据夹具 |
| **合计** | **22–28 人日** | 一期（ROC/校准/DCA + 主题 + 去注入）约 10–12 人日 |

---

## 6. 风险与回退方案

| 风险 | 影响 | 缓解/回退 |
|---|---|---|
| 双渲染（ECharts + matplotlib）口径漂移 | 网页与报告数字/形状不一致 | 共用 `chart_specs`；对同一 spec 做像素/数值回归；报告图注注明数据来源 |
| SHAP 点数过大 | 浏览器卡顿/响应体过大 | 下采样（默认 ≤1000 点）+ "已采样"提示；服务端聚合 |
| ECharts bundle 增大 | 首屏变慢 | 按需引入图表/组件；路由级懒加载；gzip 预算 |
| 主题与 E6 冲突 | 两套颜色 | 主题 token 单一来源；E6 完成后复用其 token |
| 导出 SVG 字体缺失 | 中文变方块 | 导出时使用系统字体栈/内嵌字体；提供 PNG 兜底 |
| 旧历史记录无 option | 图表空白 | `type="svg"` 兼容 `<img>`；`fallback` PNG |
| 打印/PDF 分页 | 图被截断 | 固定尺寸、`break-inside: avoid`；报告仍用静态图 |
| ECharts 在 iframe/预览中尺寸为 0 | 图不显示 | `ResizeObserver` + 显式高度；预览使用静态图兜底 |
| 移除 `dangerouslySetInnerHTML` 后旧 SVG 样式变化 | 字体/尺寸差异 | `<img>` 保持原始 viewBox；必要时后端转 PNG |

**总回退**：`chartFormat="svg"` 一键回到旧路径；新字段全部可选；前端按 `type` 分支渲染，不需要回滚数据库。

---

## 7. 🧑‍⚖️ 待用户拍板的决策点

1. **迁移范围与顺序**：是否按"ROC → 校准 → DCA → SHAP → 其他"推进？一期只做前三个是否可接受？
2. **报告渲染**：Word/PDF 继续用 matplotlib（推荐、低成本），还是投入服务端 ECharts SSR（需 Node/puppeteer，当前服务器无 node）？
3. **SHAP 下采样**：beeswarm 最大点数（500/1000/2000）与是否允许用户调整？
4. **旧 SVG 处理**：用 `<img>` 兼容（推荐）还是引入 DOMPurify 内联？是否要求历史记录也能交互？
5. **导出格式**：必须支持 SVG/PNG/CSV 三种，还是先做 SVG/PNG？
6. **主题归属**：`supabase-med` 由 E6 统一维护还是 E7d 自带一份？两处必须同源。
7. **交互深度**：是否需要图例筛选、阈值联动、DCA 置信带开关，还是先静态交互（tooltip/缩放）？
8. **包体预算**：ECharts 按需引入后的 gzip 预算（如 ≤150KB）是否接受？是否需要路由懒加载？

---

## 8. 发现但未在本方案展开的相关问题

- `frontend/src/components/ResultDisplay/ResultDisplay.tsx:28-40` 目前一图一个 Tab，图表标题来自后端英文标题；迁移时应统一中文标题与解读句（E6 已提出 ChartCard 列表）。
- `backend/app/services/ml/compare_service.py:36-41` 的 `MODEL_COLORS` 与 3.6 主题色板不完全一致；迁移时需建立"模型 → 主题色"的稳定映射，避免同一模型在不同图里颜色不同。
- `backend/app/services/ml/eval_service.py` 与 `backend/app/services/core/metrics.py` 存在重复的 DCA 计算（`eval_service.py:60-88` vs `metrics.py:61-73`）；E7d 迁移前应先统一数据源，否则网页/报告会出现两套净获益。
- `backend/app/services/report_service.py:37-48` 依赖 `cairosvg`；若未来改为 ECharts SSR，需要重新评估该依赖与字体。
- `frontend/package.json:17-18` 虽已声明 ECharts，但没有版本锁定策略/按需引入配置；迁移时需确认与 React 18、Ant Design 5 的兼容性。
