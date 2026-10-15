# -*- coding: utf-8 -*-
"""多模型对比 v2：重复（分组）交叉验证 + OOF 汇总，取代旧版单次 train_test_split。

请求参数（request.params）新增：
- group_variable: 分组列（患者 ID）。存在时按组切分，防纵向泄漏
- repeats: 重复次数，默认 5
- cvFolds: 折数，默认 5
- models: 模型 key 列表（短标签或长 key 均可）
响应契约不变：charts / tables / summary。
"""
from __future__ import annotations

import traceback

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from app.services.core.metrics import (
    bootstrap_auc_ci,
    calibration_bins,
    dca_curve,
    hosmer_lemeshow,
    calibration_slope_intercept,
)
from app.services.core.models import COMPARE_DEFAULTS, create_model, needs_scale
from app.services.core.preprocessing import encode_y
from app.services.core.validation import run_repeated_cv
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure
from app.models.schemas import ChartData, TableData

MODEL_COLORS = {
    "LR": "#000000", "Lasso": "#555555", "ENet": "#888888",
    "DT": "#DC143C", "RF": "#8B4513", "SVM": "#006400", "KNN": "#4B0082",
    "GBDT": "#00BFFF", "XGB": "#1E90FF", "LGBM": "#32CD32", "CatBoost": "#FF8C00",
    "NB": "#9370DB", "MLP": "#FF1493", "TabPFN": "#008B8B", "LDA": "#2F4F4F", "QDA": "#D2691E",
}


def _fmt(v, digits=3):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return "-"


