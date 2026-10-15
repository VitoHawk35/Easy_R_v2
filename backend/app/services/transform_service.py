# -*- coding: utf-8 -*-
"""数据转换：ALR（加性对数比）与 CLR（中心化对数比）。

CLR 为 v2 新增：峰占比数据为组成型数据（行和≈1），直接用会引入虚假相关；
CLR 无需指定基准峰，避免 ALR 结果随基准峰选择而变化。
"""
import re
import time
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from app.models.schemas import DataTransformRequest, DataTransformResponse, TableData
from app.services.data_service import get_dataset, get_variables, register_dataframe


def _safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_")


def _numeric_peak_data(df: pd.DataFrame, peak_variables: List[str]) -> pd.DataFrame:
    converted = pd.DataFrame(index=df.index)
    invalid = []
    for col in peak_variables:
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() == 0:
            invalid.append(col)
        converted[col] = series
    if invalid:
        raise ValueError(f"峰变量无法转换为数值: {', '.join(invalid)}")
    return converted


def _is_continuous_y(y: pd.Series) -> bool:
    y_numeric = pd.to_numeric(y, errors="coerce")
    if y_numeric.notna().sum() != y.notna().sum():
        return False
    return y_numeric.nunique(dropna=True) > 10


def _p_value_auto(x: pd.Series, y: pd.Series, requested_test: str) -> Tuple[float, str]:
    data = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(data) < 3:
        return np.nan, "insufficient"

    if requested_test == "spearman" or (requested_test == "auto" and _is_continuous_y(data["y"])):
        y_numeric = pd.to_numeric(data["y"], errors="coerce")
        valid = data["x"].notna() & y_numeric.notna()
        if valid.sum() < 3:
            return np.nan, "spearman"
        return float(stats.spearmanr(data.loc[valid, "x"], y_numeric.loc[valid]).pvalue), "spearman"

    groups = [group["x"].dropna() for _, group in data.groupby("y")]
    groups = [group for group in groups if len(group) > 0]
    if len(groups) < 2:
        return np.nan, "insufficient"

    if requested_test == "ttest":
        if len(groups) != 2:
            raise ValueError("t-test仅支持二分类Y变量")
        if len(groups[0]) < 2 or len(groups[1]) < 2:
            return np.nan, "ttest"
        return float(stats.ttest_ind(groups[0], groups[1], equal_var=False, nan_policy="omit").pvalue), "ttest"

    if requested_test == "auto" and len(groups) == 2:
        if len(groups[0]) < 2 or len(groups[1]) < 2:
            return np.nan, "ttest"
        return float(stats.ttest_ind(groups[0], groups[1], equal_var=False, nan_policy="omit").pvalue), "ttest"

    if requested_test in ["anova", "auto"]:
        if any(len(group) < 2 for group in groups):
            return np.nan, "anova"
        return float(stats.f_oneway(*groups).pvalue), "anova"

    raise ValueError(f"不支持的p值检验方式: {requested_test}")


def _format_float(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:.6g}"


def _screen_peaks(x_df: pd.DataFrame, y: pd.Series, request: DataTransformRequest):
    """对每个（变换前）峰计算 CV 与 p 值，返回 (retained, rows, p_tests)。"""
    retained: List[str] = []
    rows: List[List[Any]] = []
    p_tests: Dict[str, str] = {}
    reference = request.reference_variable
    for col in request.peak_variables:
        x = x_df[col]
        mean_abs = abs(float(x.mean(skipna=True)))
        cv = np.nan if mean_abs == 0 else float(x.std(skipna=True) / mean_abs)
        p_value, p_test = _p_value_auto(x, y, request.pvalue_test)
        p_tests[col] = p_test
        cv_pass = bool(not pd.isna(cv) and cv > request.cv_threshold)
        p_pass = bool(not pd.isna(p_value) and (p_value > request.p_threshold if request.p_operator == "gt" else p_value < request.p_threshold))
        is_reference = bool(reference) and col == reference
        final_pass = cv_pass and p_pass and not is_reference
        status = "基准峰" if is_reference else ("保留" if final_pass else "排除")
        rows.append([col, _format_float(cv), _format_float(p_value),
                     "通过" if cv_pass else "未通过", "通过" if p_pass else "未通过", status, "", p_test])
        if final_pass:
            retained.append(col)
    return retained, rows, p_tests


def _finish(request: DataTransformRequest, df: pd.DataFrame, transformed: pd.DataFrame,
            rows: list, p_tests: dict, retained: list, generated: list,
            table_title: str, summary: str, meta_extra: dict, user_id: str) -> DataTransformResponse:
    preserve_cols = [col for col in df.columns if col not in request.peak_variables]
    output_df = pd.concat([df[preserve_cols], transformed], axis=1)
    output_base = request.output_name or f"{request.dataset_id}_{request.method.upper()}"
    dataset_id = f"transform_{int(time.time() * 1000)}"
    dataset = register_dataframe(dataset_id, output_df, output_base, {
        "source_dataset_id": request.dataset_id,
        "method": request.method,
        "reference_variable": request.reference_variable,
        "peak_variables": request.peak_variables,
        "generated_variables": generated,
        "cv_threshold": request.cv_threshold,
        "p_threshold": request.p_threshold,
        "p_operator": request.p_operator,
        "pvalue_test": request.pvalue_test,
        "p_tests": p_tests,
        "zero_strategy": request.zero_strategy,
        "pseudocount": request.pseudocount,
        **meta_extra,
    }, user_id=user_id)
    screening_table = TableData(
        title=table_title,
        headers=["变量", "CV", "p值", "CV状态", "p值状态", "最终状态", "输出变量", "检验方法"],
        rows=rows,
    )
    return DataTransformResponse(
        dataset=dataset,
        variables=get_variables(dataset.id),
        screening_table=screening_table,
        summary=summary,
        method_info={
            "method": request.method,
            "reference_variable": request.reference_variable,
            "generated_variables": generated,
            "retained_peak_variables": retained,
        },
    )


