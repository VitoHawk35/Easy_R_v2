import pandas as pd
import numpy as np
from sklearn.svm import SVR
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, regression_metrics, ChartData, TableData, COLOR_UP, COLOR_MUTED
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

def run_bkm(request, fmt="svg"):
    """Bayesian Kernel Machine Regression (BKM) - use SVR with RBF as approximation."""
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    kernel = request.params.get("kernel", "rbf")
    iterations = int(request.params.get("iterations", 1000))
    model = SVR(kernel=kernel, C=1.0, gamma='scale')
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=True, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=False, variable_types=request.variable_types)
    y_pred = pipe.predict(X_test)
    metrics = regression_metrics(y_test, y_pred)
    # Actual vs Predicted plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    ax1, ax2 = axes
    ax1.scatter(y_test, y_pred, alpha=0.6, edgecolors=COLOR_MUTED)
    ax1.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], color=COLOR_UP, linestyle='--', lw=2)
    ax1.set_xlabel('Actual')
    ax1.set_ylabel('Predicted')
    ax1.set_title('实际值 vs 预测值')
    residuals = y_test - y_pred
    ax2.scatter(y_pred, residuals, alpha=0.6, edgecolors=COLOR_MUTED)
    ax2.axhline(0, color=COLOR_UP, linestyle='--')
    ax2.set_xlabel('Predicted')
    ax2.set_ylabel('Residuals')
    ax2.set_title('残差图')
    chart1 = ChartData(title="BKM回归结果", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    summary = f"贝叶斯核机器回归完成。核函数={kernel}，迭代参考={iterations}。"
    return {"charts": [chart1], "tables": [metrics_table], "summary": summary}
