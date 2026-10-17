import pandas as pd
import numpy as np
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData, COLOR_PURPLE
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

try:
    from xgboost import XGBClassifier, XGBRegressor
    HAS_XGB = True
except Exception:
    HAS_XGB = False

def run_xgboost(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    n_estimators = int(request.params.get("nEstimators", 200))
    max_depth = int(request.params.get("maxDepth", 6))
    learning_rate = float(request.params.get("learningRate", 0.1))
    subsample = float(request.params.get("subsample", 1.0))
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if not HAS_XGB:
        from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
        if is_classifier:
            model = GradientBoostingClassifier(n_estimators=n_estimators, max_depth=max_depth,
                                               learning_rate=learning_rate, subsample=subsample, random_state=seed)
        else:
            model = GradientBoostingRegressor(n_estimators=n_estimators, max_depth=max_depth,
                                              learning_rate=learning_rate, subsample=subsample, random_state=seed)
    else:
        if is_classifier:
            model = XGBClassifier(n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate,
                                  subsample=subsample, random_state=seed, use_label_encoder=False,
                                  eval_metric='logloss', n_jobs=-1)
        else:
            model = XGBRegressor(n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate,
                                 subsample=subsample, random_state=seed, n_jobs=-1)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=False, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    fitted_model = pipe.named_steps["clf"]
    y_pred = pipe.predict(X_test)
    if is_classifier:
        y_prob = pipe.predict_proba(X_test)
        metrics = classification_metrics(y_test, y_pred, y_prob)
        if len(np.unique(y)) == 2:
            from sklearn.metrics import roc_curve
            fpr, tpr, _ = roc_curve(y_test, y_prob[:, 1])
        else:
            fpr, tpr = None, None
    else:
        metrics = regression_metrics(y_test, y_pred)
        fpr, tpr = None, None
    imp = fitted_model.feature_importances_
    imp_df = pd.DataFrame({"Variable": feature_names, "Importance": imp}).sort_values("Importance", ascending=False)
    if fpr is not None:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        ax1, ax2 = axes
        ax1.plot(fpr, tpr, 'b-', lw=2, label=f'ROC (AUC={metrics.get("AUC",0):.3f})')
        ax1.plot([0, 1], [0, 1], 'k--')
        ax1.set_xlabel('FPR'); ax1.set_ylabel('TPR'); ax1.set_title('ROC 曲线'); ax1.legend()
        top_imp = imp_df.head(15).sort_values("Importance")
        ax2.barh(top_imp["Variable"], top_imp["Importance"], color=COLOR_PURPLE)
        ax2.set_xlabel("Importance"); ax2.set_title("特征重要性")
        chart1 = ChartData(title="XGBoost结果", data=encode_figure(fig, fmt), type=fmt)
    else:
        fig, ax = plt.subplots(figsize=(8, max(5, len(imp_df)*0.3)))
        top_imp = imp_df.head(15).sort_values("Importance")
        ax.barh(top_imp["Variable"], top_imp["Importance"], color=COLOR_PURPLE)
        ax.set_xlabel("Importance"); ax.set_title("特征重要性")
        chart1 = ChartData(title="XGBoost结果", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    imp_table = TableData(title="特征重要性", headers=["Variable", "Importance"], rows=imp_df.values.tolist())
    summary = f"XGBoost完成。n_estimators={n_estimators}, max_depth={max_depth}, learning_rate={learning_rate}。"
    return {"charts": [chart1], "tables": [metrics_table, imp_table], "summary": summary}
