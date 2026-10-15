# -*- coding: utf-8 -*-
"""评价指标：与"临床模型工作流模板"同源实现。

区分度（AUC/PR-AUC/最佳界值下灵敏度特异度F1）、校准度（Brier/H-L/校准斜率截距）、
临床效用（DCA 净获益）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    roc_auc_score,
    roc_curve,
)


def calibration_bins(y, p, n_bins=10) -> pd.DataFrame:
    d = pd.DataFrame({"y": y, "p": p})
    try:
        d["bin"] = pd.qcut(d["p"], n_bins, duplicates="drop")
    except ValueError:
        d["bin"] = pd.cut(d["p"], n_bins, include_lowest=True)
    g = d.groupby("bin", observed=True).agg(n=("y", "size"), mean_pred=("p", "mean"), obs_rate=("y", "mean"))
    return g[g["n"] >= 5]


def hosmer_lemeshow(y, p, n_bins=10):
    d = pd.DataFrame({"y": y, "p": p})
    try:
        d["bin"] = pd.qcut(d["p"], n_bins, duplicates="drop")
    except ValueError:
        d["bin"] = pd.cut(d["p"], n_bins, include_lowest=True)
    g = d.groupby("bin", observed=True).agg(n=("y", "size"), mean_pred=("p", "mean"), obs_rate=("y", "mean"))
    g = g[g["n"] >= 5]
    if len(g) < 3:
        return np.nan, np.nan
    exp = g["mean_pred"] * g["n"]
    obs = g["obs_rate"] * g["n"]
    denom = np.maximum(exp * (1 - g["mean_pred"]), 1e-8)
    hl = float(((obs - exp) ** 2 / denom).sum())
    return hl, float(stats.chi2.sf(hl, max(1, len(g) - 2)))


def calibration_slope_intercept(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    x = np.log(p / (1 - p)).reshape(-1, 1)
    try:
        m = LogisticRegression(max_iter=1000).fit(x, y)
        return float(m.coef_[0][0]), float(m.intercept_[0])
    except Exception:
        return np.nan, np.nan


def dca_curve(y, p, thresholds=None) -> pd.DataFrame:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    thr = np.arange(0.01, 0.99, 0.01) if thresholds is None else thresholds
    n = len(y)
    nb_model = np.zeros_like(thr, dtype=float)
    for i, t in enumerate(thr):
        pred = p >= t
        tp = int((pred & (y == 1)).sum())
        fp = int((pred & (y == 0)).sum())
        nb_model[i] = tp / n - fp / n * t / (1 - t)
    nb_all = y.mean() - (1 - y.mean()) * thr / (1 - thr)
    return pd.DataFrame({"threshold": thr, "nb_model": nb_model, "nb_all": nb_all, "nb_none": 0.0})


def classification_oof_metrics(y, p) -> dict:
    """在 OOF 预测上计算全套指标（模板 compute_repeat_metrics 的 Web 版）。"""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    auc = float(roc_auc_score(y, p))
    pr_auc = float(average_precision_score(y, p))
    brier = float(brier_score_loss(y, p))
    ll = float(log_loss(y, np.clip(p, 1e-7, 1 - 1e-7), labels=[0, 1]))
    fpr, tpr, thr = roc_curve(y, p)
    youden = float(thr[int(np.argmax(tpr - fpr))])
    pred = (p >= youden).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    sens = tp / max(tp + fn, 1)
    spec = tn / max(tn + fp, 1)
    hl, hl_p = hosmer_lemeshow(y, p)
    slope, intercept = calibration_slope_intercept(y, p)
    dca = dca_curve(y, p)
    return {
        "n": len(y),
        "auc": auc, "pr_auc": pr_auc, "brier": brier, "logloss": ll,
        "youden": youden, "sens": float(sens), "spec": float(spec),
        "acc": float((tp + tn) / len(y)), "f1": float(f1_score(y, pred)),
        "ppv": float(tp / max(tp + fp, 1)), "npv": float(tn / max(tn + fn, 1)),
        "hl": hl, "hl_p": hl_p, "cal_slope": slope, "cal_intercept": intercept,
        "dca_max_nb": float(dca["nb_model"].max()),
    }


def summarize_repeats(records: list[dict]) -> dict:
    """多次重复 CV 的指标 → mean / sd / 95%CI（重复间）。"""
    d = pd.DataFrame(records)
    out = {}
    for c in d.columns:
        if c == "repeat":
            continue
        vals = pd.to_numeric(d[c], errors="coerce").dropna()
        if len(vals) == 0:
            continue
        out[f"{c}_mean"] = float(vals.mean())
        out[f"{c}_sd"] = float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
        out[f"{c}_ci_low"] = float(vals.mean() - 1.96 * vals.std(ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else float(vals.mean())
        out[f"{c}_ci_high"] = float(vals.mean() + 1.96 * vals.std(ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else float(vals.mean())
    out["repeats_used"] = len(records)
    return out


def bootstrap_auc_ci(y_true, y_prob, n_boot=1000, seed=42):
    """对固定预测概率做 bootstrap，估 AUC 的 95%CI（不重新训练）。"""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    rng = np.random.RandomState(seed)
    aucs = []
    for _ in range(n_boot):
        idx = rng.randint(0, len(y_true), len(y_true))
        if len(np.unique(y_true[idx])) < 2:
            continue
        try:
            aucs.append(roc_auc_score(y_true[idx], y_prob[idx]))
        except Exception:
            pass
    if len(aucs) < 100:
        return None, None
    return float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))
