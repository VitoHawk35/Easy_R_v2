import pandas as pd
import numpy as np
from sklearn.neural_network import MLPClassifier, MLPRegressor
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

def run_mlp(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]          # 原始未变换
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    hidden_layers = request.params.get("hiddenLayers", "100,50")
    activation = request.params.get("activation", "relu")
    alpha = float(request.params.get("alpha", 0.0001))
    max_iter = int(request.params.get("maxIter", 500))
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    hidden_layer_sizes = tuple(int(x.strip()) for x in str(hidden_layers).split(",") if x.strip())
    if not hidden_layer_sizes:
        hidden_layer_sizes = (100,)
    if is_classifier:
        model = MLPClassifier(hidden_layer_sizes=hidden_layer_sizes, activation=activation, alpha=alpha,
                              max_iter=max_iter, random_state=seed, early_stopping=True)
    else:
        model = MLPRegressor(hidden_layer_sizes=hidden_layer_sizes, activation=activation, alpha=alpha,
                             max_iter=max_iter, random_state=seed, early_stopping=True)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=True, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    fitted_model = pipe.named_steps["clf"]
    y_pred = pipe.predict(X_test)
    if is_classifier:
        y_prob = pipe.predict_proba(X_test)
        metrics = classification_metrics(y_test, y_pred, y_prob)
    else:
        metrics = regression_metrics(y_test, y_pred)
    # Loss curve
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    ax1, ax2 = axes
    ax1.plot(fitted_model.loss_curve_, 'b-')
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Loss")
    ax1.set_title("MLP Training Loss Curve")
    # Actual vs Predicted
    ax2.scatter(y_test, y_pred, alpha=0.6, edgecolors='k')
    ax2.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
    ax2.set_xlabel("Actual")
    ax2.set_ylabel("Predicted")
    ax2.set_title("Actual vs Predicted")
    chart1 = ChartData(title="神经网络结果", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    summary = f"神经网络完成。hidden_layers={hidden_layer_sizes}, activation={activation}, 迭代={len(fitted_model.loss_curve_)}。"
    return {"charts": [chart1], "tables": [metrics_table], "summary": summary}
