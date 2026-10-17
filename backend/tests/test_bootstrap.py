# -*- coding: utf-8 -*-
"""task-E2 回归测试：Bootstrap 必须是有放回抽样，重复样本保留在训练集中。

统计约定（与 validation.optimism_bootstrap 文档一致）：
- 抽样单位：有 groups 时为患者组，否则为单条样本；
- 每次有放回抽 n 个单位（n = 单位总数），重复抽中的单位/样本在训练集中保留重复；
- OOB = 原始数据中从未被抽中的样本（分组时即所属组未被抽中的样本）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from app.services.core import validation as validation_mod
from app.services.core.validation import optimism_bootstrap


class _RecordingModel:
    """记录每次 fit/predict_proba 的输入，内部用 LogisticRegression 完成预测。"""

    instances: list["_RecordingModel"] = []

    def __init__(self):
        self.fit_X = []
        self.predict_X = []
        self._model = LogisticRegression(max_iter=3000, random_state=123)
        type(self).instances.append(self)

    def fit(self, X, y):
        self.fit_X.append(np.asarray(X))
        self._model.fit(X, y)
        return self

    def predict_proba(self, X):
        self.predict_X.append(np.asarray(X))
        return self._model.predict_proba(X)


@pytest.fixture(autouse=True)
def _reset_recorder():
    _RecordingModel.instances = []
    yield
    _RecordingModel.instances = []


def _fake_make_pipeline(model_factory, scale, variable_types):
    return _RecordingModel()


def _ungrouped_data(n=120, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({
        "x1": rng.normal(size=n),
        "x2": rng.normal(size=n),
    })
    logit = 1.6 * X["x1"].to_numpy() + 0.8 * X["x2"].to_numpy()
    y = rng.binomial(1, 1.0 / (1.0 + np.exp(-logit)))
    return X, y


def _grouped_data(n_groups=20, seed=1):
    rng = np.random.default_rng(seed)
    # 各组样本数不同（5~10），这样“重复抽中的组保留重复”会直接反映在训练行数上
    sizes = 5 + (np.arange(n_groups) % 6)
    g_idx = np.repeat(np.arange(n_groups), sizes)
    n = len(g_idx)
    x1 = rng.normal(size=n)
    groups = np.array([f"P{i:02d}" for i in g_idx])
    logit = 1.4 * x1 + 0.1 * g_idx
    y = rng.binomial(1, 1.0 / (1.0 + np.exp(-logit)))
    X = pd.DataFrame({"x1": x1, "g_idx": g_idx})
    return X, y, groups


def _spy_default_rng(monkeypatch):
    """记录每次 rng.choice 的返回值（即 chosen 单位）。"""
    real_default_rng = np.random.default_rng
    chosen_records = []

    class _SpyRNG:
        def __init__(self, seed=None):
            self._rng = real_default_rng(seed)

        def choice(self, *args, **kwargs):
            out = self._rng.choice(*args, **kwargs)
            chosen_records.append(np.asarray(out))
            return out

    monkeypatch.setattr(validation_mod.np.random, "default_rng", _SpyRNG)
    return chosen_records


def test_no_group_trains_on_n_rows_every_bootstrap(monkeypatch):
    """验收①（无分组）：每次 fit 的训练集行数都等于 n，而不是去重后的约 0.63n。"""
    X, y = _ungrouped_data()
    monkeypatch.setattr(validation_mod, "make_pipeline", _fake_make_pipeline)

    res = optimism_bootstrap(
        lambda: LogisticRegression(max_iter=3000, random_state=123),
        scale=False, X=X, y=y, B=5, seed=11,
    )

    assert res["resampling"] == "with_replacement"
    assert res["n_boot"] == 5
    # 第一个实例是全样本拟合的 pipe_full，其余为每次 Bootstrap 重训练
    assert len(_RecordingModel.instances) == 6
    assert _RecordingModel.instances[0].fit_X[0].shape[0] == len(X)
    for inst in _RecordingModel.instances[1:]:
        assert len(inst.fit_X) == 1
        # 有放回抽样：每次训练行数必然等于原始 n（允许重复样本）
        assert inst.fit_X[0].shape[0] == len(X)
        # 若像旧实现那样用 np.isin 去重，行数会落到约 0.63n，这里明确排除
        assert inst.fit_X[0].shape[0] > 0.8 * len(X)


def test_grouped_fit_rows_equal_sum_of_chosen_group_sizes(monkeypatch):
    """验收①（有分组）：训练行数 = 被抽中单元的样本数之和（含重复抽中的组）。"""
    X, y, groups = _grouped_data()
    group_sizes = pd.Series(groups).value_counts().to_dict()
    chosen_records = _spy_default_rng(monkeypatch)
    monkeypatch.setattr(validation_mod, "make_pipeline", _fake_make_pipeline)

    res = optimism_bootstrap(
        lambda: LogisticRegression(max_iter=3000, random_state=123),
        scale=False, X=X, y=y, groups=groups, B=8, seed=21,
    )

    assert res["n_boot"] == 8
    assert len(chosen_records) == 8
    # 第一个实例是全样本拟合的 pipe_full
    assert len(_RecordingModel.instances) == 9
    for chosen, inst in zip(chosen_records, _RecordingModel.instances[1:]):
        expected = sum(group_sizes[u] for u in chosen)
        assert inst.fit_X[0].shape[0] == expected
        # 抽中的组（去重）恰好构成训练集的组集合
        train_group_idx = set(inst.fit_X[0][:, 1].astype(int).tolist())
        assert train_group_idx == {int(u[1:]) for u in chosen}


def test_grouped_oob_groups_are_never_chosen(monkeypatch):
    """验收②：有分组时，OOB 样本所属的组都不在 chosen 中。"""
    X, y, groups = _grouped_data()
    group_sizes = pd.Series(groups).value_counts().to_dict()
    chosen_records = _spy_default_rng(monkeypatch)
    monkeypatch.setattr(validation_mod, "make_pipeline", _fake_make_pipeline)

    optimism_bootstrap(
        lambda: LogisticRegression(max_iter=3000, random_state=123),
        scale=False, X=X, y=y, groups=groups, B=8, seed=33,
    )

    assert len(chosen_records) == 8
    assert len(_RecordingModel.instances) == 9
    n_oob_calls = 0
    for chosen, inst in zip(chosen_records, _RecordingModel.instances[1:]):
        # predict 调用顺序：训练集表观 → 原始全样本 → OOB（若 OOB 满足条件）
        assert len(inst.predict_X) in (2, 3)
        assert inst.predict_X[0].shape[0] == sum(group_sizes[u] for u in chosen)
        assert inst.predict_X[1].shape[0] == len(X)
        if len(inst.predict_X) == 3:
            n_oob_calls += 1
            oob_group_idx = set(inst.predict_X[2][:, 1].astype(int).tolist())
            chosen_group_idx = {int(u[1:]) for u in chosen}
            assert oob_group_idx, "OOB 集合不应为空"
            assert oob_group_idx.isdisjoint(chosen_group_idx)
            # OOB 恰为“所有组 - 被抽中的组”
            assert oob_group_idx == set(range(len(group_sizes))) - chosen_group_idx
    assert n_oob_calls >= 1, "固定种子下应至少产生一次有效 OOB 评估"


def test_demo_logistic_corrected_le_apparent_and_n_boot():
    """验收③：demo 数据 + logistic + B=50，corrected_auc ≤ apparent_auc，n_boot ≥ 45。"""
    data_path = Path(__file__).resolve().parents[1] / "data" / "demo.csv"
    df = pd.read_csv(data_path)
    features = ["年龄", "性别", "白细胞", "血红蛋白", "BMI", "吸烟"]
    X = df[features]
    y = df["结局Y1"].astype(int).to_numpy()

    res = optimism_bootstrap(
        lambda: LogisticRegression(C=1.0, max_iter=3000, random_state=123),
        scale=True, X=X, y=y, groups=None, B=50, seed=123,
    )

    assert res["n_boot"] >= 45
    assert res["corrected_auc"] <= res["apparent_auc"] + 1e-12
    assert res["resampling"] == "with_replacement"
    assert res["oob_auc_ci_low"] <= res["oob_auc_mean"] <= res["oob_auc_ci_high"]
