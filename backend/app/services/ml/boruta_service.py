import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData, COLOR_UP, COLOR_DOWN, COLOR_WARN
from app.services.core.preprocessing import ClinicalPreprocessor, encode_y
import matplotlib.pyplot as plt

try:
    from boruta import BorutaPy
    HAS_BORUTA = True
except Exception:
    HAS_BORUTA = False

def run_boruta(request, fmt="svg"):
    df = get_data_for_ml(
        request.dataset_id, request.y_variable, request.x_variables,
        request.is_survival, request.time_variable, request.filters
    )
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    # 全数据特征选择（无留出验证）：ClinicalPreprocessor 全数据 fit + transform
    X_df = df[list(request.x_variables)]
    prep = ClinicalPreprocessor(request.variable_types).fit(X_df)
    X = prep.transform(X_df)
    y, le = encode_y(df[request.y_variable], request.variable_types)
    max_runs = request.params.get("maxRuns", 100)
    p_value = request.params.get("pValue", 0.01)
    seed = request.params.get("seed", request.seed)
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if not HAS_BORUTA:
        # Fallback: use RandomForest feature importances
        if is_classifier:
            model = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=seed, n_jobs=-1)
        else:
            model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=seed, n_jobs=-1)
        model.fit(X, y)
        importances = model.feature_importances_
        result_df = pd.DataFrame({
            "Variable": X.columns,
            "Importance": importances,
            "Decision": ["Confirmed" if imp > np.median(importances) else "Tentative" for imp in importances]
        }).sort_values("Importance", ascending=False)
    else:
        if is_classifier:
            rf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=seed, n_jobs=-1)
        else:
            rf = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=seed, n_jobs=-1)
        boruta = BorutaPy(rf, n_estimators='auto', max_iter=max_runs, alpha=p_value, random_state=seed)
        boruta.fit(X.values, y.values)
        result_df = pd.DataFrame({
            "Variable": X.columns,
            "Importance": boruta.support_.astype(int) * 1.0 + boruta.support_weak_.astype(int) * 0.5,
            "Decision": ["Confirmed" if s else ("Tentative" if w else "Rejected") for s, w in zip(boruta.support_, boruta.support_weak_)]
        }).sort_values("Importance", ascending=False)
    # Chart: feature importance bar plot
    fig, ax = plt.subplots(figsize=(10, max(6, len(result_df)*0.35)))
    colors = result_df["Decision"].map({"Confirmed": COLOR_DOWN, "Tentative": COLOR_WARN, "Rejected": COLOR_UP})
    ax.barh(result_df["Variable"][::-1], result_df["Importance"][::-1], color=colors[::-1])
    ax.set_xlabel("Importance / Support")
    ax.set_title("Boruta 特征筛选结果")
    ax.set_yticklabels(result_df["Variable"][::-1], fontsize=8)
    chart1 = ChartData(title="Boruta特征重要性", data=encode_figure(fig, fmt), type=fmt)
    # Table
    table = TableData(
        title="Boruta特征筛选结果",
        headers=["Variable", "Importance", "Decision"],
        rows=result_df.values.tolist()
    )
    summary = f"Boruta特征筛选完成。共{X.shape[1]}个特征，Confirmed: {sum(result_df['Decision']=='Confirmed')}, Tentative: {sum(result_df['Decision']=='Tentative')}, Rejected: {sum(result_df['Decision']=='Rejected')}."
    return {"charts": [chart1], "tables": [table], "summary": summary}
