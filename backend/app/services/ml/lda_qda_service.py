import pandas as pd
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis, QuadraticDiscriminantAnalysis
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, ChartData, TableData, COLOR_UP, COLOR_DOWN, COLOR_MUTED
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

def run_lda(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    solver = request.params.get("solver", "svd")
    model = LinearDiscriminantAnalysis(solver=solver)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=True, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=True, variable_types=request.variable_types)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    fitted_model = pipe.named_steps["clf"]
    y_pred = pipe.predict(X_test)
    y_prob = pipe.predict_proba(X_test)
    metrics = classification_metrics(y_test, y_pred, y_prob)
    # LD plot
    if len(feature_names) >= 2:
        X_s = pipe.named_steps["scale"].transform(pipe.named_steps["prep"].transform(X_df))
        X_ld = fitted_model.transform(X_s)
        fig, ax = plt.subplots(figsize=(8, 6))
        for cls in np.unique(y):
            ax.scatter(X_ld[y == cls, 0], X_ld[y == cls, 1] if X_ld.shape[1] > 1 else np.zeros_like(X_ld[y == cls, 0]),
                       label=f'Class {cls}', alpha=0.7, edgecolors=COLOR_MUTED)
        ax.set_xlabel('LD1')
        ax.set_ylabel('LD2' if X_ld.shape[1] > 1 else ' ')
        ax.set_title('LDA 线性判别图')
        ax.legend()
    else:
        fig, ax = plt.subplots(figsize=(8, 5))
        coefs = pd.Series(fitted_model.coef_[0], index=feature_names).sort_values()
        colors = [COLOR_DOWN if c < 0 else COLOR_UP for c in coefs]
        ax.barh(coefs.index, coefs.values, color=colors)
        ax.set_title('LDA 系数')
    chart1 = ChartData(title="LDA结果", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    summary = f"LDA完成。求解器={solver}，类别数={len(np.unique(y))}。"
    return {"charts": [chart1], "tables": [metrics_table], "summary": summary}

def run_qda(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    reg_param = request.params.get("regParam", 0.0)
    model = QuadraticDiscriminantAnalysis(reg_param=reg_param)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=True, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=True, variable_types=request.variable_types)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    fitted_model = pipe.named_steps["clf"]
    y_pred = pipe.predict(X_test)
    y_prob = pipe.predict_proba(X_test)
    metrics = classification_metrics(y_test, y_pred, y_prob)
    fig, ax = plt.subplots(figsize=(8, 5))
    # show means per class as a heatmap
    means = pd.DataFrame(fitted_model.means_, columns=feature_names, index=[f'Class {c}' for c in fitted_model.classes_])
    im = ax.imshow(means.values, cmap='coolwarm', aspect='auto')
    ax.set_xticks(range(len(means.columns)))
    ax.set_xticklabels(means.columns, rotation=45, ha='right')
    ax.set_yticks(range(len(means.index)))
    ax.set_yticklabels(means.index)
    ax.set_title('QDA 类别均值（标准化）')
    plt.colorbar(im, ax=ax)
    chart1 = ChartData(title="QDA结果", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    summary = f"QDA完成。正则化参数={reg_param}，类别数={len(np.unique(y))}。"
    return {"charts": [chart1], "tables": [metrics_table], "summary": summary}
