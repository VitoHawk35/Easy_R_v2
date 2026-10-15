import pandas as pd
import numpy as np
from sklearn.linear_model import ElasticNetCV, ElasticNet, LogisticRegressionCV, LogisticRegression
from sklearn.preprocessing import StandardScaler
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData
from app.services.core.preprocessing import ClinicalPreprocessor, encode_y
import matplotlib.pyplot as plt

def run_elastic_net(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    # 全数据上做 CV 选参/系数路径，无留出验证，不存在泄漏；改用 ClinicalPreprocessor 保证编码一致
    X_df = df[list(request.x_variables)]
    prep = ClinicalPreprocessor(request.variable_types).fit(X_df)
    X = prep.transform(X_df)
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    cv = int(request.params.get("cv", 5))
    standardize = request.params.get("standardize", True)
    l1_ratio = float(request.params.get("l1Ratio", 0.5))
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if standardize:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
    else:
        X_scaled = X
    if is_classifier:
        model = LogisticRegressionCV(Cs=20, cv=cv, penalty='elasticnet', solver='saga',
                                      l1_ratios=[l1_ratio], random_state=seed, max_iter=5000, n_jobs=-1)
    else:
        model = ElasticNetCV(l1_ratio=l1_ratio, cv=cv, random_state=seed, max_iter=5000, n_jobs=-1)
    model.fit(X_scaled, y)
    if is_classifier:
        best_C = model.C_[0]
        final_model = LogisticRegression(C=best_C, penalty='elasticnet', solver='saga', l1_ratio=l1_ratio,
                                          random_state=seed, max_iter=5000)
        alpha_str = f"C={best_C:.4f}"
    else:
        best_alpha = model.alpha_
        final_model = ElasticNet(alpha=best_alpha, l1_ratio=l1_ratio, random_state=seed, max_iter=5000)
        alpha_str = f"alpha={best_alpha:.4f}"
    final_model.fit(X_scaled, y)
    coefs = final_model.coef_
    if is_classifier and coefs.ndim > 1:
        coefs = coefs[0]
    coef_df = pd.DataFrame({
        "Variable": X.columns,
        "Coefficient": coefs,
        "AbsCoefficient": np.abs(coefs),
        "Selected": np.abs(coefs) > 1e-6
    }).sort_values("AbsCoefficient", ascending=False)
    fig, ax = plt.subplots(figsize=(8, max(5, len(coef_df)*0.35)))
    selected = coef_df[coef_df["Selected"]].sort_values("Coefficient")
    colors = ["#2ecc71" if c > 0 else "#e74c3c" for c in selected["Coefficient"]]
    ax.barh(selected["Variable"], selected["Coefficient"], color=colors)
    ax.set_xlabel("Coefficient")
    ax.set_title(f"Elastic Net Coefficients ({alpha_str}, l1_ratio={l1_ratio})")
    chart1 = ChartData(title="弹性网络系数", data=encode_figure(fig, fmt), type=fmt)
    table = TableData(title="Elastic Net系数表", headers=["Variable", "Coefficient", "Selected"],
                      rows=coef_df[["Variable", "Coefficient", "Selected"]].values.tolist())
    summary = f"弹性网络完成。{alpha_str}，l1_ratio={l1_ratio}，共选择{coef_df['Selected'].sum()}个变量。"
    intercept_val = float(final_model.intercept_)
    if is_classifier and hasattr(final_model, 'intercept_') and np.ndim(final_model.intercept_) > 0:
        intercept_val = float(final_model.intercept_[0])
    model_info = {
        "model_type": "elastic-net",
        "coefficients": dict(zip(X.columns, coefs)),
        "intercept": intercept_val,
        "feature_names": list(X.columns),
        "alpha": best_alpha if not is_classifier else best_C,
        "l1_ratio": l1_ratio,
    }
    return {"charts": [chart1], "tables": [table], "summary": summary, "model_info": model_info}
