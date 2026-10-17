from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import MLRequest, MLResult, UserPublic
from app.services.auth_service import get_current_user
from app.services.data_service import get_data_for_ml, get_raw_data, assert_dataset_access
from app.services.ml.utils import prepare_xy, encode_figure, ChartData, TableData, COLOR_UP, COLOR_DOWN
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

@router.post("/missing", response_model=MLResult)
def missing_values(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    try:
        assert_dataset_access(request.dataset_id, current_user.id)
        # E3e：缺失诊断读原始数据（应用筛选、不删行），不再走 get_data_for_ml 的 dropna
        columns = [request.y_variable] + list(request.x_variables)
        if request.is_survival and request.time_variable:
            columns.append(request.time_variable)
        columns = list(dict.fromkeys(columns))
        df = get_raw_data(request.dataset_id, columns, request.filters, current_user.id)
        if len(df) == 0:
            raise ValueError("Filtered data is empty")

        missing_data = []
        pct_by_var = {}
        for col in df.columns:
            missing = int(df[col].isna().sum())
            total = len(df)
            pct = round(missing / total * 100, 2) if total > 0 else 0.0
            uniq = df[col].dropna().unique()
            if len(uniq) == 2 and set(uniq).issubset({0, 1, True, False}):
                vtype = "逻辑"
            elif pd.api.types.is_numeric_dtype(df[col]):
                vtype = "连续"
            else:
                vtype = "分类"
            missing_data.append({
                "Variable": col,
                "MissingCount": missing,
                "MissingPercent": f"{pct}%",
                "Type": vtype
            })
            pct_by_var[col] = pct
        missing_df = pd.DataFrame(missing_data).sort_values("MissingCount", ascending=False)

        # Chart：直接用数值 pct，避免 int("12.5%") 抛异常
        fig, ax = plt.subplots(figsize=(10, max(4, len(missing_df) * 0.4)))
        pct_series = [pct_by_var[v] for v in missing_df["Variable"]]
        colors = [COLOR_UP if v > 20 else COLOR_DOWN for v in pct_series]
        ax.barh(missing_df["Variable"][::-1], pct_series[::-1], color=colors[::-1])
        ax.set_xlabel("缺失比例 (%)")
        ax.set_title("缺失值诊断")
        ax.axvline(20, color=COLOR_UP, linestyle='--', label='20%阈值')
        ax.legend()
        chart = ChartData(title="缺失值分布", data=encode_figure(fig, "svg"), type="svg")

        table = TableData(title="缺失值统计", headers=["Variable", "MissingCount", "MissingPercent", "Type"],
                          rows=missing_df.values.tolist())
        summary = f"缺失值诊断完成。共{len(df.columns)}个变量，总样本{len(df)}。"
        high_missing = missing_df[missing_df["MissingCount"] > len(df) * 0.2]
        if len(high_missing) > 0:
            summary += f" 注意：{len(high_missing)}个变量缺失率超过20%。"
        return MLResult(charts=[chart], tables=[table], summary=summary)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/correlation", response_model=MLResult)
def correlation_matrix(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    try:
        assert_dataset_access(request.dataset_id, current_user.id)
        df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                             request.is_survival, request.time_variable, request.filters)
        if len(df) == 0:
            raise ValueError("Filtered data is empty")
        X, y, le = prepare_xy(df, request.y_variable, request.x_variables, variable_types=request.variable_types)
        corr = X.corr().round(3)

        headers = ["Variable"] + list(corr.columns)
        rows = []
        for idx, row in corr.iterrows():
            rows.append([idx] + row.tolist())
        table = TableData(title="相关系数矩阵", headers=headers, rows=rows)

        summary = f"相关系数矩阵计算完成。共{len(corr.columns)}个特征变量。"
        return MLResult(tables=[table], summary=summary)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
