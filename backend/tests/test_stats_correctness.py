# -*- coding: utf-8 -*-
"""task-E3 统计正确性（a–h）验收测试。"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit

from app.services.core.metrics import calibration_slope_intercept
from app.services.core.models import create_model
from app.services.data_service import get_data_for_ml, get_raw_data
from app.services.ml import eval_service
from app.services.ml.predict_service import fit_context, predict_one


BACKEND_DIR = Path(__file__).resolve().parents[1]
TYPES_TS = BACKEND_DIR.parent / "frontend" / "src" / "types" / "index.ts"

E3_X = ["年龄", "性别", "白细胞", "血红蛋白", "BMI", "吸烟", "教育程度"]


def _request(**overrides):
    req = SimpleNamespace(
        dataset_id="demo",
        y_variable="结局Y1",
        x_variables=list(E3_X),
        is_survival=False,
        time_variable=None,
        filters=[],
        params={"modelType": "logistic", "standardize": True},
        seed=123,
        variable_types={"结局Y1": "logical", "教育程度": "categorical"},
        wizard_snapshot={},
    )
    for k, v in overrides.items():
        setattr(req, k, v)
    return req


def _ml_payload(**overrides):
    payload = {
        "dataset_id": "demo",
        "y_variable": "结局Y1",
        "x_variables": list(E3_X),
        "filters": [],
        "seed": 123,
        "variable_types": {"结局Y1": "logical", "教育程度": "categorical"},
    }
    payload.update(overrides)
    return payload


# ---------------- E3a：计算器/列线图原始尺度 ----------------

def test_predict_api_matches_pipeline_within_1e9(client, auth_headers):
    req = _request()
    ctx = fit_context(req)
    df = get_data_for_ml(req.dataset_id, req.y_variable, req.x_variables)
    patients = df[list(req.x_variables)].head(20).to_dict(orient="records")
    pipe = ctx["pipe"]
    max_diff = 0.0
    for patient in patients:
        direct = float(pipe.predict_proba(pd.DataFrame([patient]))[0, 1])
        page = client.post(
            "/api/ml/predict",
            json=_ml_payload(params={"modelType": "logistic", "standardize": True, "input": patient}),
            headers=auth_headers,
        )
        assert page.status_code == 200, page.text
        max_diff = max(max_diff, abs(page.json()["probability"] - direct))
    assert max_diff < 1e-9


@pytest.mark.parametrize("model_type,extra", [
    ("logistic", {}),
    ("lasso", {"alpha": 0.01}),
    ("elastic-net", {"alpha": 0.01, "l1Ratio": 0.5}),
])
def test_nomogram_raw_coefficients_match_pipeline(model_type, extra):
    req = _request(params={"modelType": model_type, "standardize": True, **extra})
    ctx = fit_context(req)
    df = get_data_for_ml(req.dataset_id, req.y_variable, req.x_variables)
    X_df = df[list(req.x_variables)]
    design = ctx["prep"].transform(X_df)[ctx["feature_names"]].to_numpy(float)
    beta = np.array([ctx["coefficients_raw"][c] for c in ctx["feature_names"]], float)
    lp_raw = ctx["intercept_raw"] + design @ beta
    p_raw = expit(lp_raw)
    p_direct = ctx["pipe"].predict_proba(X_df)[:, 1]
    assert np.max(np.abs(p_raw - p_direct)) < 1e-6


def test_nomogram_endpoint_returns_raw_scale_info(client, auth_headers):
    resp = client.post(
        "/api/ml/nomogram",
        json=_ml_payload(params={"modelType": "logistic", "standardize": True}),
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    info = resp.json()["model_info"]
    assert info["raw_scale"] is True
    assert info["features"] and info["features"][0]["name"] in E3_X
    edu = next(f for f in info["features"] if f["name"] == "教育程度")
    assert edu["kind"] == "categorical" and len(edu["levels"]) >= 2


def test_categorical_change_changes_probability():
    req = _request()
    ctx = fit_context(req)
    df = get_data_for_ml(req.dataset_id, req.y_variable, req.x_variables)
    levels = sorted(df["教育程度"].dropna().astype(str).unique())
    assert len(levels) >= 2
    base = df[list(req.x_variables)].median(numeric_only=True).to_dict()
    base["教育程度"] = levels[0]
    base["性别"] = float(base.get("性别", 0))
    probs = []
    for lv in levels:
        patient = dict(base, 教育程度=lv)
        probs.append(predict_one(ctx, patient)["probability"])
    assert max(probs) - min(probs) > 1e-12


# ---------------- E3b：校准斜率/CITL ----------------

def test_calibration_slope_unpenalized():
    rng = np.random.default_rng(2026)
    n = 5000
    logit_p = rng.normal(0, 1.5, n)
    p = expit(logit_p)
    y = rng.binomial(1, expit(0.6 * logit_p))
    slope, citl = calibration_slope_intercept(y, p)
    assert abs(slope - 0.6) <= 0.08, slope
    assert np.isfinite(citl)


def test_calibration_perfect_data_slope1_citl0():
    rng = np.random.default_rng(7)
    n = 5000
    p = rng.uniform(0.05, 0.95, n)
    y = rng.binomial(1, p)
    slope, citl = calibration_slope_intercept(y, p)
    assert abs(slope - 1.0) <= 0.1, slope
    assert abs(citl) <= 0.1, citl


# ---------------- E3c/E3d：参数名与 CatBoost eval_set ----------------

def _registry_params(key: str) -> set[str]:
    text = TYPES_TS.read_text(encoding="utf-8")
    start = text.index(f"key: '{key}'")
    nxt = text.find("key: '", start + 1)
    region = text[start:] if nxt == -1 else text[start:nxt]
    return set(re.findall(r"name:\s*'([^']+)'", region))


def test_registry_param_names():
    cat = _registry_params("catboost")
    assert "learningRate" in cat
    assert "learning_rate" not in cat
    dt = _registry_params("decision-tree")
    assert {"minSamplesSplit", "minSamplesLeaf"} <= dt


def test_decision_tree_factory_reads_both_params():
    model = create_model("decision-tree", {"minSamplesSplit": 11, "minSamplesLeaf": 3}, seed=1)
    assert model.min_samples_split == 11
    assert model.min_samples_leaf == 3


def test_catboost_fit_never_uses_test_as_eval_set(client, auth_headers, monkeypatch):
    from app.services.ml import catboost_service

    calls = []
    real_cls = catboost_service.CatBoostClassifier

    class RecordingCatBoost(real_cls):
        def fit(self, X, y=None, **kwargs):
            calls.append(dict(kwargs))
            return super().fit(X, y, **kwargs)

    monkeypatch.setattr(catboost_service, "CatBoostClassifier", RecordingCatBoost)
    resp = client.post(
        "/api/ml/catboost",
        json=_ml_payload(params={"modelType": "catboost", "iterations": 20,
                                 "learningRate": 0.1, "testSize": 0.3}),
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert calls, "CatBoost.fit 未被调用"
    assert all("eval_set" not in kwargs for kwargs in calls)


# ---------------- E3e：缺失值诊断 ----------------

def test_missing_diagnostics_counts_raw_missing(client, auth_headers):
    resp = client.post(
        "/api/diagnostics/missing",
        json=_ml_payload(x_variables=["年龄", "中性粒细胞"]),
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()["tables"][0]["rows"]
    row = next(r for r in rows if r[0] == "中性粒细胞")
    assert row[1] > 0


# ---------------- E3f：只删结局缺失，X 缺失交由 Pipeline ----------------

def test_x_missing_rows_are_kept():
    raw = get_raw_data("demo", ["结局Y1", "年龄", "中性粒细胞"])
    ml = get_data_for_ml("demo", "结局Y1", ["年龄", "中性粒细胞"])
    assert len(ml) == len(raw.dropna(subset=["结局Y1"]))
    assert ml["中性粒细胞"].isna().sum() > 0


def test_ml_summary_documents_missing_policy(client, auth_headers):
    resp = client.post(
        "/api/ml/logistic",
        json=_ml_payload(x_variables=["年龄", "白细胞", "中性粒细胞"]),
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()["summary"]
    assert "删除了" in summary and "中位数" in summary


# ---------------- E3g：模型 key 不静默替换 / SHAP 概率 ----------------

def test_eval_svm_builds_svc(client, auth_headers, monkeypatch):
    from sklearn.svm import SVC

    built = []
    real_create = eval_service.create_model

    def recording_create(model_type, params=None, seed=123):
        model = real_create(model_type, params, seed)
        built.append(model)
        return model

    monkeypatch.setattr(eval_service, "create_model", recording_create)
    resp = client.post(
        "/api/ml/calibration",
        json=_ml_payload(params={"modelType": "svm", "testSize": 0.3}),
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert built and isinstance(built[0], SVC)


def test_eval_unknown_model_returns_422(client, auth_headers):
    resp = client.post(
        "/api/ml/calibration",
        json=_ml_payload(params={"modelType": "foo", "testSize": 0.3}),
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text


def test_shap_predict_function_uses_probability_for_classifier():
    from sklearn.linear_model import LogisticRegression
    from app.services.ml.explain_service import _predict_function

    model = LogisticRegression().fit([[0], [1], [2], [3]], [0, 1, 0, 1])
    preds = _predict_function(model, is_classifier=True)(pd.DataFrame({"x": [0.5, 2.5]}).values)
    assert np.all((preds >= 0) & (preds <= 1))


# ---------------- E3h：评估参数生效 ----------------

def _eval_row(response, dataset_label):
    table = next(t for t in response.json()["tables"] if t["title"] == "评估指标（按评估数据集）")
    return next(r for r in table["rows"] if r[0] == dataset_label)


def test_eval_dataset_train_and_both(client, auth_headers):
    train_resp = client.post(
        "/api/ml/calibration",
        json=_ml_payload(params={"modelType": "logistic", "testSize": 0.3,
                                 "evalDataset": "train", "threshold": 0.5}),
        headers=auth_headers,
    )
    assert train_resp.status_code == 200, train_resp.text
    labels = [r[0] for r in next(t for t in train_resp.json()["tables"]
                                 if t["title"] == "评估指标（按评估数据集）")["rows"]]
    assert labels == ["训练集"]

    both_resp = client.post(
        "/api/ml/calibration",
        json=_ml_payload(params={"modelType": "logistic", "testSize": 0.3,
                                 "evalDataset": "both", "threshold": 0.5}),
        headers=auth_headers,
    )
    assert both_resp.status_code == 200, both_resp.text
    labels = [r[0] for r in next(t for t in both_resp.json()["tables"]
                                 if t["title"] == "评估指标（按评估数据集）")["rows"]]
    assert labels == ["训练集", "测试集"]


def test_eval_threshold_changes_sensitivity(client, auth_headers):
    sens = []
    for thr in (0.3, 0.7):
        resp = client.post(
            "/api/ml/calibration",
            json=_ml_payload(params={"modelType": "logistic", "testSize": 0.3,
                                     "evalDataset": "test", "threshold": thr}),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        sens.append(float(_eval_row(resp, "测试集")[5]))
    assert sens[0] != sens[1]
