import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 服务器防火墙下走HF镜像下载模型权重

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.inspection import permutation_importance
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import make_pipeline
import matplotlib.pyplot as plt

try:
    from tabpfn import TabPFNClassifier, TabPFNRegressor
    HAS_TABPFN = True
except Exception:
    HAS_TABPFN = False


def run_tabpfn(request, fmt="svg"):
    if not HAS_TABPFN:
        raise ValueError("TabPFN未安装，请在后端环境执行: pip install tabpfn")
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    n_estimators = int(request.params.get("nEstimators", 4))
    max_samples = int(request.params.get("maxSamples", 10000))
    device = request.params.get("device", "auto")
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    n_classes = len(np.unique(y)) if is_classifier else 0
    if is_classifier and n_classes > 10:
        raise ValueError(f"TabPFN分类任务最多支持10个类别，当前响应变量有{n_classes}个类别")
    X_train, X_test, y_train, y_test = train_test_split(
        X_df, y, test_size=test_size, random_state=seed, stratify=y if is_classifier else None)
    # TabPFN训练集过大时进行子采样
    subsampled = False
    if len(X_train) > max_samples:
        idx = np.random.RandomState(seed).choice(len(X_train), max_samples, replace=False)
        X_train = X_train.iloc[idx]
        y_train = y_train.iloc[idx]
        subsampled = True
    if is_classifier:
        model = TabPFNClassifier(n_estimators=n_estimators, device=device)
    else:
        model = TabPFNRegressor(n_estimators=n_estimators, device=device)
    # 预处理随训练集重新 fit，防泄漏；子采样先于 fit，满足 TabPFN 样本数限制
    pipe = make_pipeline(lambda: model, scale=False, variable_types=request.variable_types)
    pipe.fit(X_train, y_train)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    fitted_model = pipe.named_steps["clf"]
    y_pred = pipe.predict(X_test)
    if is_classifier:
        y_prob = pipe.predict_proba(X_test)
        metrics = classification_metrics(y_test, y_pred, y_prob)
    else:
        metrics = regression_metrics(y_test, y_pred)
    # TabPFN无内置特征重要性，使用排列重要性（在预处理后的测试集上）
    scoring = "accuracy" if is_classifier else "r2"
    X_test_t = pipe.named_steps["prep"].transform(X_test)
    perm = permutation_importance(fitted_model, X_test_t, y_test, n_repeats=5,
                                  random_state=seed, scoring=scoring)
    imp_df = pd.DataFrame({
        "Variable": feature_names,
        "Importance": perm.importances_mean
    }).sort_values("Importance", ascending=False)
    fig, ax = plt.subplots(figsize=(8, max(5, len(imp_df) * 0.3)))
    top_imp = imp_df.head(15).sort_values("Importance")
    ax.barh(top_imp["Variable"], top_imp["Importance"], color="#16a085")
    ax.set_xlabel("Permutation Importance")
    ax.set_title("TabPFN Feature Importance")
    chart1 = ChartData(title="TabPFN结果", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    imp_table = TableData(title="特征重要性(排列重要性)", headers=["Variable", "Importance"], rows=imp_df.values.tolist())
    summary = f"TabPFN完成。n_estimators={n_estimators}，device={device}，训练样本数={len(X_train)}。"
    if subsampled:
        summary += f"训练集超过{max_samples}样本，已随机子采样。"
    return {"charts": [chart1], "tables": [metrics_table, imp_table], "summary": summary}
