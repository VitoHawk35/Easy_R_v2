import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, confusion_matrix, roc_auc_score, roc_curve
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
from app.services.core.models import canonical_key, create_model, needs_scale
from app.services.core.metrics import calibration_slope_intercept
import matplotlib.pyplot as plt

EVAL_DATASETS = ("train", "test", "both")


def _youden_threshold(y, p):
    """Youden 界值：只在训练集上选择，绝不在测试集上选界值。"""
    fpr, tpr, thr = roc_curve(y, p)
    finite = np.isfinite(thr)
    if not finite.any():
        return 0.5
    idx = int(np.argmax((tpr - fpr)[finite]))
    return float(thr[finite][idx])


def _metrics(y, p, threshold):
    """在给定阈值下计算判别/校准指标（E3h：threshold 用于混淆矩阵与灵敏度/特异度）。"""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    auc = float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else np.nan
    brier = float(brier_score_loss(y, p))
    slope, citl = calibration_slope_intercept(y, p)
    return {
        "n": int(len(y)),
        "auc": auc,
        "brier": brier,
        "threshold": float(threshold),
        "sens": float(tp / max(tp + fn, 1)),
        "spec": float(tn / max(tn + fp, 1)),
        "acc": float((tp + tn) / max(len(y), 1)),
        "ppv": float(tp / max(tp + fp, 1)),
        "npv": float(tn / max(tn + fn, 1)),
        "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
        "cal_slope": slope, "citl": citl,
    }


def _get_probabilities(request):
    """训练模型并返回训练集/测试集的预测概率与所选阈值（E3h）。

    约定：
    - testSize 由后端固定为 0.3（前端也始终传 0.3）；旧前端传 0.0 时按 0.3 处理，
      避免 train_test_split 报错；
    - evalDataset ∈ {train, test, both} 决定在哪些集合上评估；
    - threshold 未传时用训练集 Youden 界值（不得用测试集选界值）。
    """
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    if len(np.unique(y)) != 2:
        raise ValueError("Calibration/DCA requires binary classification")

    params = request.params or {}
    seed = int(params.get("seed", request.seed))
    try:
        test_size = float(params.get("testSize", 0.3))
    except (TypeError, ValueError):
        test_size = 0.3
    if not (0.0 < test_size < 1.0):
        test_size = 0.3

    model_type = params.get("modelType", "logistic")
    key = canonical_key(model_type)
    per_model = params.get("model_params", params.get("modelParams", {})) or {}
    model_params = per_model.get(key, per_model.get(model_type, {})) or {}
    model = create_model(key, model_params, seed)

    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=needs_scale(key), X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=True, variable_types=request.variable_types)

    p_train = pipe.predict_proba(X_train)[:, 1]
    p_test = pipe.predict_proba(X_test)[:, 1]

    if params.get("threshold") is not None:
        threshold = float(params["threshold"])
        threshold_source = "用户指定"
    else:
        threshold = _youden_threshold(y_train, p_train)
        threshold_source = "训练集 Youden 界值"

    eval_dataset = str(params.get("evalDataset", "test")).lower()
    if eval_dataset not in EVAL_DATASETS:
        raise ValueError("evalDataset 必须是 train / test / both")
    if eval_dataset == "train":
        selected = [("train", y_train, p_train)]
    elif eval_dataset == "both":
        selected = [("train", y_train, p_train), ("test", y_test, p_test)]
    else:
        selected = [("test", y_test, p_test)]

    return {
        "key": key,
        "threshold": threshold,
        "threshold_source": threshold_source,
        "selected": selected,
        "train": (y_train, p_train),
        "test": (y_test, p_test),
    }


def _metrics_table(ctx):
    rows = []
    for name, yy, pp in ctx["selected"]:
        m = _metrics(yy, pp, ctx["threshold"])
        label = "训练集" if name == "train" else "测试集"
        rows.append([
            label, m["n"], round(m["auc"], 4), round(m["brier"], 4),
            round(m["threshold"], 2), round(m["sens"], 4), round(m["spec"], 4),
            round(m["acc"], 4), round(m["ppv"], 4), round(m["npv"], 4),
            m["tp"], m["fp"], m["tn"], m["fn"],
            round(m["cal_slope"], 4) if np.isfinite(m["cal_slope"]) else "N/A",
            round(m["citl"], 4) if np.isfinite(m["citl"]) else "N/A",
        ])
    return TableData(
        title="评估指标（按评估数据集）",
        headers=["数据集", "N", "AUC", "Brier", "阈值", "灵敏度", "特异度",
                 "准确率", "PPV", "NPV", "TP", "FP", "TN", "FN", "校准斜率", "CITL"],
        rows=rows,
    )


