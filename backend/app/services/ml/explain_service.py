import pandas as pd
import numpy as np
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

try:
    import shap
    HAS_SHAP = True
except Exception:
    HAS_SHAP = False

def _get_model_and_data(request):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    model_type = request.params.get("modelType", "random-forest")
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.linear_model import LogisticRegression, LinearRegression
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if model_type == "random-forest":
        model = RandomForestClassifier(n_estimators=100, random_state=seed) if is_classifier else RandomForestRegressor(n_estimators=100, random_state=seed)
    elif model_type == "logistic":
        model = LogisticRegression(max_iter=2000, random_state=seed) if is_classifier else LinearRegression()
    elif model_type == "xgboost":
        try:
            from xgboost import XGBClassifier, XGBRegressor
            model = XGBClassifier(n_estimators=100, random_state=seed, use_label_encoder=False, eval_metric='logloss') if is_classifier else XGBRegressor(n_estimators=100, random_state=seed)
        except Exception:
            model = RandomForestClassifier(n_estimators=100, random_state=seed) if is_classifier else RandomForestRegressor(n_estimators=100, random_state=seed)
    else:
        model = RandomForestClassifier(n_estimators=100, random_state=seed) if is_classifier else RandomForestRegressor(n_estimators=100, random_state=seed)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=False, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    fitted = pipe.named_steps["clf"]
    X_test_t = pipe.named_steps["prep"].transform(X_test)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    return fitted, X_test_t, y_test, feature_names

def run_shap(request, fmt="svg"):
    if not HAS_SHAP:
        raise ValueError("shap library not installed")
    model, X_test, y_test, cols = _get_model_and_data(request)
    explainer = shap.TreeExplainer(model) if hasattr(model, "tree_") or hasattr(model, "estimators_") else shap.KernelExplainer(model.predict, X_test.iloc[:50])
    shap_values = explainer.shap_values(X_test)
    if isinstance(shap_values, list):
        shap_vals = shap_values[1] if len(shap_values) > 1 else shap_values[0]
    elif getattr(shap_values, "ndim", 0) == 3:
        # 新版 shap 对分类器返回 (n_samples, n_features, n_classes)，取正类
        shap_vals = shap_values[:, :, 1] if shap_values.shape[2] > 1 else shap_values[:, :, 0]
    else:
        shap_vals = shap_values
    # SHAP Summary Plot (bar) - new shap API does not accept ax kwarg, draw into current figure
    plt.figure(figsize=(8, 7))
    shap.summary_plot(shap_vals, X_test, feature_names=cols, show=False, plot_type="bar")
    fig1 = plt.gcf()
    fig1.suptitle("SHAP Summary (Bar)")
    chart1 = ChartData(title="SHAP特征重要性图", data=encode_figure(fig1, fmt), type=fmt)
    # SHAP Beeswarm
    plt.figure(figsize=(8, 7))
    shap.summary_plot(shap_vals, X_test, feature_names=cols, show=False)
    fig2 = plt.gcf()
    fig2.suptitle("SHAP Beeswarm")
    chart2 = ChartData(title="SHAP分布图", data=encode_figure(fig2, fmt), type=fmt)
    # Top features table
    mean_shap = np.abs(shap_vals).mean(axis=0)
    shap_df = pd.DataFrame({"Variable": cols, "Mean|SHAP|": mean_shap}).sort_values("Mean|SHAP|", ascending=False)
    table = TableData(title="SHAP特征重要性", headers=["Variable", "Mean|SHAP|"], rows=shap_df.values.tolist())
    summary = f"SHAP分析完成。基于{len(X_test)}个测试样本，展示了各特征对模型预测的贡献。"
    return {"charts": [chart1, chart2], "tables": [table], "summary": summary}

def run_pdp(request, fmt="svg"):
    model, X_test, y_test, cols = _get_model_and_data(request)
    feature = request.params.get("feature", cols[0] if cols else None)
    if feature not in cols:
        feature = cols[0]
    idx = cols.index(feature)
    # Manual PDP computation
    X_copy = X_test.copy()
    grid = np.linspace(X_copy.iloc[:, idx].min(), X_copy.iloc[:, idx].max(), 50)
    pdp_vals = []
    for val in grid:
        X_temp = X_copy.copy()
        X_temp.iloc[:, idx] = val
        if hasattr(model, "predict_proba"):
            preds = model.predict_proba(X_temp)[:, 1]
        else:
            preds = model.predict(X_temp)
        pdp_vals.append(preds.mean())
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    ax1, ax2 = axes
    ax1.plot(grid, pdp_vals, 'b-', lw=2)
    ax1.set_xlabel(feature)
    ax1.set_ylabel("Average Prediction")
    ax1.set_title(f"PDP: {feature}")
    ax1.grid(True, alpha=0.3)
    # ICE lines: 对每个样本，逐一沿 grid 计算预测值
    n_ice = min(50, len(X_copy))
    for i in range(n_ice):
        # 取第 i 个样本，复制 len(grid) 份，把第 idx 列替换为 grid
        sample = X_copy.iloc[[i]].copy()
        X_ice = pd.concat([sample] * len(grid), ignore_index=True)
        X_ice.iloc[:, idx] = grid
        if hasattr(model, "predict_proba"):
            ice = model.predict_proba(X_ice)[:, 1]
        else:
            ice = model.predict(X_ice)
        ax2.plot(grid, ice, 'b-', alpha=0.1)
    ax2.plot(grid, pdp_vals, 'r-', lw=2, label="PDP")
    ax2.set_xlabel(feature)
    ax2.set_ylabel("Prediction")
    ax2.set_title(f"ICE + PDP: {feature}")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    chart1 = ChartData(title="PDP/ICE分析", data=encode_figure(fig, fmt), type=fmt)
    summary = f"PDP/ICE分析完成。特征={feature}，展示了该特征对预测结果的边际效应。"
    return {"charts": [chart1], "tables": [], "summary": summary}
