# -*- coding: utf-8 -*-
"""验证协议：重复（分组）交叉验证 + OOF，患者级乐观度校正 Bootstrap。

与模板一致的两条铁律：
1. 有分组列（患者 ID）时用 StratifiedGroupKFold —— 同一患者永不在训练/验证两侧；
2. Bootstrap 每次重抽样后【重新训练】模型 —— 只重抽预测值测不出过拟合。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.services.core.metrics import classification_oof_metrics, summarize_repeats
from app.services.core.preprocessing import ClinicalPreprocessor


def make_pipeline(model_factory, scale: bool, variable_types: dict | None) -> Pipeline:
    """每折一个全新 Pipeline：预处理随训练折重新 fit，防泄漏。"""
    steps = [("prep", ClinicalPreprocessor(variable_types))]
    if scale:
        steps.append(("scale", StandardScaler()))
    steps.append(("clf", model_factory()))
    return Pipeline(steps)


def _splitter(X, y, groups, n_splits, seed):
    if groups is not None:
        return StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X, y, groups)
    return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X, y)


def run_repeated_cv(model_factory, scale, X: pd.DataFrame, y, groups=None,
                    repeats=5, n_splits=5, seed=123, variable_types=None) -> dict:
    """重复分层（分组）CV。返回每次重复的 OOF 指标 + 跨重复平均 OOF 概率。"""
    y = np.asarray(y, dtype=int)
    X = X.reset_index(drop=True)
    if groups is not None:
        groups = pd.Series(groups).fillna("__NO_GROUP__").astype(str).to_numpy()

    records = []
    oof_acc = np.zeros(len(X))
    n_acc = 0
    for r in range(repeats):
        oof_p = np.zeros(len(X))
        train_aucs = []
        for tr, te in _splitter(X, y, groups, n_splits, seed + r):
            pipe = make_pipeline(model_factory, scale, variable_types)
            pipe.fit(X.iloc[tr], y[tr])
            oof_p[te] = pipe.predict_proba(X.iloc[te])[:, 1]
            if len(np.unique(y[tr])) == 2:
                train_aucs.append(roc_auc_score(y[tr], pipe.predict_proba(X.iloc[tr])[:, 1]))
        rec = classification_oof_metrics(y, oof_p)
        rec["train_auc"] = float(np.mean(train_aucs)) if train_aucs else np.nan
        rec["optimism"] = rec["train_auc"] - rec["auc"] if np.isfinite(rec["train_auc"]) else np.nan
        rec["repeat"] = r + 1
        records.append(rec)
        oof_acc += oof_p
        n_acc += 1
    oof_avg = oof_acc / max(n_acc, 1)
    return {
        "records": records,
        "summary": summarize_repeats(records),
        "oof_avg": oof_avg,
        "y": y,
    }


def optimism_bootstrap(model_factory, scale, X: pd.DataFrame, y, groups=None,
                       B=300, seed=7, variable_types=None,
                       progress_cb=None) -> dict:
    """乐观度校正 Bootstrap 内部验证（有放回抽样；有分组列时按患者整组重抽样）。

    统计约定：
    - 抽样单位：有 groups 时为患者组，否则为单条样本；每次有放回抽 n 个单位
      （n = 单位总数），重复抽中的单位/样本在训练集中**保留重复**。
    - 训练集：被抽中单位包含的全部原始样本（分组时组内样本一起进入训练集）。
    - OOB（out-of-bag）：原始数据中**从未被抽中**的样本（分组时即所属组未被抽中的样本）。
    - apparent AUC：全样本拟合模型在全样本上的 AUC；
      auc_boot：本次重抽样训练集上的表观 AUC；
      optimism = auc_boot - auc_test（auc_test 为本次模型在原始全样本上的 AUC）；
      corrected AUC = apparent AUC - mean(optimism)。
    - OOB AUC 用每次重抽样模型在未抽中样本上计算。

    返回 apparent / mean_optimism / corrected / OOB AUC 及分布。
    """
    y = np.asarray(y, dtype=int)
    X = X.reset_index(drop=True)
    if groups is not None:
        groups = pd.Series(groups).fillna("__NO_GROUP__").astype(str).to_numpy()
        units = np.unique(groups)
        pos_by_unit = {u: np.flatnonzero(groups == u) for u in units}
    else:
        units = np.arange(len(X))
        pos_by_unit = None

    pipe_full = make_pipeline(model_factory, scale, variable_types)
    pipe_full.fit(X, y)
    apparent = float(roc_auc_score(y, pipe_full.predict_proba(X)[:, 1]))

    rng = np.random.default_rng(seed)
    test_aucs, oob_aucs, optimisms = [], [], []
    for b in range(B):
        chosen = rng.choice(units, size=len(units), replace=True)
        if groups is not None:
            idx = np.concatenate([pos_by_unit[u] for u in chosen])
        else:
            idx = chosen
        oob = np.setdiff1d(np.arange(len(X)), idx)
        Xb, yb = X.iloc[idx], y[idx]
        if len(np.unique(yb)) < 2 or len(idx) < 10:
            continue
        pipe = make_pipeline(model_factory, scale, variable_types)
        try:
            pipe.fit(Xb, yb)
        except Exception:
            continue
        auc_boot = float(roc_auc_score(yb, pipe.predict_proba(Xb)[:, 1]))
        auc_test = float(roc_auc_score(y, pipe.predict_proba(X)[:, 1]))
        if len(oob) >= 10 and len(np.unique(y[oob])) == 2:
            oob_aucs.append(float(roc_auc_score(y[oob], pipe.predict_proba(X.iloc[oob])[:, 1])))
        optimisms.append(auc_boot - auc_test)
        test_aucs.append(auc_test)
        if progress_cb and (b + 1) % 50 == 0:
            progress_cb(b + 1, B)

    test_aucs = np.asarray(test_aucs)
    oob_aucs = np.asarray(oob_aucs) if oob_aucs else np.asarray([np.nan])
    mean_opt = float(np.mean(optimisms)) if optimisms else np.nan
    return {
        "apparent_auc": apparent,
        "mean_optimism": mean_opt,
        "corrected_auc": apparent - mean_opt if np.isfinite(mean_opt) else np.nan,
        "oob_auc_mean": float(np.nanmean(oob_aucs)),
        "oob_auc_ci_low": float(np.nanpercentile(oob_aucs, 2.5)),
        "oob_auc_ci_high": float(np.nanpercentile(oob_aucs, 97.5)),
        "n_boot": int(len(test_aucs)),
        "grouped": groups is not None,
        "resampling": "with_replacement",
        "test_auc_dist": test_aucs.tolist(),
        "optimism_dist": [float(v) for v in optimisms],
    }


def train_test_pipeline(model, scale: bool, X: pd.DataFrame, y,
                        test_size: float = 0.3, seed: int = 123,
                        stratify: bool = False, variable_types: dict | None = None):
    """单次划分 + Pipeline(预处理→[标准化]→模型)，预处理只在训练集 fit。

    供各单模型服务使用，替代旧的 prepare_xy（全数据 fillna/get_dummies 再划分，有泄漏）。
    返回 (fitted_pipeline, X_train, X_test, y_train, y_test)；
    特征名取 pipe.named_steps["prep"].get_feature_names_out()。
    """
    from sklearn.model_selection import train_test_split

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed,
        stratify=y if stratify else None)
    pipe = make_pipeline(lambda: model, scale, variable_types)
    pipe.fit(X_train, y_train)
    return pipe, X_train, X_test, y_train, y_test
