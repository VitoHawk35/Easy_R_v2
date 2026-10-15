import pandas as pd
import numpy as np
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData
from app.services.core.preprocessing import ClinicalPreprocessor
import matplotlib.pyplot as plt

try:
    from lifelines import CoxPHFitter
    HAS_LIFELINES = True
except Exception:
    HAS_LIFELINES = False

def run_cox(request, fmt="svg"):
    if not request.is_survival or not request.time_variable:
        raise ValueError("Cox回归需要生存数据，请设置Y变量和生存时间变量")
    overlap = set(request.x_variables) & {request.y_variable, request.time_variable}
    if overlap:
        raise ValueError(f"生存时间/事件变量不能同时作为特征变量: {', '.join(sorted(overlap))}")
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         True, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    # Cox需要完整的生存数据
    needed = list(dict.fromkeys([request.y_variable, request.time_variable] + list(request.x_variables)))
    df = df[needed].dropna()
    if len(df) == 0:
        raise ValueError("No valid data after removing missing values")
    # Prepare X and survival（生存时间/事件列不进预处理器，原样传给 lifelines）
    X_df = df[list(request.x_variables)]
    y = pd.to_numeric(df[request.y_variable], errors='coerce').fillna(0).astype(int)
    time = pd.to_numeric(df[request.time_variable], errors='coerce').astype(float)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    alpha = float(request.params.get("alpha", 0.0))
    penalizer = float(request.params.get("penalizer", 0.0))
    # Split
    np.random.seed(seed)
    idx = np.random.permutation(len(df))
    n_test = int(len(df) * test_size)
    train_idx, test_idx = idx[n_test:], idx[:n_test]
    # 预处理只在训练集 fit，防泄漏
    prep = ClinicalPreprocessor(request.variable_types).fit(X_df.iloc[train_idx])
    train_df = prep.transform(X_df.iloc[train_idx])
    train_df["time"] = time.iloc[train_idx].values
    train_df["event"] = y.iloc[train_idx].values
    if HAS_LIFELINES:
        cph = CoxPHFitter(penalizer=penalizer)
        cph.fit(train_df, duration_col="time", event_col="event")
        summary_df = cph.summary.copy()
        summary_df = summary_df.reset_index()
        summary_df.columns = [str(c) for c in summary_df.columns]
        # Hazard ratio plot
        hr = np.exp(summary_df["coef"].values)
        vars_names = summary_df["covariate"].values if "covariate" in summary_df.columns else summary_df.iloc[:, 0].values
        ci_low = np.exp(summary_df["coef lower 95%"].values) if "coef lower 95%" in summary_df.columns else hr * 0.8
        ci_high = np.exp(summary_df["coef upper 95%"].values) if "coef upper 95%" in summary_df.columns else hr * 1.2
        fig, ax = plt.subplots(figsize=(8, max(5, len(vars_names)*0.35)))
        y_pos = np.arange(len(vars_names))
        ax.errorbar(hr, y_pos, xerr=[hr - ci_low, ci_high - hr], fmt='o', color='#3498db', ecolor='gray', capsize=3)
        ax.axvline(1, color='r', linestyle='--')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(vars_names, fontsize=9)
        ax.set_xlabel("Hazard Ratio (HR)")
        ax.set_title("Cox Regression Hazard Ratios with 95% CI")
        ax.set_xscale('log')
        chart1 = ChartData(title="Cox回归HR", data=encode_figure(fig, fmt), type=fmt)
        headers = list(summary_df.columns)
        rows = summary_df.values.tolist()
        concordance = round(cph.concordance_index_, 4)
    else:
        raise ValueError("lifelines not installed, Cox regression unavailable")
    table = TableData(title="Cox回归结果", headers=headers, rows=rows)
    summary = f"Cox回归完成。Concordance Index={concordance}，事件数={int(y.sum())}/{len(y)}。"
    coef_dict = dict(zip(vars_names, summary_df["coef"].values)) if "coef" in summary_df.columns else {}
    model_info = {
        "model_type": "cox",
        "coefficients": coef_dict,
        "intercept": 0.0,
        "feature_names": list(vars_names),
    }
    return {"charts": [chart1], "tables": [table], "summary": summary, "model_info": model_info}
