import pandas as pd
import numpy as np
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

try:
    from catboost import CatBoostClassifier, CatBoostRegressor
    HAS_CATBOOST = True
except Exception:
    HAS_CATBOOST = False

def run_catboost(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    iterations = int(request.params.get("iterations", 500))
    learning_rate = float(request.params.get("learning_rate", 0.1))
    depth = int(request.params.get("depth", 6))
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if not HAS_CATBOOST:
        from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
        if is_classifier:
            model = GradientBoostingClassifier(n_estimators=iterations, learning_rate=learning_rate,
                                               max_depth=depth, random_state=seed)
        else:
            model = GradientBoostingRegressor(n_estimators=iterations, learning_rate=learning_rate,
                                              max_depth=depth, random_state=seed)
    else:
        if is_classifier:
            model = CatBoostClassifier(iterations=iterations, learning_rate=learning_rate, depth=depth,
                                       random_seed=seed, verbose=False, loss_function='Logloss')
        else:
            model = CatBoostRegressor(iterations=iterations, learning_rate=learning_rate, depth=depth,
                                      random_seed=seed, verbose=False, loss_function='RMSE')
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=False, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    fitted_model = pipe.named_steps["clf"]
    if HAS_CATBOOST:
        # 保留旧代码 eval_set 行为：用训练集 fit 好的预处理器显式变换训练/测试集后重训
        prep = pipe.named_steps["prep"]
        fitted_model.fit(prep.transform(X_train), y_train,
                         eval_set=(prep.transform(X_test), y_test), verbose=False)
    y_pred = pipe.predict(X_test)
    if is_classifier:
        y_prob = pipe.predict_proba(X_test)
        metrics = classification_metrics(y_test, y_pred, y_prob)
    else:
        metrics = regression_metrics(y_test, y_pred)
    if HAS_CATBOOST:
        imp = fitted_model.get_feature_importance()
    else:
        imp = fitted_model.feature_importances_
    imp_df = pd.DataFrame({
        "Variable": feature_names,
        "Importance": imp
    }).sort_values("Importance", ascending=False)
    fig, ax = plt.subplots(figsize=(8, max(5, len(imp_df)*0.3)))
    top_imp = imp_df.head(15).sort_values("Importance")
    ax.barh(top_imp["Variable"], top_imp["Importance"], color="#9b59b6")
    ax.set_xlabel("Importance")
    ax.set_title("CatBoost Feature Importance")
    chart1 = ChartData(title="CatBoost结果", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    imp_table = TableData(title="特征重要性", headers=["Variable", "Importance"], rows=imp_df.values.tolist())
    summary = f"CatBoost完成。iterations={iterations}，depth={depth}，learning_rate={learning_rate}。"
    return {"charts": [chart1], "tables": [metrics_table, imp_table], "summary": summary}
