# -*- coding: utf-8 -*-
"""防泄漏预处理：所有统计量（中位数、类别水平）只在训练折上学习。

旧版 utils.prepare_xy 在全数据上 fillna(mean) + get_dummies，再切训练/测试集，
会把验证集信息泄进预处理。ClinicalPreprocessor 作为 sklearn Transformer
放进 Pipeline 里，随每折重新 fit，杜绝该问题。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import LabelEncoder

MISSING_LEVEL = "__MISSING__"


class ClinicalPreprocessor(BaseEstimator, TransformerMixin):
    """连续变量：转数值 + 中位数填补；分类变量：哑变量展开（第一水平为参照）。

    fit 时记录每列类型、中位数、类别集合；transform 输出列固定的数值矩阵，
    外部验证/新数据出现的未见过类别自动归入参照水平（全 0）。
    """

    def __init__(self, variable_types=None):
        self.variable_types = variable_types or {}

    def _is_categorical(self, col: str, s: pd.Series) -> bool:
        vt = self.variable_types.get(col)
        vt = getattr(vt, "value", vt)  # 兼容 Enum
        if vt in ("categorical", "logical"):
            return True
        if vt == "continuous":
            return False
        return s.dtype == object or str(s.dtype) == "category" or s.dtype == bool

    def fit(self, X: pd.DataFrame, y=None):
        self.columns_ = list(X.columns)
        self.col_info_ = {}
        for c in self.columns_:
            s = X[c]
            if self._is_categorical(c, s):
                levels = sorted(set(s.where(s.notna(), MISSING_LEVEL).astype(str).unique()))
                self.col_info_[c] = {"kind": "cat", "levels": levels}
            else:
                num = pd.to_numeric(s, errors="coerce")
                med = float(num.median()) if num.notna().any() else 0.0
                self.col_info_[c] = {"kind": "num", "median": med}
        self.feature_names_ = []
        for c in self.columns_:
            info = self.col_info_[c]
            if info["kind"] == "num":
                self.feature_names_.append(c)
            else:
                self.feature_names_ += [f"{c}={lv}" for lv in info["levels"][1:]]
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        out = {}
        for c in self.columns_:
            info = self.col_info_[c]
            if c not in X.columns:
                # 外部数据缺列：数值给中位数，分类给参照水平（全 0）
                if info["kind"] == "num":
                    out[c] = np.full(len(X), info["median"])
                continue
            if info["kind"] == "num":
                out[c] = pd.to_numeric(X[c], errors="coerce").fillna(info["median"]).to_numpy(float)
            else:
                s = X[c].where(X[c].notna(), MISSING_LEVEL).astype(str)
                for lv in info["levels"][1:]:
                    out[f"{c}={lv}"] = (s == lv).astype(float).to_numpy()
        for c in self.columns_:
            info = self.col_info_[c]
            if info["kind"] == "cat" and c not in X.columns:
                for lv in info["levels"][1:]:
                    out[f"{c}={lv}"] = np.zeros(len(X))
        return pd.DataFrame(out, index=X.index)[self.feature_names_]

    def get_feature_names_out(self, input_features=None):
        return np.array(self.feature_names_)


def encode_y(y: pd.Series, variable_types: dict = None):
    """编码响应变量。返回 (y_numeric_series, label_encoder 或 None)。"""
    variable_types = variable_types or {}
    vt = variable_types.get(y.name)
    vt = getattr(vt, "value", vt)
    if vt in ("categorical", "logical") or (vt is None and (y.dtype == object or str(y.dtype) == "category")):
        le = LabelEncoder()
        return pd.Series(le.fit_transform(y.astype(str)), index=y.index, name=y.name), le
    num = pd.to_numeric(y, errors="coerce")
    if num.notna().sum() == 0:
        raise ValueError(f"响应变量 {y.name} 无法转换为数值")
    return num.astype(float), None
