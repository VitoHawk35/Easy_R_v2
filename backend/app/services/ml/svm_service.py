import pandas as pd
import numpy as np
from sklearn.svm import SVC, SVR
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

def run_svm(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]          # 原始未变换
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    kernel = request.params.get("kernel", "rbf")
    C = request.params.get("C", 1.0)
    gamma = request.params.get("gamma", "scale")
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if is_classifier:
        model = SVC(kernel=kernel, C=C, gamma=gamma, probability=True, random_state=seed)
    else:
        model = SVR(kernel=kernel, C=C, gamma=gamma)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=True, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    y_pred = pipe.predict(X_test)
    if is_classifier:
        y_prob = pipe.predict_proba(X_test)
        metrics = classification_metrics(y_test, y_pred, y_prob)
    else:
        metrics = regression_metrics(y_test, y_pred)
    # PCA visualization for 2D scatter（用训练集学得的预处理+标准化变换全数据，仅作展示）
    X_s = pipe[:-1].transform(X_df)
    if X_s.shape[1] > 2:
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X_s)
    else:
        X_pca = np.asarray(X_s)
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=y, cmap='viridis', edgecolors='k', alpha=0.7)
    ax.set_xlabel('PC1' if X_s.shape[1] > 2 else 'X1')
    ax.set_ylabel('PC2' if X_s.shape[1] > 2 else 'X2')
    ax.set_title(f'SVM {kernel.upper()} Kernel Data Distribution')
    plt.colorbar(scatter, ax=ax, label=request.y_variable)
    chart1 = ChartData(title="SVM数据分布", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    summary = f"SVM完成。核函数={kernel}，C={C}，支持向量数={len(model.support_)}。"
    return {"charts": [chart1], "tables": [metrics_table], "summary": summary}
