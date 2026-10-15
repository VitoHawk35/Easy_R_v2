from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union, Literal
from enum import Enum

class VariableType(str, Enum):
    CONTINUOUS = "continuous"
    CATEGORICAL = "categorical"
    LOGICAL = "logical"

class ImageFormat(str, Enum):
    SVG = "svg"
    PNG = "png"
    TIFF = "tiff"

class ChartData(BaseModel):
    type: str = "svg"
    title: str
    data: str

class TableData(BaseModel):
    title: str
    headers: List[str]
    rows: List[List[Any]]

class MLResult(BaseModel):
    success: bool = True
    charts: List[ChartData] = []
    tables: List[TableData] = []
    summary: str = ""
    download_urls: List[str] = []
    model_info: Dict[str, Any] = Field(default_factory=dict, description="模型元信息，含coefficients/intercept等")

class MLRequest(BaseModel):
    dataset_id: str = Field(..., description="数据集ID")
    y_variable: str = Field(..., description="响应变量")
    is_survival: bool = Field(False, description="是否为生存数据")
    time_variable: Optional[str] = Field(None, description="生存时间变量")
    x_variables: List[str] = Field(default_factory=list, description="特征变量列表")
    filters: List[Dict[str, Any]] = Field(default_factory=list, description="筛选条件")
    params: Dict[str, Any] = Field(default_factory=dict, description="算法参数")
    seed: int = Field(123, description="随机数种子")
    variable_types: Dict[str, VariableType] = Field(default_factory=dict, description="变量类型覆盖")
    wizard_snapshot: Dict[str, Any] = Field(default_factory=dict, description="向导状态快照")

class DatasetInfo(BaseModel):
    id: str
    name: str
    rows: int
    cols: int

class UserPublic(BaseModel):
    id: str
    username: str
    created_at: str

class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)

class RegisterRequest(AuthRequest):
    pass

class AuthResponse(BaseModel):
    token: str
    user: UserPublic

class HistoryListItem(BaseModel):
    id: str
    created_at: str
    algorithm: str
    dataset_id: str
    dataset_name: str = ""
    y_variable: str = ""
    feature_count: int = 0
    summary: str = ""
    chart_count: int = 0
    table_count: int = 0

class HistoryDetail(HistoryListItem):
    request: Dict[str, Any] = Field(default_factory=dict)
    result: MLResult
    wizard_snapshot: Dict[str, Any] = Field(default_factory=dict, description="向导状态快照")

class VariableInfo(BaseModel):
    name: str
    type: VariableType
    range_str: str
    missing_count: int
    unique_count: int

class VariableListResponse(BaseModel):
    total: int
    selected: int
    variables: List[VariableInfo]

class DataTransformRequest(BaseModel):
    dataset_id: str = Field(..., description="源数据集ID")
    method: Literal["alr", "clr"] = Field("alr", description="转换方法")
    peak_variables: List[str] = Field(..., description="峰变量列表")
    reference_variable: Optional[str] = Field(None, description="基准峰变量（仅ALR需要）")
    y_variable: str = Field(..., description="响应变量，用于自动计算p值")
    cv_threshold: float = Field(0.15, ge=0, description="CV筛选阈值")
    p_threshold: float = Field(0.05, ge=0, le=1, description="p值筛选阈值")
    p_operator: Literal["gt", "lt"] = Field("gt", description="p值比较方向")
    pvalue_test: Literal["auto", "ttest", "anova", "spearman"] = Field("auto", description="p值检验方式")
    zero_strategy: Literal["pseudocount"] = Field("pseudocount", description="非正值处理策略")
    pseudocount: float = Field(1e-6, gt=0, description="伪计数")
    output_name: Optional[str] = Field(None, description="输出数据集名称")

class DataTransformResponse(BaseModel):
    success: bool = True
    dataset: DatasetInfo
    variables: List[VariableInfo]
    screening_table: TableData
    summary: str
    method_info: Dict[str, Any] = Field(default_factory=dict)
