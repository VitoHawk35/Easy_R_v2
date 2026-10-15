import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline

# Supported models with linear coefficients
LINEAR_MODELS = {
    'logistic': 'sklearn.linear_model.LogisticRegression',
    'lasso': 'sklearn.linear_model.Lasso',
    'lasso-predict': 'sklearn.linear_model.Lasso',
    'elastic-net': 'sklearn.linear_model.ElasticNet',
    'cox': 'lifelines.CoxPHFitter',
}

def _get_points_scale(x, xmin, xmax, points_min=0, points_max=100):
    """Map a variable value to points linearly."""
    if xmax == xmin:
        return points_max / 2
    return points_min + (x - xmin) / (xmax - xmin) * (points_max - points_min)

def draw_nomogram(variables, ranges, coefs, intercept=0, model_type='logistic', fmt='svg'):
    """
    Draw a simplified nomogram using matplotlib.
    variables: list of feature names
    ranges: dict {name: (min, max)}
    coefs: dict {name: coefficient}
    intercept: model intercept
    """
    n_vars = len(variables)
    fig_height = max(6, n_vars * 1.2 + 2)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    ax.set_xlim(0, 100)
    ax.set_ylim(-1, n_vars + 2)
    ax.axis('off')

    # Title
    ax.text(50, n_vars + 1.5, 'Nomogram 列线图', fontsize=14, fontweight='bold',
            ha='center', va='center')

    y_positions = np.linspace(n_vars - 0.5, 0.5, n_vars)
    points_list = []

    for i, var in enumerate(variables):
        y = y_positions[i]
        vmin, vmax = ranges[var]
        c = coefs[var]

        # Draw variable axis line
        ax.plot([10, 90], [y, y], color='#333', linewidth=2)
        # Min/Max labels
        ax.text(5, y, f'{vmin:.1f}', fontsize=8, ha='right', va='center')
        ax.text(95, y, f'{vmax:.1f}', fontsize=8, ha='left', va='center')
        # Variable name (bold, colored)
        color = '#2f855a' if c >= 0 else '#c53030'
        ax.text(50, y + 0.3, f'{var} (β={c:.3f})', fontsize=10, fontweight='bold',
                ha='center', va='bottom', color=color)

        # Tick marks every 25%
        for pct in [0, 0.25, 0.5, 0.75, 1.0]:
            x_pos = 10 + pct * 80
            val = vmin + pct * (vmax - vmin)
            ax.plot([x_pos, x_pos], [y - 0.08, y + 0.08], color='#666', linewidth=1)
            ax.text(x_pos, y - 0.25, f'{val:.1f}', fontsize=7, ha='center', va='top', color='#666')

        points_list.append({
            'variable': var,
            'min': vmin,
            'max': vmax,
            'coef': c,
            'y': y
        })

    # Total Points axis (bottom)
    total_y = -0.5
    ax.plot([10, 90], [total_y, total_y], color='#2f855a', linewidth=3)
    ax.text(50, total_y - 0.5, 'Total Points', fontsize=11, fontweight='bold',
            ha='center', va='top', color='#2f855a')
    for pts in [0, 25, 50, 75, 100]:
        x_pos = 10 + pts / 100 * 80
        ax.plot([x_pos, x_pos], [total_y - 0.1, total_y + 0.1], color='#2f855a', linewidth=1.5)
        ax.text(x_pos, total_y - 0.3, str(pts), fontsize=8, ha='center', va='top', color='#2f855a')

    # Probability axis (very bottom)
    prob_y = -1.3
    ax.plot([10, 90], [prob_y, prob_y], color='#3182ce', linewidth=3)
    ax.text(50, prob_y - 0.5, 'Probability', fontsize=11, fontweight='bold',
            ha='center', va='top', color='#3182ce')

    # Probability ticks (sigmoid mapping for logistic)
    if model_type == 'logistic':
        # Total points range roughly: sum of scaled coefs
        total_range = sum(abs(coefs[v]) * (ranges[v][1] - ranges[v][0]) for v in variables)
        for label_pct in [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]:
            # Inverse sigmoid: logit(p) = total_points + intercept
            # total_points = logit(p) - intercept
            from scipy.special import logit
            tp = logit(label_pct) - intercept
            # Map tp to 0-100 scale approximately
            x_pos = 10 + ((tp + total_range/2) / total_range) * 80
            x_pos = max(10, min(90, x_pos))
            ax.plot([x_pos, x_pos], [prob_y - 0.1, prob_y + 0.1], color='#3182ce', linewidth=1.5)
            ax.text(x_pos, prob_y - 0.3, f'{label_pct:.0%}', fontsize=7, ha='center', va='top', color='#3182ce')
    else:
        for p in [0.0, 0.25, 0.5, 0.75, 1.0]:
            x_pos = 10 + p * 80
            ax.plot([x_pos, x_pos], [prob_y - 0.1, prob_y + 0.1], color='#3182ce', linewidth=1.5)
            ax.text(x_pos, prob_y - 0.3, f'{p:.0%}', fontsize=7, ha='center', va='top', color='#3182ce')

    # Draw vertical reference lines connecting to Total Points (example lines)
    # We'll draw 3 sample lines for low/medium/high risk
    for scenario_label, scenario_color in [('低风险', '#48bb78'), ('中风险', '#ecc94b'), ('高风险', '#f56565')]:
        ax.annotate('', xy=(50, total_y + 0.15), xytext=(50, n_vars - 0.5),
                    arrowprops=dict(arrowstyle='->', color=scenario_color, lw=1.5, ls='--'))

    plt.tight_layout()
    chart = ChartData(title="Nomogram 列线图", data=encode_figure(fig, fmt), type=fmt)

    # Also generate a points reference table
    table_rows = []
    for p in points_list:
        vmin, vmax = p['min'], p['max']
        c = p['coef']
        # Show points for min, median, max
        for val_label, val in [('Min', vmin), ('Median', (vmin+vmax)/2), ('Max', vmax)]:
            pts = _get_points_scale(val, vmin, vmax) * abs(c)
            table_rows.append([p['variable'], val_label, round(val, 2), round(pts, 1)])

    table = TableData(
        title="Nomogram Points 参考表",
        headers=["Variable", "Level", "Value", "Points"],
        rows=table_rows
    )

    return chart, table, points_list


