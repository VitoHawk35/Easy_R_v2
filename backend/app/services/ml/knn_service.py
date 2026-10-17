import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.base import clone
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData, COLOR_UP
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

def run_knn(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]          # 原始未变换
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    k = int(request.params.get("k", 5))
    weights = request.params.get("weights", "uniform")
    metric = request.params.get("metric", "minkowski")
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if is_classifier:
        model = KNeighborsClassifier(n_neighbors=k, weights=weights, metric=metric)
    else:
        model = KNeighborsRegressor(n_neighbors=k, weights=weights, metric=metric)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=True, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    y_pred = pipe.predict(X_test)
    if is_classifier:
        y_prob = pipe.predict_proba(X_test) if hasattr(pipe.named_steps["clf"], "predict_proba") else None
        metrics = classification_metrics(y_test, y_pred, y_prob)
    else:
        metrics = regression_metrics(y_test, y_pred)
    # K selection plot
    k_range = range(1, min(21, len(X_train)))
    scores = []
    for ki in k_range:
        # 每个候选 K 用独立 Pipeline：预处理只在训练集 fit，防泄漏
        p = clone(pipe).set_params(clf__n_neighbors=ki)
        p.fit(X_train, y_train)
        scores.append(p.score(X_test, y_test))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(list(k_range), scores, 'bo-')
    ax.axvline(k, color=COLOR_UP, linestyle='--', label=f'Selected K={k}')
    ax.set_xlabel('K')
    ax.set_ylabel('Score (Accuracy or R2)')
    ax.set_title('K-NN 近邻数选择')
    ax.legend()
    chart1 = ChartData(title="K值选择", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    summary = f"K-近邻完成。K={k}，距离度量={metric}，权重={weights}。"
    return {"charts": [chart1], "tables": [metrics_table], "summary": summary}
