# -*- coding: utf-8 -*-
"""E3a：Web 计算器与列线图的原始尺度预测服务。

约定：
- 模型只在训练集（testSize=0.3，与 Step4 相同种子）上拟合 Pipeline：
  ClinicalPreprocessor（中位数/哑变量）→ StandardScaler（standardize=True）→ 线性模型；
- 同一个（数据集, 结局, 特征, 参数, seed）的 Pipeline 在进程内 LRU 缓存（maxsize=16）；
- 列线图/计算器使用原始尺度系数：
      β_raw = β_scaled / σ，b0_raw = b0 − Σ β_scaled·μ/σ
  哑变量也是预处理后的 0/1 列，按同一公式还原，保证 sigmoid(lp_raw) 与
  pipe.predict_proba 数值一致；
- 仅支持 logistic / lasso / elastic-net（其余模型前端隐藏计算器）。
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, SGDClassifier

from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
from app.services.data_service import get_data_for_ml

SUPPORTED_MODELS = ("logistic", "lasso", "lasso-predict", "elastic-net")


def canonical_linear_model(model_type: str) -> str:
    key = str(model_type or "logistic").strip().lower()
    if key == "lasso":
        key = "lasso-predict"
    if key not in SUPPORTED_MODELS:
        raise ValueError(f"Web计算器/列线图仅支持 logistic、lasso、elastic-net，收到: {model_type}")
    return key


def resolve_model_params(params: dict, model_type: str) -> dict:
    """从 request.params 中取出该模型的参数（兼容 E4 的 modelParams 嵌套结构）。"""
    params = params or {}
    per_model = params.get("model_params") or params.get("modelParams") or {}
    if isinstance(per_model, dict):
        for candidate in (model_type, canonical_linear_model(model_type), "LR" if model_type == "logistic" else model_type):
            value = per_model.get(candidate)
            if isinstance(value, dict):
                return dict(value)
    ignored = {"input", "modelParams", "model_params", "format", "testSize",
               "modelType", "evalDataset", "threshold"}
    return {k: v for k, v in params.items() if k not in ignored}


def _make_linear_model(model_type: str, params: dict, seed: int):
    key = canonical_linear_model(model_type)
    p = params or {}
    if key == "logistic":
        return LogisticRegression(
            C=float(p.get("C", 1.0)),
            penalty=p.get("penalty", "l2"),
            solver=p.get("solver", "lbfgs"),
            random_state=seed, max_iter=2000, n_jobs=-1)
    if key == "lasso-predict":
        alpha = float(p.get("alpha", 0.1))
        return LogisticRegression(
            penalty="l1", C=1.0 / max(alpha, 1e-6), solver="saga",
            max_iter=5000, random_state=seed)
    alpha = float(p.get("alpha", 0.1))
    l1_ratio = float(p.get("l1Ratio", 0.5))
    return SGDClassifier(
        loss="log_loss", penalty="elasticnet", alpha=alpha,
        l1_ratio=l1_ratio, max_iter=5000, random_state=seed)


def _raw_coefficients(pipe) -> tuple[dict, float]:
    """把标准化空间的系数还原到原始设计矩阵尺度。"""
    prep = pipe.named_steps["prep"]
    names = list(prep.get_feature_names_out())
    clf = pipe.named_steps["clf"]
    beta = np.asarray(clf.coef_[0], dtype=float)
    b0 = float(np.ravel(clf.intercept_)[0])
    if "scale" in pipe.named_steps:
        scaler = pipe.named_steps["scale"]
        mu = np.asarray(scaler.mean_, dtype=float)
        sigma = np.asarray(scaler.scale_, dtype=float)
        beta_raw = beta / sigma
        b0_raw = b0 - float(np.sum(beta * mu / sigma))
    else:
        beta_raw = beta
        b0_raw = b0
    return dict(zip(names, beta_raw.tolist())), b0_raw


def _variable_spec(x_variables, variable_types, X_df):
    """给前端计算器用的原始变量定义：连续变量给 min/max，分类变量给水平。"""
    spec = []
    for col in x_variables:
        vt = variable_types.get(col)
        vt = getattr(vt, "value", vt)
        s = X_df[col]
        is_cat = vt in ("categorical", "logical") or (
            vt is None and (s.dtype == object or str(s.dtype) == "category" or s.dtype == bool))
        if is_cat:
            levels = sorted(set(s.dropna().astype(str).unique()))
            spec.append({"name": col, "kind": "categorical", "levels": levels})
        else:
            num = pd.to_numeric(s, errors="coerce").dropna()
            spec.append({
                "name": col, "kind": "continuous",
                "min": float(num.min()) if len(num) else None,
                "max": float(num.max()) if len(num) else None,
                "median": float(num.median()) if len(num) else None,
            })
    return spec


@lru_cache(maxsize=16)
def _fit_cached(dataset_id: str, y_variable: str, x_variables: tuple,
                is_survival: bool, time_variable: str, filters_json: str,
                variable_types_json: str, model_type: str, params_json: str,
                seed: int):
    filters = json.loads(filters_json) if filters_json else []
    variable_types = json.loads(variable_types_json) if variable_types_json else {}
    params = json.loads(params_json) if params_json else {}
    key = canonical_linear_model(model_type)

    df = get_data_for_ml(dataset_id, y_variable, list(x_variables),
                         is_survival, time_variable or None, filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(x_variables)]
    y, _ = encode_y(df[y_variable], variable_types)
    if len(np.unique(y)) != 2:
        raise ValueError("Web计算器/列线图仅支持二分类结局")

    model = _make_linear_model(key, params, seed)
    scale = bool(params.get("standardize", True))
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=scale, X=X_df, y=y, test_size=0.3, seed=seed,
        stratify=True, variable_types=variable_types)

    coefs_raw, b0_raw = _raw_coefficients(pipe)
    prep = pipe.named_steps["prep"]
    X_design = prep.transform(X_df)
    feature_names = list(prep.get_feature_names_out())
    ranges = {c: (float(X_design[c].min()), float(X_design[c].max())) for c in feature_names}

    return {
        "pipe": pipe,
        "prep": prep,
        "model_type": key,
        "feature_names": feature_names,
        "coefficients_raw": coefs_raw,
        "intercept_raw": b0_raw,
        "ranges": ranges,
        "x_variables": list(x_variables),
        "variable_types": variable_types,
        "features": _variable_spec(list(x_variables), variable_types, X_df),
        "n_train": int(len(X_train)),
    }


def fit_context(request):
    """按请求拟合（或取缓存）线性 Pipeline，返回原始尺度上下文。"""
    params = request.params or {}
    model_type = canonical_linear_model(params.get("modelType", "logistic"))
    model_params = resolve_model_params(params, model_type)
    seed = int(params.get("seed", request.seed))
    variable_types = {k: getattr(v, "value", v) for k, v in (request.variable_types or {}).items()}
    return _fit_cached(
        request.dataset_id,
        request.y_variable,
        tuple(request.x_variables),
        bool(request.is_survival),
        request.time_variable or "",
        json.dumps(request.filters or [], sort_keys=True, default=str),
        json.dumps(variable_types, sort_keys=True, default=str),
        model_type,
        json.dumps(model_params, sort_keys=True, default=str),
        seed,
    )


def predict_one(ctx, patient_input: dict) -> dict:
    """对一位原始尺度患者预测：返回概率与原始尺度线性预测值。"""
    if not isinstance(patient_input, dict):
        raise ValueError("params.input 必须是对象（变量名 → 原始取值）")
    row = pd.DataFrame([{c: patient_input.get(c) for c in ctx["x_variables"]}])
    design = ctx["prep"].transform(row)
    x = np.asarray(design[ctx["feature_names"]].values, dtype=float)[0]
    beta = np.asarray([ctx["coefficients_raw"][c] for c in ctx["feature_names"]], dtype=float)
    lp = float(ctx["intercept_raw"] + np.dot(beta, x))
    probability = 1.0 / (1.0 + math.exp(-lp)) if lp >= 0 else math.exp(lp) / (1.0 + math.exp(lp))
    return {"probability": float(probability), "linear_predictor": lp}


def nomogram_context(request) -> dict:
    """列线图所需上下文：原始尺度 β/b0 + 各特征范围 + 前端变量定义。"""
    return fit_context(request)
