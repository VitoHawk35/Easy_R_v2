import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.linear_model import LogisticRegression
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline


def run_adv_diag(request, fmt='svg'):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)

    seed = request.params.get("seed", request.seed)
    model_type = request.params.get("modelType", "logistic")
    standardize = request.params.get("standardize", True)

    if model_type != 'logistic':
        raise ValueError(f"高级诊断暂仅支持logistic回归，当前: {model_type}")
    model = LogisticRegression(max_iter=2000, random_state=seed)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=True, X=X_df, y=y, test_size=0.3, seed=seed,
        stratify=True, variable_types=request.variable_types)
    fitted = pipe.named_steps["clf"]
    # 诊断基于训练集（in-sample 残差/杠杆值），用变换后的训练设计矩阵
    X_train_s = pipe.named_steps["scale"].transform(pipe.named_steps["prep"].transform(X_train))
    y_prob = fitted.predict_proba(X_train_s)[:, 1]
    y_pred = fitted.predict(X_train_s)

    n = len(y_train)
    p = X_train_s.shape[1]

    # Pearson residuals
    pearson_residuals = (y_train.values - y_prob) / np.sqrt(y_prob * (1 - y_prob))
    # Deviance residuals
    deviance_residuals = np.where(
        y_train.values == 1,
        np.sqrt(-2 * np.log(y_prob + 1e-10)),
        -np.sqrt(-2 * np.log(1 - y_prob + 1e-10))
    )

    # Leverage (hat values)
    X_design = np.column_stack([np.ones(n), X_train_s])
    H = X_design @ np.linalg.inv(X_design.T @ X_design + np.eye(p+1)*1e-6) @ X_design.T
    leverage = np.diag(H)

    # Cook's distance approximation
    # D_i = (r_i^2 / (p+1)) * (h_ii / (1 - h_ii))
    cooks_d = (pearson_residuals**2 / (p + 1)) * (leverage / (1 - leverage + 1e-10))

    # Standardized Pearson residuals
    std_residuals = pearson_residuals / np.sqrt(1 - leverage + 1e-10)

    # Charts
    charts = []
    tables = []

    # 1. Residuals vs Fitted
    fig1, axes = plt.subplots(1, 2, figsize=(14, 5))
    ax1, ax2 = axes
    ax1.scatter(y_prob, std_residuals, alpha=0.6, edgecolors='none', s=40)
    ax1.axhline(0, color='r', linestyle='--')
    ax1.axhline(2, color='orange', linestyle=':', label='±2')
    ax1.axhline(-2, color='orange', linestyle=':')
    ax1.set_xlabel("Fitted Values (Predicted Probability)")
    ax1.set_ylabel("Standardized Pearson Residuals")
    ax1.set_title("Residuals vs Fitted")
    ax1.legend()

    # 2. Q-Q plot
    stats.probplot(std_residuals, dist="norm", plot=ax2)
    ax2.set_title("Q-Q Plot (Normal)")
    ax2.get_lines()[0].set_markerfacecolor('#3498db')
    ax2.get_lines()[0].set_markersize(5)
    ax2.get_lines()[1].set_color('#e74c3c')
    charts.append(ChartData(title="残差分析", data=encode_figure(fig1, fmt), type=fmt))

    # 3. Cook's Distance
    fig2, ax3 = plt.subplots(figsize=(10, 5))
    ax3.stem(range(n), cooks_d, basefmt=" ")
    ax3.axhline(4 / n, color='r', linestyle='--', label=f'4/n = {4/n:.3f}')
    ax3.axhline(1, color='orange', linestyle=':', label='1.0')
    ax3.set_xlabel("Observation Index")
    ax3.set_ylabel("Cook's Distance")
    ax3.set_title("Cook's Distance (Influence Detection)")
    ax3.legend()
    charts.append(ChartData(title="Cook距离", data=encode_figure(fig2, fmt), type=fmt))

    # 4. Leverage vs Standardized Residuals
    fig3, ax4 = plt.subplots(figsize=(8, 6))
    ax4.scatter(leverage, std_residuals, alpha=0.6, s=40)
    ax4.axhline(0, color='k', linestyle='--', linewidth=0.8)
    ax4.axhline(2, color='orange', linestyle=':')
    ax4.axhline(-2, color='orange', linestyle=':')
    # Average leverage = (p+1)/n
    avg_leverage = (p + 1) / n
    ax4.axvline(2 * avg_leverage, color='r', linestyle='--', label=f'2×avg leverage = {2*avg_leverage:.3f}')
    ax4.axvline(3 * avg_leverage, color='darkred', linestyle='--', label=f'3×avg leverage = {3*avg_leverage:.3f}')
    ax4.set_xlabel("Leverage (Hat Values)")
    ax4.set_ylabel("Standardized Residuals")
    ax4.set_title("Leverage vs Standardized Residuals")
    ax4.legend()
    charts.append(ChartData(title="杠杆值-残差散点图", data=encode_figure(fig3, fmt), type=fmt))

    # Tables
    # Top influential points
    infl_idx = np.argsort(cooks_d)[::-1][:10]
    infl_rows = []
    for i in infl_idx:
        infl_rows.append([
            int(i),
            round(float(y_prob[i]), 3),
            round(float(std_residuals[i]), 3),
            round(float(leverage[i]), 4),
            round(float(cooks_d[i]), 4),
            "高影响" if cooks_d[i] > 4/n else "正常"
        ])
    tables.append(TableData(
        title="Top 10 影响点检测",
        headers=["Index", "Predicted Prob", "Std Residual", "Leverage", "Cook's D", "Status"],
        rows=infl_rows
    ))

    # Residual summary
    tables.append(TableData(
        title="残差统计摘要",
        headers=["Metric", "Value"],
        rows=[
            ["Mean Std Residual", round(float(np.mean(std_residuals)), 4)],
            ["Std Std Residual", round(float(np.std(std_residuals)), 4)],
            ["Max |Std Residual|", round(float(np.max(np.abs(std_residuals))), 4)],
            ["Max Leverage", round(float(np.max(leverage)), 4)],
            ["Max Cook's D", round(float(np.max(cooks_d)), 4)],
            ["High Influence Count (D>4/n)", int(np.sum(cooks_d > 4/n))],
        ]
    ))

    summary = (
        f"高级诊断完成。样本量{n}，变量数{p}。"
        f"最大标准化残差{np.max(np.abs(std_residuals)):.2f}，"
        f"最大Cook距离{np.max(cooks_d):.4f}，"
        f"高影响点{int(np.sum(cooks_d > 4/n))}个。"
    )

    return {
        "charts": charts,
        "tables": tables,
        "summary": summary
    }
