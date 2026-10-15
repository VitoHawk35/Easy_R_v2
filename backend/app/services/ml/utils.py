import base64
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             roc_auc_score, confusion_matrix, roc_curve, mean_squared_error,
                             r2_score, classification_report)
from app.models.schemas import ChartData, TableData

sns.set_style("whitegrid")
plt.rcParams['font.sans-serif'] = ['SimHei', 'Noto Sans CJK SC', 'Noto Sans CJK JP', 'Noto Serif CJK SC', 'Noto Serif CJK JP', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def fig_to_svg(fig: matplotlib.figure.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format='svg', bbox_inches='tight')
    buf.seek(0)
    svg = buf.getvalue().decode('utf-8')
    plt.close(fig)
    return svg

def fig_to_png_base64(fig: matplotlib.figure.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return b64

def encode_figure(fig: matplotlib.figure.Figure, fmt: str = "svg") -> str:
    if fmt == "png":
        return fig_to_png_base64(fig)
    return fig_to_svg(fig)

def _to_numeric_series(series: pd.Series) -> pd.Series:
    if series.dtype == object or series.dtype.name == 'category':
        cleaned = series.astype(str).str.strip().str.replace(',', '', regex=False)
        return pd.to_numeric(cleaned, errors='coerce')
    return pd.to_numeric(series, errors='coerce')


def prepare_x(df: pd.DataFrame, x_vars: list, variable_types: dict = None) -> pd.DataFrame:
    variable_types = variable_types or {}
    parts = []

    for var in x_vars:
        vtype = variable_types.get(var)
        series = df[var]

        if vtype == 'continuous':
            numeric = _to_numeric_series(series)
            if numeric.notna().sum() == 0:
                raise ValueError(f"变量 {var} 被设置为连续变量，但无法转换为数值")
            parts.append(numeric.rename(var).to_frame())
        elif vtype in ('categorical', 'logical'):
            dummies = pd.get_dummies(series.astype(str), prefix=var, drop_first=True)
            parts.append(dummies)
        else:
            if series.dtype == object or series.dtype.name == 'category':
                dummies = pd.get_dummies(series.astype(str), prefix=var, drop_first=True)
                parts.append(dummies)
            else:
                parts.append(_to_numeric_series(series).rename(var).to_frame())

    if not parts:
        return pd.DataFrame(index=df.index)

    X = pd.concat(parts, axis=1)
    X = X.apply(pd.to_numeric, errors='coerce')
    return X.fillna(X.mean()).fillna(0)


def prepare_xy(df: pd.DataFrame, y_var: str, x_vars: list, survival: bool = False, time_var: str = None, variable_types: dict = None):
    """Prepare X, y from dataframe. For classification, encode y to numeric."""
    variable_types = variable_types or {}
    X = prepare_x(df, x_vars, variable_types)
    y = df[y_var].copy()

    le = None
    y_type = variable_types.get(y_var)
    if y_type in ('categorical', 'logical') or (y_type is None and (y.dtype == object or y.dtype.name == 'category')):
        le = LabelEncoder()
        y = pd.Series(le.fit_transform(y.astype(str)), index=y.index, name=y.name)
    elif y_type == 'continuous':
        numeric_y = _to_numeric_series(y)
        if numeric_y.notna().sum() == 0:
            raise ValueError(f"响应变量 {y_var} 被设置为连续变量，但无法转换为数值")
        y = numeric_y.fillna(numeric_y.mean())
    return X, y, le

def classification_metrics(y_true, y_pred, y_prob=None) -> dict:
    result = {
        "Accuracy": round(accuracy_score(y_true, y_pred), 4),
        "Precision": round(precision_score(y_true, y_pred, average='weighted', zero_division=0), 4),
        "Recall": round(recall_score(y_true, y_pred, average='weighted', zero_division=0), 4),
        "F1": round(f1_score(y_true, y_pred, average='weighted', zero_division=0), 4),
    }
    # binary AUC
    if y_prob is not None and len(np.unique(y_true)) == 2:
        try:
            result["AUC"] = round(roc_auc_score(y_true, y_prob[:, 1]), 4)
        except Exception:
            pass
    return result

def regression_metrics(y_true, y_pred) -> dict:
    return {
        "MSE": round(mean_squared_error(y_true, y_pred), 4),
        "RMSE": round(np.sqrt(mean_squared_error(y_true, y_pred)), 4),
        "R2": round(r2_score(y_true, y_pred), 4),
        "MAE": round(np.mean(np.abs(y_true - y_pred)), 4),
    }
