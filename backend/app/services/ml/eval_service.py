import pandas as pd
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, roc_auc_score
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, ChartData, TableData
from app.services.core.preprocessing import encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt

def _get_probabilities(request):
    """Train a model and return test probabilities for binary classification."""
    df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                         request.is_survival, request.time_variable, request.filters)
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    if len(np.unique(y)) != 2:
        raise ValueError("Calibration/DCA requires binary classification")
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    model_type = request.params.get("modelType", "logistic")
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    if model_type == "random-forest":
        model = RandomForestClassifier(n_estimators=200, random_state=seed)
    elif model_type == "xgboost":
        try:
            from xgboost import XGBClassifier
            model = XGBClassifier(n_estimators=200, random_state=seed, use_label_encoder=False, eval_metric='logloss')
        except Exception:
            model = RandomForestClassifier(n_estimators=200, random_state=seed)
    else:
        model = LogisticRegression(max_iter=2000, random_state=seed)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=False, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=True, variable_types=request.variable_types)
    y_prob = pipe.predict_proba(X_test)[:, 1]
    return y_test, y_prob

def run_calibration(request, fmt="svg"):
    y_test, y_prob = _get_probabilities(request)
    prob_true, prob_pred = calibration_curve(y_test, y_prob, n_bins=10, strategy='uniform')
    brier = brier_score_loss(y_test, y_prob)
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')
    ax.plot(prob_pred, prob_true, 's-', color='#3498db', label=f'Model (Brier={brier:.3f})')
    ax.set_xlabel('Mean Predicted Probability')
    ax.set_ylabel('Fraction of Positives')
    ax.set_title('Calibration Curve (Reliability Diagram)')
    ax.legend(loc='lower right')
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    ax.grid(True, alpha=0.3)
    chart1 = ChartData(title="校准曲线", data=encode_figure(fig, fmt), type=fmt)
    table = TableData(title="校准数据", headers=["Bin Mean Pred", "Fraction Positives"],
                      rows=list(zip(prob_pred.round(3), prob_true.round(3))))
    summary = f"校准曲线完成。Brier分数={brier:.4f}，模型{'校准良好' if brier < 0.1 else '校准一般' if brier < 0.25 else '校准较差'}。"
    return {"charts": [chart1], "tables": [table], "summary": summary}

def run_dca(request, fmt="svg"):
    y_test, y_prob = _get_probabilities(request)
    # Compute net benefit for model, treat all, treat none
    thresholds = np.arange(0.01, 1.00, 0.01)
    n = len(y_test)
    net_benefit_model = []
    net_benefit_all = []
    net_benefit_none = []
    for thresh in thresholds:
        pred_pos = (y_prob >= thresh).astype(int)
        tp = np.sum((pred_pos == 1) & (y_test == 1))
        fp = np.sum((pred_pos == 1) & (y_test == 0))
        nb = (tp / n) - (fp / n) * (thresh / (1 - thresh))
        net_benefit_model.append(nb)
        net_benefit_all.append((np.sum(y_test == 1) / n) - (np.sum(y_test == 0) / n) * (thresh / (1 - thresh)))
        net_benefit_none.append(0)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(thresholds, net_benefit_model, 'b-', lw=2, label='Model')
    ax.plot(thresholds, net_benefit_all, 'r--', lw=1.5, label='Treat All')
    ax.plot(thresholds, net_benefit_none, 'k:', lw=1.5, label='Treat None')
    ax.set_xlabel('Threshold Probability')
    ax.set_ylabel('Net Benefit')
    ax.set_title('Decision Curve Analysis (DCA)')
    ax.legend(loc='upper right')
    ax.set_xlim([0, 1])
    ax.grid(True, alpha=0.3)
    chart1 = ChartData(title="DCA曲线", data=encode_figure(fig, fmt), type=fmt)
    summary = f"DCA分析完成。在概率阈值范围内评估了模型的临床净获益。"
    return {"charts": [chart1], "tables": [], "summary": summary}