def run_nomogram(request, fmt='svg'):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)

    model_type = request.params.get("modelType", "logistic")
    seed = request.params.get("seed", request.seed)
    standardize = request.params.get("standardize", True)

    # Train the model to get coefficients（预处理只在训练集 fit，防泄漏）
    from sklearn.linear_model import LogisticRegression

    if model_type == 'logistic':
        model = LogisticRegression(max_iter=2000, random_state=seed)
    elif model_type in ('lasso', 'lasso-predict'):
        alpha = float(request.params.get('alpha', 0.1))
        # For classification, use LogisticRegression with L1 penalty instead of Lasso regressor
        model = LogisticRegression(
            penalty='l1',
            C=1.0 / max(alpha, 1e-6),
            solver='saga',
            max_iter=5000, random_state=seed
        )
    elif model_type == 'elastic-net':
        alpha = float(request.params.get('alpha', 0.1))
        l1_ratio = float(request.params.get('l1Ratio', 0.5))
        # Use SGDClassifier with log_loss for classification elastic net
        from sklearn.linear_model import SGDClassifier
        model = SGDClassifier(
            loss='log_loss',
            penalty='elasticnet',
            alpha=alpha,
            l1_ratio=l1_ratio,
            max_iter=5000, random_state=seed
        )
    else:
        raise ValueError(f"Nomogram暂不支持模型类型: {model_type}")

    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=True, X=X_df, y=y, test_size=0.3, seed=seed,
        stratify=True, variable_types=request.variable_types)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    fitted = pipe.named_steps["clf"]
    coefs = dict(zip(feature_names, fitted.coef_[0]))
    intercept = float(fitted.intercept_[0])

    # Get ranges from transformed design matrix (unscaled; 仅用于列线图刻度展示)
    X_all = pipe.named_steps["prep"].transform(X_df)
    ranges = {}
    for col in feature_names:
        ranges[col] = (float(X_all[col].min()), float(X_all[col].max()))

    chart, table, points_list = draw_nomogram(
        feature_names, ranges, coefs, intercept, model_type, fmt
    )

    summary = f"Nomogram生成完成。模型: {model_type}，共{len(coefs)}个变量。"
    return {
        "charts": [chart],
        "tables": [table],
        "summary": summary,
        "model_info": {
            "model_type": model_type,
            "coefficients": coefs,
            "intercept": intercept,
            "ranges": ranges,
            "nomogram_points": {p['variable']: {"min": p['min'], "max": p['max'], "coef": p['coef']} for p in points_list}
        }
    }
