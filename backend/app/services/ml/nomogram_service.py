import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.special import logit

from app.services.ml.utils import encode_figure, ChartData, TableData, COLOR_INK, COLOR_UP, COLOR_DOWN
from app.services.ml.predict_service import nomogram_context

# 支持列线图/计算器的线性二分类模型
LINEAR_MODELS = ("logistic", "lasso", "lasso-predict", "elastic-net")


def _point_value(value, vmin, vmax, coef, points_denom):
    """单变量 points：β≥0 时随 x 增大，β<0 时轴反向。"""
    span = vmax - vmin
    if span == 0 or points_denom == 0:
        return 0.0
    if coef >= 0:
        return 100.0 * abs(coef) * (value - vmin) / points_denom
    return 100.0 * abs(coef) * (vmax - value) / points_denom


def _nomogram_geometry(variables, ranges, coefs, intercept):
    """计算 points 标尺与 Total Points ↔ 线性预测值的线性映射。

    points_j(x) = 100·|β_j|·(x−x_min)/D（β<0 时轴反向），
    D = max_k(|β_k|·range_k)；
    lp = b0_raw + Σ β_j·(β_j≥0 ? x_min_j : x_max_j) + (D/100)·TotalPoints。
    """
    denom = max((abs(coefs[v]) * (ranges[v][1] - ranges[v][0]) for v in variables), default=0.0)
    total_max = sum(100.0 * abs(coefs[v]) * (ranges[v][1] - ranges[v][0]) / denom
                    for v in variables) if denom > 0 else 0.0
    offset = intercept + sum(
        coefs[v] * (ranges[v][0] if coefs[v] >= 0 else ranges[v][1]) for v in variables
    )
    return denom, total_max, offset


def draw_nomogram(variables, ranges, coefs, intercept=0.0, model_type='logistic', fmt='svg'):
    """按标准列线图画法绘制；概率轴由 sigmoid(lp) 反解，不再使用线性近似。"""
    n_vars = len(variables)
    fig_height = max(6, n_vars * 1.2 + 2.5)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    ax.set_xlim(0, 100)
    ax.set_ylim(-2.2, n_vars + 2)
    ax.axis('off')

    denom, total_max, offset = _nomogram_geometry(variables, ranges, coefs, intercept)

    ax.text(50, n_vars + 1.5, 'Nomogram 列线图', fontsize=14, fontweight='bold',
            ha='center', va='center')

    y_positions = np.linspace(n_vars - 0.5, 0.5, n_vars)
    points_list = []

    for i, var in enumerate(variables):
        y = y_positions[i]
        vmin, vmax = ranges[var]
        c = coefs[var]
        span = vmax - vmin

        ax.plot([10, 90], [y, y], color='#333', linewidth=2)
        # 端点：β<0 时轴反向（左端为 max）
        left_val = vmin if c >= 0 else vmax
        right_val = vmax if c >= 0 else vmin
        ax.text(5, y, f'{left_val:.3f}', fontsize=8, ha='right', va='center')
        ax.text(95, y, f'{right_val:.3f}', fontsize=8, ha='left', va='center')
        color = COLOR_UP if c >= 0 else COLOR_DOWN
        ax.text(50, y + 0.3, f'{var} (β_raw={c:.3f})', fontsize=10, fontweight='bold',
                ha='center', va='bottom', color=color)

        # Tick marks every 25%，方向随 β 符号
        for pct in [0, 0.25, 0.5, 0.75, 1.0]:
            x_pos = 10 + pct * 80
            val = vmin + pct * span if c >= 0 else vmax - pct * span
            ax.plot([x_pos, x_pos], [y - 0.08, y + 0.08], color='#666', linewidth=1)
            ax.text(x_pos, y - 0.25, f'{val:.3f}', fontsize=7, ha='center', va='top', color='#666')

        points_list.append({'variable': var, 'min': vmin, 'max': vmax, 'coef': c, 'y': y})

    # Total Points axis
    total_y = -0.6
    ax.plot([10, 90], [total_y, total_y], color=COLOR_INK, linewidth=3)
    ax.text(50, total_y - 0.5, f'Total Points (0–{total_max:.1f})', fontsize=11,
            fontweight='bold', ha='center', va='top', color=COLOR_INK)
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        x_pos = 10 + frac * 80
        ax.plot([x_pos, x_pos], [total_y - 0.1, total_y + 0.1], color=COLOR_INK, linewidth=1.5)
        ax.text(x_pos, total_y - 0.3, f'{total_max * frac:.1f}', fontsize=8,
                ha='center', va='top', color=COLOR_INK)

    # Probability axis：由 lp = offset + (D/100)·points 反解
    prob_y = -1.6
    ax.plot([10, 90], [prob_y, prob_y], color=COLOR_DOWN, linewidth=3)
    ax.text(50, prob_y - 0.5, 'Probability', fontsize=11, fontweight='bold',
            ha='center', va='top', color=COLOR_DOWN)
    prob_ticks = [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    for label_pct in prob_ticks:
        if denom <= 0:
            break
        total_points = (float(logit(label_pct)) - offset) * 100.0 / denom
        if 0 <= total_points <= total_max:
            x_pos = 10 + total_points / total_max * 80
            ax.plot([x_pos, x_pos], [prob_y - 0.1, prob_y + 0.1], color=COLOR_DOWN, linewidth=1.5)
            ax.text(x_pos, prob_y - 0.3, f'{label_pct:.0%}', fontsize=7,
                    ha='center', va='top', color=COLOR_DOWN)

    plt.tight_layout()
    chart = ChartData(title="Nomogram 列线图", data=encode_figure(fig, fmt), type=fmt)

    table_rows = []
    for p in points_list:
        for val_label, val in [('Min', p['min']), ('Median', (p['min'] + p['max']) / 2),
                               ('Max', p['max'])]:
            pts = _point_value(val, p['min'], p['max'], p['coef'], denom)
            table_rows.append([p['variable'], val_label, round(val, 3), round(pts, 1)])
    table = TableData(
        title="Nomogram Points 参考表",
        headers=["Variable", "Level", "Value", "Points"],
        rows=table_rows)

    return chart, table, points_list, {"denom": denom, "total_max": total_max, "offset": offset}


def run_nomogram(request, fmt='svg'):
    ctx = nomogram_context(request)
    variables = ctx["feature_names"]
    ranges = ctx["ranges"]
    coefs = ctx["coefficients_raw"]
    intercept = ctx["intercept_raw"]

    chart, table, points_list, geometry = draw_nomogram(
        variables, ranges, coefs, intercept, ctx["model_type"], fmt)

    summary = (f"Nomogram生成完成。模型: {ctx['model_type']}，共{len(coefs)}个设计矩阵特征；"
               f"系数已还原到原始尺度（β_raw、b0_raw），概率轴由 sigmoid(lp) 反解。")
    return {
        "charts": [chart],
        "tables": [table],
        "summary": summary,
        "model_info": {
            "model_type": ctx["model_type"],
            "coefficients": coefs,
            "intercept": intercept,
            "ranges": ranges,
            "features": ctx["features"],
            "raw_scale": True,
            "nomogram_points": {
                p['variable']: {"min": p['min'], "max": p['max'], "coef": p['coef']}
                for p in points_list
            },
            "nomogram_geometry": geometry,
            "n_train": ctx["n_train"],
        }
    }
