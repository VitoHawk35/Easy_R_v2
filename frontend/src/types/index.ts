export type VariableType = 'continuous' | 'categorical' | 'logical';

export interface VariableInfo {
  name: string;
  type: VariableType;
  range_str: string;
  missing_count: number;
  unique_count: number;
}

export interface DatasetInfo {
  id: string;
  name: string;
  rows: number;
  cols: number;
}

export interface MLRequest {
  dataset_id: string;
  y_variable: string;
  is_survival: boolean;
  time_variable?: string;
  x_variables: string[];
  filters: any[];
  params: Record<string, any>;
  seed: number;
  variable_types?: Record<string, VariableType>;
  wizard_snapshot?: Record<string, any>;
}

export function buildVariableTypes(variables: VariableInfo[]): Record<string, VariableType> {
  return variables.reduce<Record<string, VariableType>>((acc, variable) => {
    acc[variable.name] = variable.type;
    return acc;
  }, {});
}

export interface DataTransformConfig {
  dataset_id: string;
  method: 'alr' | 'clr';
  peak_variables: string[];
  reference_variable: string;
  y_variable: string;
  cv_threshold: number;
  p_threshold: number;
  p_operator: 'gt' | 'lt';
  pvalue_test: 'auto' | 'ttest' | 'anova' | 'spearman';
  zero_strategy: 'pseudocount';
  pseudocount: number;
  output_name?: string;
}

export interface DataTransformResponse {
  success: boolean;
  dataset: DatasetInfo;
  variables: VariableInfo[];
  screening_table: TableData;
  summary: string;
  method_info: Record<string, any>;
}

export interface ChartData {
  type: string;
  title: string;
  data: string;
}

export interface TableData {
  title: string;
  headers: string[];
  rows: any[][];
}

export interface MLResult {
  success: boolean;
  charts: ChartData[];
  tables: TableData[];
  summary: string;
  download_urls: string[];
  model_info?: Record<string, any>;
}

export interface User {
  id: string;
  username: string;
  created_at: string;
}

