# -*- coding: utf-8 -*-
"""Bootstrap 内部验证 v2：每次重抽样后重新训练，输出乐观度校正 AUC。

旧版只对测试集预测概率重抽样、不重训模型，测不出过拟合，已废弃。
请求参数（request.params）：
- modelType: 模型 key（长短均可），默认 LR
- nBootstrap: 次数，默认 300
- group_variable: 分组列（患者 ID），有则按组重抽样
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.services.core.models import create_model, needs_scale, canonical_key
from app.services.core.preprocessing import encode_y
from app.services.core.validation import optimism_bootstrap
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, COLOR_UP, COLOR_DOWN, COLOR_WARN
from app.models.schemas import ChartData, TableData


def _fmt(v, digits=4):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return "-"


def run_bootstrap(request, fmt="svg"):
    params = request.params or {}
    seed = int(params.get("seed", request.seed))
    n_boot = int(params.get("nBootstrap", 300))
    model_type = params.get("modelType", "LR")
    group_var = params.get("group_variable") or None

    df = get_data_for_ml(
        request.dataset_id, request.y_variable, request.x_variables,
        request.is_survival, request.time_variable, request.filters,
        extra_cols=[group_var] if group_var else None,
    )
    X = df[list(request.x_variables)]
    y, _ = encode_y(df[request.y_variable], request.variable_types)
    if len(np.unique(y)) != 2:
        raise ValueError("Bootstrap 验证目前仅支持二分类结局")

    groups = None
    if group_var and group_var in df.columns:
        groups = df[group_var].astype(str).to_numpy()

    key = canonical_key(model_type)
    res = optimism_bootstrap(
        lambda: create_model(key, params.get("model_params", {}).get(key, {}), seed),
        needs_scale(key), X, y, groups, B=n_boot, seed=seed,
        variable_types=request.variable_types,
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].hist(res["test_auc_dist"], bins=30, color=COLOR_DOWN, edgecolor="white", alpha=0.85)
    axes[0].axvline(res["apparent_auc"], color=COLOR_UP, linestyle="--", label=f"Apparent={res['apparent_auc']:.3f}")
    axes[0].axvline(res["corrected_auc"], color=COLOR_WARN, linestyle="--", label=f"Corrected={res['corrected_auc']:.3f}")
    axes[0].set_xlabel("AUC"); axes[0].set_ylabel("Frequency")
    axes[0].set_title(f"Bootstrap 模型在全数据上的 AUC (n={res['n_boot']})")
    axes[0].legend()
    axes[1].hist(res["optimism_dist"], bins=30, color=COLOR_WARN, edgecolor="white", alpha=0.85)
    axes[1].axvline(res["mean_optimism"], color=COLOR_UP, linestyle="--", label=f"Mean={res['mean_optimism']:.4f}")
    axes[1].set_xlabel("Optimism (AUC_boot - AUC_full)")
    axes[1].set_ylabel("Frequency")
    axes[1].set_title("乐观度分布")
    axes[1].legend()
    plt.tight_layout()
    chart = ChartData(title="Bootstrap内部验证（重训练）", data=encode_figure(fig, fmt), type=fmt)

    table = TableData(
        title="Bootstrap 内部验证结果（每次重抽样重新训练模型）",
        headers=["指标", "数值"],
        rows=[
            ["模型", key],
            ["重抽样单位", f"按 {group_var} 分组" if res["grouped"] else "按样本"],
            ["重抽样方式", "有放回（重复抽中的单位保留重复样本）"],
            ["表观 AUC（全数据）", _fmt(res["apparent_auc"])],
            ["平均乐观度", _fmt(res["mean_optimism"])],
            ["乐观度校正 AUC", _fmt(res["corrected_auc"])],
            ["OOB AUC (95%CI)", f"{_fmt(res['oob_auc_mean'])} ({_fmt(res['oob_auc_ci_low'])}-{_fmt(res['oob_auc_ci_high'])})"],
            ["有效 Bootstrap 次数", res["n_boot"]],
        ],
    )
    summary = (
        f"Bootstrap 内部验证完成（{res['n_boot']}次，{'按患者分组' if res['grouped'] else '按样本'}有放回重抽样，"
        f"重复抽中的单位保留在训练集中，每次重新训练）。"
        f"{key} 表观AUC={_fmt(res['apparent_auc'])}，校正AUC={_fmt(res['corrected_auc'])}，"
        f"OOB AUC={_fmt(res['oob_auc_mean'])}。"
    )
    return {"charts": [chart], "tables": [table], "summary": summary}