def _run_alr(request: DataTransformRequest, df: pd.DataFrame, user_id: str = None) -> DataTransformResponse:
    if not request.reference_variable:
        raise ValueError("ALR转换必须指定基准峰变量")
    if request.reference_variable not in request.peak_variables:
        raise ValueError("基准峰必须包含在峰变量列表中")
    if len(request.peak_variables) < 2:
        raise ValueError("ALR转换至少需要2个峰变量")

    peak_df = _numeric_peak_data(df, request.peak_variables)
    adjusted = peak_df + request.pseudocount
    if (adjusted <= 0).any().any():
        bad_cols = adjusted.columns[(adjusted <= 0).any()].tolist()
        raise ValueError(f"加伪计数后仍存在非正峰值: {', '.join(bad_cols)}")

    y = df[request.y_variable]
    retained, rows, p_tests = _screen_peaks(adjusted, y, request)
    if not retained:
        raise ValueError("没有峰变量通过筛选，无法生成ALR变量。请调整CV或p值阈值。")

    ref = adjusted[request.reference_variable]
    generated = [f"ALR_{_safe_name(col)}_{_safe_name(request.reference_variable)}" for col in retained]
    transformed = pd.DataFrame(index=df.index)
    for col, out_var in zip(retained, generated):
        transformed[out_var] = np.log(adjusted[col] / ref)
    for row in rows:
        col = row[0]
        if col in retained:
            row[6] = f"ALR_{_safe_name(col)}_{_safe_name(request.reference_variable)}"

    op_label = ">" if request.p_operator == "gt" else "<"
    summary = (
        f"ALR转换完成：输入{len(request.peak_variables)}个峰，基准峰为{request.reference_variable}，"
        f"筛选条件为CV > {request.cv_threshold:g} 且 p {op_label} {request.p_threshold:g}，"
        f"生成{len(generated)}个ALR变量。"
    )
    return _finish(request, df, transformed, rows, p_tests, retained, generated,
                   "ALR转换变量筛选结果", summary, {}, user_id)


def _run_clr(request: DataTransformRequest, df: pd.DataFrame, user_id: str = None) -> DataTransformResponse:
    """CLR：行闭合（和为1）后取对数、减几何均值对数。无需基准峰。

    注意：CLR 坐标之和恒为 0（精确共线），建模时建议剔除任一坐标，
    或使用对共线不敏感的模型（树模型/正则化回归）。
    """
    if len(request.peak_variables) < 2:
        raise ValueError("CLR转换至少需要2个峰变量")

    peak_df = _numeric_peak_data(df, request.peak_variables)
    adjusted = peak_df.copy()
    zero_mask = adjusted <= 0
    if zero_mask.any().any():
        min_pos = adjusted[adjusted > 0].min().min()
        if not np.isfinite(min_pos) or min_pos <= 0:
            min_pos = request.pseudocount
        adjusted[zero_mask] = min_pos / 2  # 乘性替换：半最小正值

    y = df[request.y_variable]
    retained, rows, p_tests = _screen_peaks(adjusted, y, request)
    if not retained:
        raise ValueError("没有峰变量通过筛选，无法生成CLR变量。请调整CV或p值阈值。")

    # 闭合 + CLR（对全部峰计算几何均值，保证坐标定义与筛选无关）
    closed = adjusted.div(adjusted.sum(axis=1), axis=0)
    logv = np.log(closed)
    gm_log = logv.mean(axis=1)
    generated = [f"CLR_{_safe_name(col)}" for col in retained]
    transformed = pd.DataFrame(index=df.index)
    for col, out_var in zip(retained, generated):
        transformed[out_var] = logv[col] - gm_log
    for row in rows:
        col = row[0]
        if col in retained:
            row[6] = f"CLR_{_safe_name(col)}"

    op_label = ">" if request.p_operator == "gt" else "<"
    summary = (
        f"CLR转换完成：输入{len(request.peak_variables)}个峰（行闭合后取对数减几何均值），"
        f"筛选条件为CV > {request.cv_threshold:g} 且 p {op_label} {request.p_threshold:g}，"
        f"生成{len(generated)}个CLR变量。注意CLR坐标共线，建模时建议剔除一个坐标或使用正则化/树模型。"
    )
    return _finish(request, df, transformed, rows, p_tests, retained, generated,
                   "CLR转换变量筛选结果", summary, {}, user_id)


def run_data_transform(request: DataTransformRequest, user_id: str = None) -> DataTransformResponse:
    df = get_dataset(request.dataset_id).copy()
    needed_cols = list(request.peak_variables) + [request.y_variable]
    if request.reference_variable:
        needed_cols.append(request.reference_variable)
    missing = [col for col in needed_cols if col not in df.columns]
    if missing:
        raise ValueError(f"变量不存在: {', '.join(sorted(set(missing)))}")

    if request.method == "alr":
        return _run_alr(request, df, user_id)
    if request.method == "clr":
        return _run_clr(request, df, user_id)
    raise ValueError(f"暂不支持的转换方法: {request.method}")
