import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, plot_tree
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData, COLOR_PURPLE
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

def run_decision_tree(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]          # 原始未变换
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    max_depth = request.params.get("maxDepth", 5)
    min_samples_split = request.params.get("minSamplesSplit", 2)
    criterion = request.params.get("criterion", "gini")
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if is_classifier:
        model = DecisionTreeClassifier(max_depth=max_depth, min_samples_split=min_samples_split,
                                        criterion=criterion, random_state=seed)
    else:
        model = DecisionTreeRegressor(max_depth=max_depth, min_samples_split=min_samples_split,
                                       criterion="squared_error", random_state=seed)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=False, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    fitted_model = pipe.named_steps["clf"]
    y_pred = pipe.predict(X_test)
    if is_classifier:
        y_prob = pipe.predict_proba(X_test) if hasattr(fitted_model, "predict_proba") else None
        metrics = classification_metrics(y_test, y_pred, y_prob)
    else:
        metrics = regression_metrics(y_test, y_pred)
    # Feature importance
    imp_df = pd.DataFrame({
        "Variable": feature_names,
        "Importance": fitted_model.feature_importances_
    }).sort_values("Importance", ascending=False)
    # Charts
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    ax1, ax2 = axes
    # Tree plot
    plot_tree(fitted_model, feature_names=feature_names, filled=True, rounded=True, fontsize=8, ax=ax1, max_depth=3)
    ax1.set_title("决策树结构（前 3 层）")
    # Importance plot
    top_imp = imp_df.head(15).sort_values("Importance")
    ax2.barh(top_imp["Variable"], top_imp["Importance"], color=COLOR_PURPLE)
    ax2.set_xlabel("Importance")
    ax2.set_title("特征重要性")
    chart1 = ChartData(title="决策树结果", data=encode_figure(fig, fmt), type=fmt)
    # Tables
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"], rows=[[k, v] for k, v in metrics.items()])
    imp_table = TableData(title="特征重要性", headers=["Variable", "Importance"], rows=imp_df.values.tolist())
    summary = f"决策树完成。深度={max_depth}，节点数={fitted_model.tree_.node_count}。"
    return {"charts": [chart1], "tables": [metrics_table, imp_table], "summary": summary}
