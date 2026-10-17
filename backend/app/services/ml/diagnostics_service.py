import pandas as pd
import numpy as np
from statsmodels.stats.outliers_influence import variance_inflation_factor
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData, COLOR_UP, COLOR_DOWN
from app.services.core.preprocessing import ClinicalPreprocessor, encode_y
import matplotlib.pyplot as plt
import seaborn as sns

def run_vif(request, fmt="svg"):
    if not request.x_variables or len(request.x_variables) == 0:
        raise ValueError("请先选择至少一个特征变量(X)再进行VIF诊断")
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    # 全数据共线性诊断（无留出验证）：ClinicalPreprocessor 全数据 fit + transform
    X_df = df[list(request.x_variables)]
    prep = ClinicalPreprocessor(request.variable_types).fit(X_df)
    X = prep.transform(X_df)
    y, le = encode_y(df[request.y_variable], request.variable_types)
    if len(X.columns) == 0:
        raise ValueError("特征变量为空，无法计算VIF")
    vif_threshold = float(request.params.get("vifThreshold", 5.0))
    corr_threshold = float(request.params.get("corrThreshold", 0.7))
    auto_remove = request.params.get("autoRemove", True)
    # Compute VIF
    X_const = X.copy()
    X_const["_const"] = 1
    vif_data = []
    for i, col in enumerate(X.columns):
        try:
            vif_val = variance_inflation_factor(X_const.values, i)
        except Exception:
            vif_val = np.nan
        status = "正常" if vif_val < vif_threshold else "共线性"
        vif_data.append({"Variable": col, "VIF": round(vif_val, 3) if not np.isnan(vif_val) else "N/A", "Status": status})
    vif_df = pd.DataFrame(vif_data).sort_values("VIF", ascending=False)
    # Correlation matrix
    corr = X.corr()
    high_corr_pairs = []
    for i in range(len(corr.columns)):
        for j in range(i+1, len(corr.columns)):
            val = abs(corr.iloc[i, j])
            if val >= corr_threshold:
                high_corr_pairs.append({"Var1": corr.columns[i], "Var2": corr.columns[j], "Correlation": round(val, 3)})
    corr_df = pd.DataFrame(high_corr_pairs).sort_values("Correlation", ascending=False) if high_corr_pairs else pd.DataFrame(columns=["Var1", "Var2", "Correlation"])
    # Charts
    fig, axes = plt.subplots(2, 1, figsize=(10, 14))
    ax1, ax2 = axes
    # VIF bar
    colors = [COLOR_DOWN if (isinstance(v, (int, float)) and v < vif_threshold) else COLOR_UP for v in vif_df["VIF"]]
    ax1.barh(vif_df["Variable"][::-1], [v if isinstance(v, (int, float)) else 0 for v in vif_df["VIF"]][::-1], color=colors[::-1])
    ax1.axvline(vif_threshold, color=COLOR_UP, linestyle='--', label=f'VIF阈值={vif_threshold}')
    ax1.set_xlabel("VIF")
    ax1.set_title("VIF 共线性分析")
    ax1.legend()
    # Correlation heatmap
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax2, square=True,
                annot_kws={"size": 7}, cbar_kws={"shrink": 0.8})
    ax2.set_title("相关性矩阵")
    chart1 = ChartData(title="VIF与相关性诊断", data=encode_figure(fig, fmt), type=fmt)
    # Tables
    vif_table = TableData(title="VIF分析", headers=["Variable", "VIF", "Status"], rows=vif_df.values.tolist())
    corr_table = TableData(title="高相关性变量对", headers=["Var1", "Var2", "Correlation"],
                           rows=corr_df.values.tolist() if len(corr_df) > 0 else [["无", "", ""]])
    all_normal = all(isinstance(v, (int, float)) and v < vif_threshold for v in vif_df["VIF"])
    summary = f"VIF诊断完成。VIF阈值={vif_threshold}，相关系数阈值={corr_threshold}。{'所有变量VIF正常' if all_normal else '存在共线性变量'}。"
    result = {"charts": [chart1], "tables": [vif_table, corr_table], "summary": summary}
    if auto_remove and not all_normal:
        # Iteratively remove highest VIF
        removed = []
        X_new = X.copy()
        while True:
            X_const = X_new.copy()
            X_const["_const"] = 1
            vifs = []
            for i, col in enumerate(X_new.columns):
                try:
                    vifs.append(variance_inflation_factor(X_const.values, i))
                except Exception:
                    vifs.append(np.inf)
            if not vifs:
                break
            max_vif = max(vifs)
            if max_vif < vif_threshold:
                break
            remove_idx = vifs.index(max_vif)
            removed.append(X_new.columns[remove_idx])
            X_new = X_new.drop(columns=[X_new.columns[remove_idx]])
        result["removed_vars"] = removed
        # 同时放入 model_info，前端可统一从 model_info.removed_vars 读取（E4e）
        result["model_info"] = {"removed_vars": removed}
        result["summary"] += f" 自动移除了{len(removed)}个变量: {', '.join(removed)}。"
    else:
        result["removed_vars"] = []
    return result
