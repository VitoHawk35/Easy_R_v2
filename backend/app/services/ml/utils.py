import base64
import io
import logging
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rc_params_from_file
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             roc_auc_score, confusion_matrix, roc_curve, mean_squared_error,
                             r2_score, classification_report)
from app.models.schemas import ChartData, TableData

logger = logging.getLogger(__name__)

# 统一图表配色（与前端 tokens / supabase-med.mplstyle 保持一致）。
# 绿色只作品牌色，不用于表达数据含义；上/下调固定为品红/靛蓝。
COLOR_INK = "#171717"
COLOR_MUTED = "#707070"
COLOR_GREEN = "#3ecf8e"
COLOR_PURPLE = "#644fc1"
COLOR_UP = "#e2005a"
COLOR_DOWN = "#054cff"
COLOR_WARN = "#a16207"

# 多系列数据的分类色（不含绿色）
DATA_COLORS = [COLOR_INK, COLOR_PURPLE, COLOR_DOWN, COLOR_UP, COLOR_WARN, COLOR_MUTED]

# backend/app/assets/supabase-med.mplstyle
PLOT_STYLE_PATH = Path(__file__).resolve().parents[2] / "assets" / "supabase-med.mplstyle"

# 服务器上没有 Inter/苹方时回退到可用的 CJK 字体，保证中文标题正常渲染
_CJK_FONT_FALLBACK = [
    'Inter', 'SimHei', 'PingFang SC', 'Microsoft YaHei',
    'Noto Sans CJK SC', 'Noto Sans CJK JP',
    'Noto Serif CJK SC', 'Noto Serif CJK JP', 'DejaVu Sans',
]


def apply_plot_style(style_path=None) -> bool:
    """加载统一图表样式；失败时降级为 matplotlib 默认样式并打 warning，绝不抛异常。"""
    path = Path(style_path) if style_path is not None else PLOT_STYLE_PATH
    try:
        # plt.style.use 遇到非法取值只打 warning、不抛异常，因此先严格预校验一遍
        rc_params_from_file(str(path), use_default_template=False, fail_on_error=True)
        plt.style.use(str(path))
        applied = True
    except Exception as exc:  # 文件缺失、语法错误、非法取值、字体/cycler 不兼容等
        logger.warning("无法加载 matplotlib 样式 %s，已回退默认样式：%s", path, exc)
        plt.style.use('default')
        applied = False

    # 字体兜底放在样式之后，避免被样式表覆盖
    plt.rcParams['font.sans-serif'] = _CJK_FONT_FALLBACK
    plt.rcParams['axes.unicode_minus'] = False
    return applied


# 模块加载时应用一次
apply_plot_style()

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
