from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import MLRequest, MLResult, UserPublic
from app.services.auth_service import get_current_user
from app.services.data_service import get_data_for_ml, assert_dataset_access
from app.services.ml.utils import prepare_xy, encode_figure, ChartData, TableData
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

@router.post("/missing", response_model=MLResult)
def missing_values(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    try:
        assert_dataset_access(request.dataset_id, current_user.id)
        df = get_data_for_ml(request.dataset_id, request.y_variable, request.x_variables,
                             request.is_survival, request.time_variable, request.filters)
        if len(df) == 0:
            raise ValueError("Filtered data is empty")

        missing_data = []
        for col in df.columns:
            missing = int(df[col].isna().sum())
            total = len(df)
            pct = round(missing / total * 100, 2) if total > 0 else 0
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
        missing_df = pd.DataFrame(missing_data).sort_values("MissingCount", ascending=False)

        # Chart
        fig, ax = plt.subplots(figsize=(10, max(4, len(missing_df) * 0.4)))
        colors = ["#e74c3c" if int(str(v).replace("%", "")) > 20 else "#3498db" for v in missing_df["MissingPercent"]]
        ax.barh(missing_df["Variable"][::-1], [int(str(v).replace("%", "")) for v in missing_df["MissingPercent"]][::-1], color=colors[::-1])
        ax.set_xlabel("缺失比例 (%)")
        ax.set_title("缺失值诊断")
        ax.axvline(20, color='r', linestyle='--', label='20%阈值')
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