def run_compare(request, fmt="svg"):
    params = request.params or {}
    seed = int(params.get("seed", request.seed))
    repeats = max(2, int(params.get("repeats", 5)))
    cv_folds = int(params.get("cvFolds", params.get("cv", 5)))
    group_var = params.get("group_variable") or None
    selected = params.get("models", COMPARE_DEFAULTS)

    df = get_data_for_ml(
        request.dataset_id, request.y_variable, request.x_variables,
        request.is_survival, request.time_variable, request.filters,
        extra_cols=[group_var] if group_var else None,
    )
    X = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    if len(np.unique(y)) != 2:
        raise ValueError("多模型对比目前仅支持二分类结局")

    groups = None
    grouped = False
    if group_var and group_var in df.columns:
        groups = df[group_var].astype(str).to_numpy()
        grouped = True

    results = []
    curves = {}  # key -> 平均 OOF 概率
    for name in selected:
        try:
            from app.services.core.models import canonical_key
            key = canonical_key(name)
        except ValueError:
            results.append({"Model": name, "error": "未知模型"})
            continue
        try:
            res = run_repeated_cv(
                lambda: create_model(key, params.get("model_params", {}).get(key, {}), seed),
                needs_scale(key), X, y, groups,
                repeats=repeats, n_splits=cv_folds, seed=seed,
                variable_types=request.variable_types,
            )
            s = res["summary"]
            # 平均 OOF 上的校准指标 + bootstrap CI
            oof = res["oof_avg"]
            yy = res["y"]
            ci = bootstrap_auc_ci(yy, oof, seed=seed)
            hl, hl_p = hosmer_lemeshow(yy, oof)
            slope, intercept = calibration_slope_intercept(yy, oof)
            results.append({
                "Model": key,
                "auc_mean": s["auc_mean"], "auc_sd": s["auc_sd"],
                "auc_ci": f"{_fmt(s['auc_ci_low'])}-{_fmt(s['auc_ci_high'])}",
                "boot_ci": f"{_fmt(ci[0])}-{_fmt(ci[1])}" if ci[0] is not None else "-",
                "pr_auc": s.get("pr_auc_mean"), "brier": s.get("brier_mean"),
                "sens": s.get("sens_mean"), "spec": s.get("spec_mean"),
                "f1": s.get("f1_mean"), "acc": s.get("acc_mean"),
                "optimism": s.get("optimism_mean"),
                "hl_p": hl_p, "cal_slope": slope, "cal_intercept": intercept,
            })
            curves[key] = (yy, oof)
        except Exception as e:
            print(f"[COMPARE ERROR] Model={key}: {e}")
            traceback.print_exc()
            results.append({"Model": key, "error": str(e)[:80]})

    ok = [r for r in results if "error" not in r]
    if not ok:
        raise ValueError("所有模型均运行失败")

    # ---------- Chart 1: ROC（平均 OOF） ----------
    fig_roc, ax_roc = plt.subplots(figsize=(7, 7))
    for name, (yy, oof) in curves.items():
        from sklearn.metrics import roc_curve, roc_auc_score
        fpr, tpr, _ = roc_curve(yy, oof)
        ax_roc.plot(fpr, tpr, label=f"{name} AUC={roc_auc_score(yy, oof):.3f}",
                    color=MODEL_COLORS.get(name), linewidth=1.5)
    ax_roc.plot([0, 1], [0, 1], "k--", linewidth=0.8, alpha=0.5)
    ax_roc.set_xlim([-0.02, 1.02]); ax_roc.set_ylim([-0.02, 1.02])
    ax_roc.set_xlabel("1 - Specificity", fontsize=12)
    ax_roc.set_ylabel("Sensitivity", fontsize=12)
    ax_roc.set_title(f"ROC Curves (OOF, {repeats}×{cv_folds}-fold CV)", fontsize=13, fontweight="bold")
    ax_roc.legend(loc="lower right", fontsize=9, frameon=False)
    ax_roc.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    chart_roc = ChartData(title="多模型ROC曲线（OOF）", data=encode_figure(fig_roc, fmt), type=fmt)

    # ---------- Chart 2: 校准 + DCA ----------
    fig_cd, (ax_cal, ax_dca) = plt.subplots(1, 2, figsize=(14, 7))
    for name, (yy, oof) in curves.items():
        cb = calibration_bins(yy, oof)
        ax_cal.plot(cb["mean_pred"], cb["obs_rate"], "o-", color=MODEL_COLORS.get(name),
                    label=name, markersize=4, linewidth=1.2)
    ax_cal.plot([0, 1], [0, 1], "k--", linewidth=0.8, alpha=0.5)
    ax_cal.set_xlim([-0.02, 1.02]); ax_cal.set_ylim([-0.02, 1.02])
    ax_cal.set_xlabel("Predicted Probability", fontsize=11)
    ax_cal.set_ylabel("Observed Probability", fontsize=11)
    ax_cal.set_title("Calibration Curves (OOF)", fontsize=12, fontweight="bold")
    ax_cal.legend(loc="upper left", fontsize=8, frameon=False)
    ax_cal.set_aspect("equal", adjustable="box")

    thresholds = None
    for name, (yy, oof) in curves.items():
        dca = dca_curve(yy, oof)
        thresholds = dca["threshold"]
        ax_dca.plot(dca["threshold"], dca["nb_model"], color=MODEL_COLORS.get(name), label=name, linewidth=1.2)
    if thresholds is not None:
        yy0 = next(iter(curves.values()))[0]
        nb_all = yy0.mean() - (1 - yy0.mean()) * thresholds / (1 - thresholds)
        ax_dca.plot(thresholds, nb_all, "k--", linewidth=0.8, alpha=0.6, label="Treat All")
        ax_dca.axhline(0, color="k", ls=":", lw=0.8, alpha=0.6, label="Treat None")
    ax_dca.set_xlim([0, 1])
    ax_dca.set_xlabel("Threshold Probability", fontsize=11)
    ax_dca.set_ylabel("Net Benefit", fontsize=11)
    ax_dca.set_title("Decision Curve Analysis (OOF)", fontsize=12, fontweight="bold")
    ax_dca.legend(loc="upper right", fontsize=8, frameon=False)
    ax_dca.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    chart_cd = ChartData(title="多模型校准曲线与DCA（OOF）", data=encode_figure(fig_cd, fmt), type=fmt)

    # ---------- Chart 3: AUC 对比（误差棒） ----------
    ok_sorted = sorted(ok, key=lambda r: r["auc_mean"])
    fig_bar, ax_bar = plt.subplots(figsize=(10, 6))
    names = [r["Model"] for r in ok_sorted]
    aucs = [r["auc_mean"] for r in ok_sorted]
    sds = [r["auc_sd"] for r in ok_sorted]
    ax_bar.errorbar(aucs, np.arange(len(names)), xerr=sds, fmt="o", ms=5, capsize=3, color="#1E90FF")
    ax_bar.set_yticks(np.arange(len(names))); ax_bar.set_yticklabels(names, fontsize=9)
    ax_bar.set_xlabel(f"AUC-ROC (mean ± SD, {repeats} repeats)")
    ax_bar.set_title("Discrimination Comparison (OOF)", fontsize=12, fontweight="bold")
    plt.tight_layout()
    chart_bar = ChartData(title="多模型AUC对比（OOF）", data=encode_figure(fig_bar, fmt), type=fmt)

    # ---------- Table 1: 性能 ----------
    perf_headers = ["模型", "OOF AUC (mean±SD)", "重复间95%CI", "Bootstrap 95%CI",
                    "PR-AUC", "灵敏度", "特异度", "F1", "Brier", "训练-外检乐观度"]
    perf_rows = [[
        r["Model"],
        f"{_fmt(r['auc_mean'])}±{_fmt(r['auc_sd'])}",
        r["auc_ci"], r["boot_ci"],
        _fmt(r.get("pr_auc")), _fmt(r.get("sens")), _fmt(r.get("spec")),
        _fmt(r.get("f1")), _fmt(r.get("brier")), _fmt(r.get("optimism")),
    ] for r in sorted(ok, key=lambda r: -r["auc_mean"])]
    for r in results:
        if "error" in r:
            perf_rows.append([r["Model"], "运行失败", r["error"], "-", "-", "-", "-", "-", "-", "-"])
    table_perf = TableData(title="多模型性能比较（重复分组CV，OOF）", headers=perf_headers, rows=perf_rows)

    # ---------- Table 2: 校准 ----------
    calib_headers = ["模型", "Brier分数", "P值 (H-L检验)", "校准截距", "校准斜率"]
    calib_rows = [[
        r["Model"], _fmt(r.get("brier")), _fmt(r.get("hl_p")),
        _fmt(r.get("cal_intercept")), _fmt(r.get("cal_slope")),
    ] for r in ok]
    table_calib = TableData(title="多模型校准评价（平均OOF）", headers=calib_headers, rows=calib_rows)

    best = max(ok, key=lambda r: r["auc_mean"])
    group_txt = f"按 {group_var} 分组" if grouped else "未指定分组列（普通分层CV）"
    summary = (
        f"多模型对比完成（{group_txt}，{repeats}次×{cv_folds}折，OOF 汇总）。"
        f"最佳模型: {best['Model']}，AUC={_fmt(best['auc_mean'])}±{_fmt(best['auc_sd'])}，"
        f"乐观度={_fmt(best['optimism'])}。"
    )
    return {"charts": [chart_roc, chart_cd, chart_bar], "tables": [table_perf, table_calib], "summary": summary}
