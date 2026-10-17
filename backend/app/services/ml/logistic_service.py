import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, ChartData, TableData, COLOR_UP, COLOR_DOWN, COLOR_MUTED
from app.services.core.preprocessing import ClinicalPreprocessor, encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt
import statsmodels.api as sm

def run_logistic(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    if len(np.unique(y)) > 10 or y.dtype == float:
        raise ValueError("Logistic regression supports classification only")
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    C = float(request.params.get("C", 1.0))
    penalty = request.params.get("penalty", "l2")
    solver = request.params.get("solver", "lbfgs")
    cv = int(request.params.get("cv", 5))
    standardize = request.params.get("standardize", True)
    model = LogisticRegression(C=C, penalty=penalty, solver=solver, random_state=seed, max_iter=2000, n_jobs=-1)
    # 防泄漏：预处理（填补/哑变量）随 Pipeline 只在训练集 fit；旧代码 stratify=y
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=standardize, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=True, variable_types=request.variable_types)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    y_pred = pipe.predict(X_test)
    y_prob = pipe.predict_proba(X_test)
    metrics = classification_metrics(y_test, y_pred, y_prob)
    # CV 对整条 Pipeline 做，预处理在每折内重新 fit
    cv_scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring='roc_auc')
    metrics["CV_AUC_mean"] = round(cv_scores.mean(), 4)
    metrics["CV_AUC_std"] = round(cv_scores.std(), 4)
    fitted = pipe.named_steps["clf"]
    coefs = fitted.coef_[0]
    coef_df = pd.DataFrame({
        "Variable": feature_names,
        "Coefficient": coefs,
        "OR": np.exp(coefs),
        "AbsCoef": np.abs(coefs)
    }).sort_values("AbsCoef", ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    ax1, ax2 = axes
    # Forest plot style
    sorted_coef = coef_df.sort_values("Coefficient")
    colors = [COLOR_UP if c > 0 else COLOR_DOWN for c in sorted_coef["Coefficient"]]
    ax1.barh(sorted_coef["Variable"], sorted_coef["Coefficient"], color=colors)
    ax1.axvline(0, color=COLOR_MUTED, linestyle='--')
    ax1.set_xlabel("Coefficient (log OR)")
    ax1.set_title("Logistic 回归系数")
    # OR plot
    or_vals = sorted_coef["OR"].values
    or_vars = sorted_coef["Variable"].values
    ax2.scatter(or_vals, range(len(or_vals)), color=COLOR_DOWN, s=60)
    ax2.axvline(1, color=COLOR_MUTED, linestyle='--')
    ax2.set_yticks(range(len(or_vals)))
    ax2.set_yticklabels(or_vars, fontsize=8)
    ax2.set_xlabel("Odds Ratio (OR)")
    ax2.set_title("比值比（OR）图")
    ax2.set_xscale('log')
    chart1 = ChartData(title="Logistic回归结果", data=encode_figure(fig, fmt), type=fmt)
    table = TableData(title="回归系数与OR", headers=["Variable", "Coefficient", "OR"],
                      rows=coef_df[["Variable", "Coefficient", "OR"]].values.tolist())
    metrics_table = TableData(title="评估指标", headers=["Metric", "Value"],
                              rows=[[k, v] for k, v in metrics.items()])
    summary = f"Logistic回归完成。C={C}, penalty={penalty}, CV_AUC={metrics['CV_AUC_mean']:.4f}。"
    return {
        "charts": [chart1], "tables": [table, metrics_table], "summary": summary,
        "model_info": {
            "model_type": "logistic",
            "coefficients": dict(zip(feature_names, [round(float(c), 6) for c in coefs])),
            "intercept": round(float(fitted.intercept_[0]), 6),
            "feature_names": feature_names,
        }
    }


def run_logistic_screening(request, fmt="svg"):
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    # 筛选类函数无留出验证，不存在泄漏；改用 ClinicalPreprocessor 保证编码一致
    X_df = df[list(request.x_variables)]
    prep = ClinicalPreprocessor(request.variable_types).fit(X_df)
    X = prep.transform(X_df)
    y, le = encode_y(df[request.y_variable], request.variable_types)
    classes = np.unique(y)
    if len(classes) != 2:
        raise ValueError("Logistic单因素筛选仅支持二分类响应变量")
    y_binary = pd.Series(y, index=X.index).map({classes[0]: 0, classes[1]: 1}).astype(int)

    p_threshold = float(request.params.get("pValue", request.params.get("p", 0.05)))
    rows = []
    for col in X.columns:
        x = pd.to_numeric(X[col], errors='coerce').fillna(0).astype(float)
        row = {
            "Variable": col,
            "Coefficient": np.nan,
            "OR": np.nan,
            "CI95_Lower": np.nan,
            "CI95_Upper": np.nan,
            "PValue": np.nan,
            "Selected": False,
            "Status": "OK",
        }
        if x.nunique(dropna=False) <= 1:
            row["Status"] = "Constant"
            rows.append(row)
            continue
        try:
            x_design = sm.add_constant(x, has_constant='add')
            fit = sm.Logit(y_binary, x_design).fit(disp=False, maxiter=200)
            coef = float(fit.params.iloc[1])
            p_value = float(fit.pvalues.iloc[1])
            ci_low, ci_high = fit.conf_int().iloc[1]
            row.update({
                "Coefficient": coef,
                "OR": float(np.exp(coef)),
                "CI95_Lower": float(np.exp(ci_low)),
                "CI95_Upper": float(np.exp(ci_high)),
                "PValue": p_value,
                "Selected": bool(p_value <= p_threshold),
            })
        except Exception:
            row["Status"] = "FitFailed"
        rows.append(row)

    result_df = pd.DataFrame(rows)
    result_df["SortP"] = pd.to_numeric(result_df["PValue"], errors='coerce').fillna(np.inf)
    result_df = result_df.sort_values(["Selected", "SortP"], ascending=[False, True]).drop(columns=["SortP"])

    plot_df = result_df[(result_df["Status"] == "OK") & result_df["OR"].notna()].head(25).copy()
    fig, ax = plt.subplots(figsize=(8, max(4, len(plot_df) * 0.35)))
    if len(plot_df) > 0:
        y_pos = np.arange(len(plot_df))
        or_vals = plot_df["OR"].values.astype(float)
        ci_low = plot_df["CI95_Lower"].values.astype(float)
        ci_high = plot_df["CI95_Upper"].values.astype(float)
        ax.errorbar(or_vals, y_pos, xerr=[or_vals - ci_low, ci_high - or_vals], fmt='o', color=COLOR_DOWN, ecolor=COLOR_MUTED, capsize=3)
        ax.axvline(1, color=COLOR_UP, linestyle='--')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(plot_df["Variable"], fontsize=8)
        ax.set_xscale('log')
        ax.set_xlabel("Odds Ratio (95% CI)")
    else:
        ax.text(0.5, 0.5, "No valid variables", ha='center', va='center')
        ax.set_axis_off()
    ax.set_title("Logistic 单因素筛选")
    chart = ChartData(title="Logistic单因素筛选OR森林图", data=encode_figure(fig, fmt), type=fmt)

    headers = ["Variable", "Coefficient", "OR", "CI95_Lower", "CI95_Upper", "PValue", "Selected", "Status"]
    output_df = result_df.copy()
    for col in ["Coefficient", "OR", "CI95_Lower", "CI95_Upper", "PValue"]:
        output_df[col] = output_df[col].apply(lambda v: None if pd.isna(v) else round(float(v), 6))
    table = TableData(title="Logistic单因素筛选结果", headers=headers, rows=output_df[headers].values.tolist())
    selected_count = int(result_df["Selected"].sum())
    failed_count = int((result_df["Status"] != "OK").sum())
    summary = f"Logistic单因素筛选完成。P值阈值={p_threshold}，共筛选{len(result_df)}个变量，入选{selected_count}个，跳过/失败{failed_count}个。"
    model_info = {
        "model_type": "logistic-screening",
        "feature_names": result_df.loc[result_df["Selected"], "Variable"].tolist(),
        "p_threshold": p_threshold,
    }
    return {"charts": [chart], "tables": [table], "summary": summary, "model_info": model_info}