export interface AuthRequest {
  username: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface HistoryListItem {
  id: string;
  created_at: string;
  algorithm: string;
  dataset_id: string;
  dataset_name: string;
  y_variable: string;
  feature_count: number;
  summary: string;
  chart_count: number;
  table_count: number;
}

export interface HistoryDetail extends HistoryListItem {
  request: Record<string, any>;
  result: MLResult;
  wizard_snapshot?: Record<string, any>;
}

export interface AlgorithmConfig {
  key: string;
  label: string;
  params: AlgorithmParam[];
  category?: string;
}

export interface AlgorithmParam {
  name: string;
  label: string;
  type: 'number' | 'select' | 'boolean' | 'string' | 'array' | 'slider';
  default: any;
  options?: { label: string; value: any }[];
  min?: number;
  max?: number;
  step?: number;
}

// Wizard types
export interface DiagnosisConfig {
  vifThreshold: number;
  corrThreshold: number;
  autoRemove: boolean;
}

export interface FilterConfig {
  useUnivariate: boolean;
  univariateP: number;
  useLasso: boolean;
  lassoLambda: 'min' | '1se';
  useRF: boolean;
  useBoruta: boolean;
  borutaRuns: number;
  borutaP: number;
}

export interface FilterResults {
  univariate: string[];
  lasso: string[];
  rf: string[];
  boruta: string[];
  final: string[];
}

export interface WizardState {
  datasetId: string;
  datasetInfo: DatasetInfo | null;
  previewData: any[];
  previewColumns: string[];
  yVariable: string;
  isSurvival: boolean;
  timeVariable: string;
  groupVariable: string;
  allVariables: VariableInfo[];
  transformConfig: DataTransformConfig;
  transformResult: DataTransformResponse | null;
  diagnosisConfig: DiagnosisConfig;
  diagnosisResult: MLResult | null;
  removedVars: string[];
  filterConfig: FilterConfig;
  filterResults: FilterResults;
  buildMode: 'single' | 'compare';
  selectedModel: string;
  compareModels: string[];
  forcedIncludeVars: string[];
  modelParams: Record<string, any>;
  buildResult: MLResult | null;
  bestModel: string;
  evalResults: MLResult | null;
  vizResults: MLResult | null;
  explainResults: MLResult | null;
  advDiagResults: MLResult | null;
  validationResults: MLResult | null;
  modelInfo: Record<string, any> | null;
  currentStep: number;
  completedSteps: Set<number>;
}

export const ALGORITHMS: AlgorithmConfig[] = [
  {
    key: 'boruta',
    label: 'Boruta特征筛选',
    category: '特征筛选',
    params: [
      { name: 'maxRuns', label: '最大迭代次数maxRuns', type: 'number', default: 100, min: 10, max: 1000, step: 10 },
      { name: 'pValue', label: '显著性阈值pValue', type: 'number', default: 0.01, min: 0.001, max: 0.5, step: 0.001 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'lasso-screening',
    label: 'LASSO特征筛选',
    category: '特征筛选',
    params: [
      { name: 'cv', label: '交叉验证折数', type: 'number', default: 10, min: 2, max: 10, step: 1 },
      { name: 'standardize', label: '标准化', type: 'boolean', default: true },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'logistic-screening',
    label: 'Logistic单因素筛选',
    category: '特征筛选',
    params: [
      { name: 'pValue', label: 'P值阈值', type: 'number', default: 0.05, min: 0.001, max: 1, step: 0.01 },
      { name: 'standardize', label: '标准化', type: 'boolean', default: false },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'compare',
    label: '多个机器学习对比',
    category: '模型对比',
    params: [
      { name: 'models', label: '选择模型', type: 'array', default: ['LR', 'DT', 'RF', 'SVM', 'KNN', 'GBDT'] },
      { name: 'cv', label: '交叉验证折数', type: 'number', default: 5, min: 2, max: 10, step: 1 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'vif',
    label: 'VIF共线性诊断',
    category: '变量诊断',
    params: [
      { name: 'vifThreshold', label: 'VIF阈值', type: 'number', default: 5.0, min: 1, max: 20, step: 0.5 },
      { name: 'corrThreshold', label: '相关系数阈值', type: 'number', default: 0.7, min: 0.1, max: 1.0, step: 0.05 },
      { name: 'autoRemove', label: '自动移除高共线性变量', type: 'boolean', default: true },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'lasso',
    label: 'LASSO回归',
    category: '回归模型',
    params: [
      { name: 'cv', label: '交叉验证折数', type: 'number', default: 10, min: 2, max: 10, step: 1 },
      { name: 'standardize', label: '标准化', type: 'boolean', default: true },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'lasso-predict',
    label: 'Lasso预测模型',
    category: '回归模型',
    params: [
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'alpha', label: 'Alpha', type: 'number', default: 0.1, min: 0.0001, max: 10, step: 0.001 },
      { name: 'standardize', label: '标准化', type: 'boolean', default: true },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'elastic-net',
    label: '弹性网络',
    category: '回归模型',
    params: [
      { name: 'cv', label: '交叉验证折数', type: 'number', default: 5, min: 2, max: 10, step: 1 },
      { name: 'l1Ratio', label: 'L1比例', type: 'slider', default: 0.5, min: 0.01, max: 1.0, step: 0.01 },
      { name: 'standardize', label: '标准化', type: 'boolean', default: true },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'logistic',
    label: 'Logistic回归',
    category: '分类模型',
    params: [
      { name: 'C', label: 'C (正则化强度)', type: 'number', default: 1.0, min: 0.001, max: 100, step: 0.1 },
      { name: 'penalty', label: '惩罚类型', type: 'select', default: 'l2', options: [{ label: 'L1', value: 'l1' }, { label: 'L2', value: 'l2' }, { label: 'ElasticNet', value: 'elasticnet' }] },
      { name: 'solver', label: '求解器', type: 'select', default: 'lbfgs', options: [{ label: 'lbfgs', value: 'lbfgs' }, { label: 'liblinear', value: 'liblinear' }, { label: 'saga', value: 'saga' }] },
      { name: 'cv', label: '交叉验证折数', type: 'number', default: 5, min: 2, max: 10, step: 1 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'standardize', label: '标准化', type: 'boolean', default: true },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'cox',
    label: 'Cox回归',
    category: '生存分析',
    params: [
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'alpha', label: 'Alpha', type: 'number', default: 0.0, min: 0, max: 1, step: 0.01 },
      { name: 'penalizer', label: '惩罚系数', type: 'number', default: 0.0, min: 0, max: 1, step: 0.01 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'bkm',
    label: '贝叶斯核机器回归',
    category: '回归模型',
    params: [
      { name: 'kernel', label: '核函数', type: 'select', default: 'rbf', options: [{ label: 'RBF', value: 'rbf' }, { label: 'Linear', value: 'linear' }, { label: 'Poly', value: 'poly' }] },
      { name: 'iterations', label: '迭代次数', type: 'number', default: 1000, min: 100, max: 10000, step: 100 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'decision-tree',
    label: '决策树',
    category: '树模型',
    params: [
      { name: 'maxDepth', label: '最大深度', type: 'number', default: 5, min: 1, max: 20, step: 1 },
      { name: 'minSamplesSplit', label: '最小分裂样本', type: 'number', default: 2, min: 2, max: 50, step: 1 },
      { name: 'criterion', label: '分裂标准', type: 'select', default: 'gini', options: [{ label: 'Gini', value: 'gini' }, { label: 'Entropy', value: 'entropy' }] },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'random-forest',
    label: '随机森林',
    category: '树模型',
    params: [
      { name: 'nEstimators', label: '树的数量', type: 'number', default: 200, min: 10, max: 1000, step: 10 },
      { name: 'maxDepth', label: '最大深度', type: 'number', default: 10, min: 1, max: 50, step: 1 },
      { name: 'maxFeatures', label: '最大特征', type: 'select', default: 'sqrt', options: [{ label: 'sqrt', value: 'sqrt' }, { label: 'log2', value: 'log2' }, { label: '全部', value: null }] },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'xgboost',
    label: 'XGBoost',
    category: '梯度提升',
    params: [
      { name: 'nEstimators', label: '迭代次数', type: 'number', default: 200, min: 10, max: 1000, step: 10 },
      { name: 'maxDepth', label: '最大深度', type: 'number', default: 6, min: 1, max: 15, step: 1 },
      { name: 'learningRate', label: '学习率', type: 'number', default: 0.1, min: 0.01, max: 1.0, step: 0.01 },
      { name: 'subsample', label: '子采样比例', type: 'slider', default: 1.0, min: 0.1, max: 1.0, step: 0.05 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'lightgbm',
    label: 'LightGBM',
    category: '梯度提升',
    params: [
      { name: 'nEstimators', label: '迭代次数', type: 'number', default: 200, min: 10, max: 1000, step: 10 },
      { name: 'maxDepth', label: '最大深度', type: 'number', default: -1, min: -1, max: 15, step: 1 },
      { name: 'numLeaves', label: '叶子数', type: 'number', default: 31, min: 2, max: 256, step: 1 },
      { name: 'learningRate', label: '学习率', type: 'number', default: 0.1, min: 0.01, max: 1.0, step: 0.01 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'svm',
    label: '支持向量机',
    category: '分类模型',
    params: [
      { name: 'kernel', label: '核函数', type: 'select', default: 'rbf', options: [{ label: 'RBF', value: 'rbf' }, { label: 'Linear', value: 'linear' }, { label: 'Poly', value: 'poly' }, { label: 'Sigmoid', value: 'sigmoid' }] },
      { name: 'C', label: 'C', type: 'number', default: 1.0, min: 0.01, max: 100, step: 0.1 },
      { name: 'gamma', label: 'Gamma', type: 'select', default: 'scale', options: [{ label: 'scale', value: 'scale' }, { label: 'auto', value: 'auto' }] },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'knn',
    label: 'K-近邻算法',
    category: '分类模型',
    params: [
      { name: 'k', label: 'K值', type: 'number', default: 5, min: 1, max: 50, step: 1 },
      { name: 'weights', label: '权重', type: 'select', default: 'uniform', options: [{ label: 'Uniform', value: 'uniform' }, { label: 'Distance', value: 'distance' }] },
      { name: 'metric', label: '距离度量', type: 'select', default: 'minkowski', options: [{ label: 'Minkowski', value: 'minkowski' }, { label: 'Euclidean', value: 'euclidean' }, { label: 'Manhattan', value: 'manhattan' }] },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'lda',
    label: '线性判别分析LDA',
    category: '分类模型',
    params: [
      { name: 'solver', label: '求解器', type: 'select', default: 'svd', options: [{ label: 'SVD', value: 'svd' }, { label: 'LSQR', value: 'lsqr' }, { label: 'Eigen', value: 'eigen' }] },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'qda',
    label: '二次判别分析QDA',
    category: '分类模型',
    params: [
      { name: 'regParam', label: '正则化参数', type: 'number', default: 0.0, min: 0.0, max: 1.0, step: 0.01 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'catboost',
    label: 'CatBoost',
    category: '梯度提升',
    params: [
      { name: 'iterations', label: '迭代次数', type: 'number', default: 500, min: 50, max: 5000, step: 50 },
      { name: 'learning_rate', label: '学习率', type: 'number', default: 0.1, min: 0.01, max: 1.0, step: 0.01 },
      { name: 'depth', label: '树深度', type: 'number', default: 6, min: 2, max: 12, step: 1 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'mlp',
    label: '神经网络',
    category: '神经网络',
    params: [
      { name: 'hiddenLayers', label: '隐藏层结构', type: 'string', default: '100,50' },
      { name: 'activation', label: '激活函数', type: 'select', default: 'relu', options: [{ label: 'ReLU', value: 'relu' }, { label: 'Tanh', value: 'tanh' }, { label: 'Logistic', value: 'logistic' }] },
      { name: 'alpha', label: '正则化Alpha', type: 'number', default: 0.0001, min: 0.00001, max: 1, step: 0.0001 },
      { name: 'maxIter', label: '最大迭代次数', type: 'number', default: 500, min: 100, max: 5000, step: 100 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'tabpfn',
    label: 'TabPFN',
    category: '神经网络',
    params: [
      { name: 'nEstimators', label: '集成估计器数', type: 'number', default: 4, min: 1, max: 32, step: 1 },
      { name: 'device', label: '计算设备', type: 'select', default: 'auto', options: [{ label: '自动', value: 'auto' }, { label: 'CPU', value: 'cpu' }, { label: 'GPU(CUDA)', value: 'cuda' }] },
      { name: 'maxSamples', label: '最大训练样本数', type: 'number', default: 10000, min: 100, max: 100000, step: 1000 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'naive-bayes',
    label: '朴素贝叶斯',
    category: '分类模型',
    params: [
      { name: 'varSmoothing', label: '方差平滑', type: 'number', default: 1e-9, min: 1e-15, max: 1, step: 1e-10 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'shap',
    label: 'SHAP解释性',
    category: '模型解释',
    params: [
      { name: 'modelType', label: '模型类型', type: 'select', default: 'random-forest', options: [{ label: '随机森林', value: 'random-forest' }, { label: 'Logistic', value: 'logistic' }, { label: 'XGBoost', value: 'xgboost' }] },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'pdp',
    label: 'PDP/ICE分析',
    category: '模型解释',
    params: [
      { name: 'modelType', label: '模型类型', type: 'select', default: 'random-forest', options: [{ label: '随机森林', value: 'random-forest' }, { label: 'Logistic', value: 'logistic' }, { label: 'XGBoost', value: 'xgboost' }] },
      { name: 'feature', label: '分析特征', type: 'string', default: '' },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'calibration',
    label: '校准曲线',
    category: '模型评估',
    params: [
      { name: 'modelType', label: '模型类型', type: 'select', default: 'logistic', options: [{ label: 'Logistic', value: 'logistic' }, { label: '随机森林', value: 'random-forest' }, { label: 'XGBoost', value: 'xgboost' }] },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'dca',
    label: 'DCA曲线',
    category: '模型评估',
    params: [
      { name: 'modelType', label: '模型类型', type: 'select', default: 'logistic', options: [{ label: 'Logistic', value: 'logistic' }, { label: '随机森林', value: 'random-forest' }, { label: 'XGBoost', value: 'xgboost' }] },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
  {
    key: 'bootstrap',
    label: 'Bootstrap验证',
    category: '模型验证',
    params: [
      { name: 'modelType', label: '模型类型', type: 'select', default: 'logistic', options: [{ label: 'Logistic', value: 'logistic' }, { label: '随机森林', value: 'random-forest' }] },
      { name: 'nBootstrap', label: 'Bootstrap次数', type: 'number', default: 200, min: 50, max: 2000, step: 50 },
      { name: 'testSize', label: '测试集比例', type: 'slider', default: 0.3, min: 0.1, max: 0.5, step: 0.05 },
      { name: 'seed', label: '随机数种子', type: 'number', default: 123, min: 1, max: 9999, step: 1 },
    ],
  },
];
