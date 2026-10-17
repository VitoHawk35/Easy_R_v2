import pandas as pd
import numpy as np
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
from app.services.core.models import canonical_key, create_model, needs_scale
import matplotlib.pyplot as plt

try:
    import shap
    HAS_SHAP = True
except Exception:
    HAS_SHAP = False


def _create_explanation_model(key, params, seed, is_classifier):
    """E3g：统一走模型工厂，未知 key 直接报错，不做静默替换。

    回归结局保留原有的 RF/XGB/线性回归实现（工厂目前只注册分类器）。
    """
    if is_classifier:
        return create_model(key, params, seed)
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    if key == "RF":
        return RandomForestRegressor(n_estimators=int(params.get("nEstimators", 200)),
                                     max_depth=int(params.get("maxDepth", 10)),
                                     random_state=seed, n_jobs=-1)
    if key == "XGB":
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=int(params.get("nEstimators", 200)),
                            max_depth=int(params.get("maxDepth", 5)),
                            learning_rate=float(params.get("learningRate", 0.1)),
                            random_state=seed, n_jobs=-1)
    if key == "LR":
        return LinearRegression()
    raise ValueError(f"回归结局的 SHAP/PDP 暂不支持模型类型: {key}")


def _get_model_and_data(request):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    params = request.params or {}
    seed = int(params.get("seed", request.seed))
    test_size = float(params.get("testSize", 0.3))
    if not (0.0 < test_size < 1.0):
        test_size = 0.3
    model_type = params.get("modelType", "random-forest")
    key = canonical_key(model_type)
    per_model = params.get("model_params", params.get("modelParams", {})) or {}
    model_params = per_model.get(key, per_model.get(model_type, {})) or {}
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    model = _create_explanation_model(key, model_params, seed, is_classifier)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=needs_scale(key) if is_classifier else False,
        X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    fitted = pipe.named_steps["clf"]
    X_test_t = pipe.named_steps["prep"].transform(X_test)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    return fitted, X_test_t, y_test, feature_names, is_classifier, key


def _predict_function(model, is_classifier):
    """E3g：非树模型分类任务解释概率（predict_proba），不要解释 0/1 硬标签。"""
    if is_classifier and hasattr(model, "predict_proba"):
        return lambda X: model.predict_proba(X)[:, 1]
    return model.predict


def run_shap(request, fmt="svg"):
    if not HAS_SHAP:
        raise ValueError("shap library not installed")
    model, X_test, y_test, cols, is_classifier, key = _get_model_and_data(request)
    predict_fn = _predict_function(model, is_classifier)
    is_tree = hasattr(model, "tree_") or hasattr(model, "estimators_")
    explainer = shap.TreeExplainer(model) if is_tree else shap.KernelExplainer(predict_fn, X_test.iloc[:50])
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
    fig1.suptitle("SHAP 特征贡献汇总（条形图）")
    chart1 = ChartData(title="SHAP特征重要性图", data=encode_figure(fig1, fmt), type=fmt)
    # SHAP Beeswarm
    plt.figure(figsize=(8, 7))
    shap.summary_plot(shap_vals, X_test, feature_names=cols, show=False)
    fig2 = plt.gcf()
    fig2.suptitle("SHAP 蜂群图")
    chart2 = ChartData(title="SHAP分布图", data=encode_figure(fig2, fmt), type=fmt)
    # Top features table
    mean_shap = np.abs(shap_vals).mean(axis=0)
    shap_df = pd.DataFrame({"Variable": cols, "Mean|SHAP|": mean_shap}).sort_values("Mean|SHAP|", ascending=False)
    table = TableData(title="SHAP特征重要性", headers=["Variable", "Mean|SHAP|"], rows=shap_df.values.tolist())
    summary = f"SHAP分析完成。模型={key}，基于{len(X_test)}个测试样本，展示了各特征对模型预测的贡献。"
    return {"charts": [chart1, chart2], "tables": [table], "summary": summary}


def run_pdp(request, fmt="svg"):
    model, X_test, y_test, cols, is_classifier, key = _get_model_and_data(request)
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
    ax1.set_title(f"部分依赖图（PDP）：{feature}")
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
    ax2.set_title(f"ICE + PDP：{feature}")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    chart1 = ChartData(title="PDP/ICE分析", data=encode_figure(fig, fmt), type=fmt)
    summary = f"PDP/ICE分析完成。模型={key}，特征={feature}，展示了该特征对预测结果的边际效应。"
    return {"charts": [chart1], "tables": [], "summary": summary}
