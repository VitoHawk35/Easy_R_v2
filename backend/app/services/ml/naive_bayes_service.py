import pandas as pd
import numpy as np
from sklearn.naive_bayes import GaussianNB
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

def run_naive_bayes(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]          # 原始未变换
    y, le = encode_y(df[request.y_variable], request.variable_types)
    if len(np.unique(y)) > 10 or y.dtype == float:
        raise ValueError("Naive Bayes supports classification only")
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    var_smoothing = float(request.params.get("varSmoothing", 1e-9))
    model = GaussianNB(var_smoothing=var_smoothing)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=False, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=True, variable_types=request.variable_types)
    fitted_model = pipe.named_steps["clf"]
    y_pred = pipe.predict(X_test)
    y_prob = pipe.predict_proba(X_test)
    metrics = classification_metrics(y_test, y_pred, y_prob)
    if len(np.unique(y)) == 2:
        from sklearn.metrics import roc_curve
        fpr, tpr, _ = roc_curve(y_test, y_prob[:, 1])
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(fpr, tpr, 'b-', lw=2, label=f'ROC (AUC={metrics.get("AUC",0):.3f})')
        ax.plot([0, 1], [0, 1], 'k--')
        ax.set_xlabel('FPR'); ax.set_ylabel('TPR'); ax.set_title('ROC Curve'); ax.legend()
        chart1 = ChartData(title="朴素贝叶斯ROC", data=encode_figure(fig, fmt), type=fmt)
    else:
        # Confusion matrix heatmap
        from sklearn.metrics import confusion_matrix
        cm = confusion_matrix(y_test, y_pred)
        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(cm, cmap='Blues')
        ax.set_xticks(range(len(fitted_model.classes_)))
        ax.set_yticks(range(len(fitted_model.classes_)))
        ax.set_xticklabels(fitted_model.classes_)
        ax.set_yticklabels(fitted_model.classes_)
        ax.set_xlabel('Predicted'); ax.set_ylabel('Actual'); ax.set_title('Confusion Matrix')
        for i in range(len(fitted_model.classes_)):
            for j in range(len(fitted_model.classes_)):
                ax.text(j, i, cm[i, j], ha='center', va='center', color='red')
        plt.colorbar(im, ax=ax)
        chart1 = ChartData(title="混淆矩阵", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    summary = f"朴素贝叶斯完成。类别数={len(fitted_model.classes_)}，var_smoothing={var_smoothing}。"
    return {"charts": [chart1], "tables": [metrics_table], "summary": summary}
