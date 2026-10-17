# -*- coding: utf-8 -*-
"""外部验证 v2：训练集上 fit 完整 Pipeline（预处理+模型），外部数据只 transform+predict。

修复点：
- 预处理（中位数填补、哑变量水平）全部来自训练集，外部数据不做任何统计学习；
- 模型实例化统一走 core 注册表，支持全部模型 key（REPAIR_LOG #5）。
"""
from __future__ import annotations

import json
import os
import shutil
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.models.schemas import MLResult, UserPublic
from app.services.auth_service import get_current_user
from app.services.core.metrics import bootstrap_auc_ci, calibration_bins, dca_curve
from app.services.core.models import create_model, needs_scale
from app.services.core.preprocessing import ClinicalPreprocessor, encode_y
from app.services.data_service import DATA_DIR, assert_dataset_access, get_data_for_ml
from app.services.ml.utils import ChartData, TableData, encode_figure, COLOR_UP, COLOR_PURPLE, COLOR_MUTED

router = APIRouter(prefix="/api/eval", tags=["evaluation"])


@router.post("/external", response_model=MLResult)
def external_validation(
    dataset_id: str = Form(...),
    model_type: str = Form(...),
    y_variable: str = Form(...),
    x_variables: str = Form(...),  # comma separated
    params: str = Form("{}"),
    seed: int = Form(123),
    variable_types: str = Form("{}"),
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(get_current_user),
):
    try:
        assert_dataset_access(dataset_id, current_user.id)
        x_vars = [v.strip() for v in x_variables.split(",") if v.strip()]
        param_dict = json.loads(params)
        variable_type_dict = json.loads(variable_types)

        # 1. 训练集：fit 完整 Pipeline（预处理统计量只来自训练集）
        df_train = get_data_for_ml(dataset_id, y_variable, x_vars, False, None, [])
        if len(df_train) == 0:
            raise ValueError("训练数据为空")
        X_train = df_train[x_vars]
        y_train, le = encode_y(df_train[y_variable], variable_type_dict)

        steps = [("prep", ClinicalPreprocessor(variable_type_dict))]
        if needs_scale(model_type):
            steps.append(("scale", StandardScaler()))
        steps.append(("clf", create_model(model_type, param_dict, seed)))
        pipe = Pipeline(steps)
        pipe.fit(X_train, y_train)

        # 2. 读取外部数据
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in [".csv", ".xlsx", ".xls"]:
            raise HTTPException(status_code=400, detail="仅支持 CSV 或 Excel 文件")
        temp_id = f"ext_val_{int(time.time())}"
        file_path = os.path.join(DATA_DIR, f"{temp_id}{ext}")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        df_ext = pd.read_excel(file_path) if ext in [".xlsx", ".xls"] else pd.read_csv(file_path)
        os.remove(file_path)

        missing = [c for c in [y_variable] + x_vars if c not in df_ext.columns]
        if missing:
            raise ValueError(f"外部数据缺少必要变量: {', '.join(missing)}")
        df_ext = df_ext.dropna(subset=[y_variable])

        # 3. 外部数据只 transform + predict；y 编码沿用训练集
        X_ext = df_ext[x_vars]
        y_ext_raw = df_ext[y_variable]
        if le is not None:
            y_str = y_ext_raw.astype(str)
            unseen = set(y_str.unique()) - set(le.classes_)
            if unseen:
                raise ValueError(f"外部数据的Y变量包含训练时未见过的类别: {unseen}")
            y_ext = pd.Series(le.transform(y_str), index=y_str.index)
        else:
            y_ext = pd.to_numeric(y_ext_raw, errors="coerce")
            ok = y_ext.notna()
            X_ext, y_ext = X_ext[ok], y_ext[ok]

        y_prob = pipe.predict_proba(X_ext)[:, 1]
        y_pred = pipe.predict(X_ext)

        # 4. 指标
        acc = accuracy_score(y_ext, y_pred)
        prec = precision_score(y_ext, y_pred, zero_division=0)
        rec = recall_score(y_ext, y_pred, zero_division=0)
        f1 = f1_score(y_ext, y_pred, zero_division=0)
        auc = roc_auc_score(y_ext, y_prob)
        ci = bootstrap_auc_ci(y_ext, y_prob, seed=seed)
        brier = brier_score_loss(y_ext, y_prob)

        # 5. 图：ROC + 校准 + DCA
        fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
        fpr, tpr, _ = roc_curve(y_ext, y_prob)
        axes[0].plot(fpr, tpr, label=f"AUC = {auc:.3f}")
        axes[0].plot([0, 1], [0, 1], "k--")
        axes[0].set_xlabel("False Positive Rate"); axes[0].set_ylabel("True Positive Rate")
        axes[0].set_title("外部验证 ROC 曲线"); axes[0].legend(loc="lower right")

        cb = calibration_bins(y_ext, y_prob)
        axes[1].plot(cb["mean_pred"], cb["obs_rate"], "o-", color=COLOR_UP)
        axes[1].plot([0, 1], [0, 1], "k--")
        axes[1].set_xlabel("Predicted Probability"); axes[1].set_ylabel("Observed Rate")
        axes[1].set_title("外部验证校准曲线")

        dca = dca_curve(y_ext, y_prob)
        axes[2].plot(dca["threshold"], dca["nb_model"], color=COLOR_PURPLE, label="Model")
        axes[2].plot(dca["threshold"], dca["nb_all"], "k--", lw=0.8, label="Treat all")
        axes[2].axhline(0, color=COLOR_MUTED, ls=":", lw=0.8, label="Treat none")
        axes[2].set_xlabel("Threshold Probability"); axes[2].set_ylabel("Net Benefit")
        axes[2].set_title("外部验证决策曲线"); axes[2].legend()
        plt.tight_layout()
        chart = ChartData(title="外部验证（ROC/校准/DCA）", data=encode_figure(fig, "svg"), type="svg")

        cm = confusion_matrix(y_ext, y_pred)
        cm_table = TableData(title="混淆矩阵", headers=["", "Pred 0", "Pred 1"],
                             rows=[["Actual 0", int(cm[0, 0]), int(cm[0, 1])],
                                   ["Actual 1", int(cm[1, 0]), int(cm[1, 1])]])
        auc_str = f"{auc:.4f} ({ci[0]:.4f}-{ci[1]:.4f})" if ci[0] is not None else f"{auc:.4f}"
        metrics_table = TableData(title="评估指标", headers=["Metric", "Value"],
                                  rows=[["Accuracy", round(acc, 4)],
                                        ["Precision", round(prec, 4)],
                                        ["Recall", round(rec, 4)],
                                        ["F1", round(f1, 4)],
                                        ["AUC (95%CI)", auc_str],
                                        ["Brier", round(brier, 4)]])
        summary = (f"外部验证完成（模型仅在训练集上训练）。训练集样本量: {len(df_train)}，"
                   f"独立数据集样本量: {len(df_ext)}。AUC={auc:.3f}，Brier={brier:.3f}。")
        return MLResult(charts=[chart], tables=[cm_table, metrics_table], summary=summary)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