def _calibration_note(ctx):
    notes = []
    for name, yy, pp in ctx["selected"]:
        slope, citl = calibration_slope_intercept(yy, pp)
        if not np.isfinite(slope) or not np.isfinite(citl):
            label = "训练集" if name == "train" else "测试集"
            notes.append(f"{label}校准斜率/CITL 无法估计（完全分离或不收敛）。")
    return (" " + " ".join(notes)) if notes else ""


def run_calibration(request, fmt="svg"):
    ctx = _get_probabilities(request)
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')
    for name, yy, pp in ctx["selected"]:
        prob_true, prob_pred = calibration_curve(yy, pp, n_bins=10, strategy='uniform')
        brier = brier_score_loss(yy, pp)
        label = "训练集" if name == "train" else "测试集"
        ax.plot(prob_pred, prob_true, 's-', label=f'{label} (Brier={brier:.3f})')
    ax.set_xlabel('Mean Predicted Probability')
    ax.set_ylabel('Fraction of Positives')
    ax.set_title('校准曲线（可靠性图）')
    ax.legend(loc='lower right')
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    ax.grid(True, alpha=0.3)
    chart1 = ChartData(title="校准曲线", data=encode_figure(fig, fmt), type=fmt)
    table = _metrics_table(ctx)
    summary = (
        f"校准曲线完成。模型={ctx['key']}，评估数据集={ctx['selected'][0][0] if len(ctx['selected']) == 1 else 'both'}，"
        f"阈值={ctx['threshold']:.2f}（{ctx['threshold_source']}）。"
        f"{_calibration_note(ctx)}"
    )
    return {"charts": [chart1], "tables": [table], "summary": summary}


def run_dca(request, fmt="svg"):
    ctx = _get_probabilities(request)
    thresholds = np.arange(0.01, 1.00, 0.01)
    fig, ax = plt.subplots(figsize=(8, 6))
    for name, yy, pp in ctx["selected"]:
        n = len(yy)
        net_benefit_model = []
        for thresh in thresholds:
            pred_pos = (pp >= thresh).astype(int)
            tp = np.sum((pred_pos == 1) & (yy == 1))
            fp = np.sum((pred_pos == 1) & (yy == 0))
            net_benefit_model.append((tp / n) - (fp / n) * (thresh / (1 - thresh)))
        label = "训练集" if name == "train" else "测试集"
        ax.plot(thresholds, net_benefit_model, lw=2, label=f'Model ({label})')
    yy0 = ctx["selected"][0][1]
    net_benefit_all = (np.sum(yy0 == 1) / len(yy0)) - (np.sum(yy0 == 0) / len(yy0)) * (thresholds / (1 - thresholds))
    ax.plot(thresholds, net_benefit_all, 'r--', lw=1.5, label='Treat All')
    ax.plot(thresholds, np.zeros_like(thresholds), 'k:', lw=1.5, label='Treat None')
    ax.set_xlabel('Threshold Probability')
    ax.set_ylabel('Net Benefit')
    ax.set_title('决策曲线分析（DCA）')
    ax.legend(loc='upper right')
    ax.set_xlim([0, 1])
    ax.grid(True, alpha=0.3)
    chart1 = ChartData(title="DCA曲线", data=encode_figure(fig, fmt), type=fmt)
    table = _metrics_table(ctx)
    summary = (
        f"DCA分析完成。模型={ctx['key']}，评估数据集="
        f"{'both' if len(ctx['selected']) > 1 else ctx['selected'][0][0]}，"
        f"阈值={ctx['threshold']:.2f}（{ctx['threshold_source']}）。"
    )
    return {"charts": [chart1], "tables": [table], "summary": summary}
