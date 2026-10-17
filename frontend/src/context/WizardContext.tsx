import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import type { WizardState, MLResult, DatasetInfo, VariableInfo, DiagnosisConfig, FilterConfig, FilterResults, DataTransformConfig, DataTransformResponse } from '@/types';

export const WIZARD_STORAGE_KEY = 'easyr_wizard_v1';

/** 统一构造空的筛选结果，避免多处共享同一对象引用 */
export function emptyFilterResults(): FilterResults {
  return { univariate: [], lasso: [], rf: [], boruta: [], final: [] };
}

/** 去掉图表（SVG）数据；持久化与 buildRequest 共用此函数（E4a / E4f） */
function stripCharts(result: MLResult | null): MLResult | null {
  if (!result) return result;
  return { ...result, charts: [] };
}

/**
 * 序列化向导状态：
 * - 去掉所有 SVG/图表数据和 previewData，控制 sessionStorage 与请求体体积；
 * - Set 转为数组，便于 JSON 存储。
 */
export function serializeWizardState(state: WizardState): any {
  return JSON.parse(JSON.stringify({
    ...state,
    previewData: [],
    diagnosisResult: stripCharts(state.diagnosisResult),
    buildResult: stripCharts(state.buildResult),
    evalResults: stripCharts(state.evalResults),
    vizResults: stripCharts(state.vizResults),
    explainResults: stripCharts(state.explainResults),
    advDiagResults: stripCharts(state.advDiagResults),
    validationResults: stripCharts(state.validationResults),
    completedSteps: Array.from(state.completedSteps),
    staleSteps: Array.from(state.staleSteps || []),
  }));
}

export function deserializeWizardState(snapshot: any): Partial<WizardState> {
  if (!snapshot || typeof snapshot !== 'object') return {};
  return {
    ...snapshot,
    previewData: [],
    transformConfig: { ...initialState.transformConfig, ...(snapshot.transformConfig || {}) },
    diagnosisConfig: { ...initialState.diagnosisConfig, ...(snapshot.diagnosisConfig || {}) },
    filterConfig: { ...initialState.filterConfig, ...(snapshot.filterConfig || {}) },
    filterResults: { ...emptyFilterResults(), ...(snapshot.filterResults || {}) },
    idVariables: snapshot.idVariables || [],
    modelFeatures: snapshot.modelFeatures || [],
    completedSteps: new Set(snapshot.completedSteps || []),
    staleSteps: new Set(snapshot.staleSteps || []),
  };
}

/**
 * 从 sessionStorage 读取上次的向导状态。
 * D8 已决：刷新后仍需重新登录，登录成功后由此恢复向导。
 */
export function loadPersistedWizardState(): Partial<WizardState> | null {
  try {
    if (typeof sessionStorage === 'undefined') return null;
    const raw = sessionStorage.getItem(WIZARD_STORAGE_KEY);
    if (!raw) return null;
    return deserializeWizardState(JSON.parse(raw));
  } catch {
    return null;
  }
}

export const initialState: WizardState = {
  datasetId: '',
  datasetInfo: null,
  previewData: [],
  previewColumns: [],
  yVariable: '',
  isSurvival: false,
  timeVariable: '',
  groupVariable: '',
  idVariables: [],
  allVariables: [],
  transformConfig: {
    dataset_id: '',
    method: 'alr',
    peak_variables: [],
    reference_variable: '',
    y_variable: '',
    cv_threshold: 0.15,
    p_threshold: 0.05,
    p_operator: 'gt',
    pvalue_test: 'auto',
    zero_strategy: 'pseudocount',
    pseudocount: 1e-6,
    output_name: '',
  },
  transformResult: null,
  diagnosisConfig: { vifThreshold: 5, corrThreshold: 0.7, autoRemove: true },
  diagnosisResult: null,
  removedVars: [],
  filterConfig: {
    useUnivariate: true, univariateP: 0.1,
    useLasso: true, lassoLambda: 'min',
    useRF: true, rfTopK: 10,
    useBoruta: true, borutaRuns: 100, borutaP: 0.05,
  },
  filterResults: emptyFilterResults(),
  buildMode: 'single',
  selectedModel: '',
  compareModels: [],
  forcedIncludeVars: [],
  modelParams: {},
  modelFeatures: [],
  buildResult: null,
  modelInfo: null,
  bestModel: '',
  evalResults: null,
  vizResults: null,
  explainResults: null,
  advDiagResults: null,
  validationResults: null,
  currentStep: 0,
  completedSteps: new Set(),
  staleSteps: new Set(),
};

/** 每次新建一份独立默认状态（RESET / Provider 初始化用） */
export function createDefaultState(): WizardState {
  return {
    ...initialState,
    transformConfig: { ...initialState.transformConfig },
    diagnosisConfig: { ...initialState.diagnosisConfig },
    filterConfig: { ...initialState.filterConfig },
    filterResults: emptyFilterResults(),
    compareModels: [],
    forcedIncludeVars: [],
    modelParams: {},
    modelFeatures: [],
    idVariables: [],
    allVariables: [],
    previewData: [],
    previewColumns: [],
    completedSteps: new Set(),
    staleSteps: new Set(),
  };
}

/**
 * 上游变更后需要清空的结果字段（key = 被影响步骤的 0 基下标）。
 * 1=变量诊断，2=变量筛选，3=模型构建，4=模型评估 … 8=模型验证。
 */
const RESULT_FIELDS_BY_STEP: Record<number, Array<keyof WizardState>> = {
  1: ['diagnosisResult', 'removedVars'],
  2: ['filterResults'],
  3: ['buildResult', 'modelInfo', 'bestModel', 'modelParams', 'modelFeatures'],
  4: ['evalResults'],
  5: ['vizResults'],
  6: ['explainResults'],
  7: ['advDiagResults'],
  8: ['validationResults'],
};

function emptyField(field: keyof WizardState): any {
  switch (field) {
    case 'filterResults':
      return emptyFilterResults();
    case 'removedVars':
    case 'modelFeatures':
      return [];
    case 'modelParams':
      return {};
    case 'bestModel':
      return '';
    default:
      return null;
  }
}

function hasValue(value: any): boolean {
  if (Array.isArray(value)) return value.length > 0;
  if (value instanceof Set) return value.size > 0;
  if (value && typeof value === 'object') return true;
  return value !== null && value !== undefined && value !== '';
}

/**
 * 从 fromStep（0 基）开始清空该步及之后所有步骤的结果字段，
 * 并把此前已完成的步骤标记为“需重跑”。
 */
export function invalidateFrom(state: WizardState, fromStep: number): WizardState {
  const next: any = { ...state };
  for (let step = fromStep; step <= 9; step++) {
    for (const field of RESULT_FIELDS_BY_STEP[step] || []) {
      next[field] = emptyField(field);
    }
  }

  // 已完成的步骤被上游改动影响后，从完成列表中移除并记为“需重跑”
  const completedSteps = new Set([...state.completedSteps].filter((s) => s < fromStep));
  const staleSteps = new Set(state.staleSteps || []);
  for (const s of state.completedSteps) {
    if (s >= fromStep) staleSteps.add(s);
  }
  for (let step = fromStep; step <= 9; step++) {
    if ((RESULT_FIELDS_BY_STEP[step] || []).some((field) => hasValue(state[field]))) {
      staleSteps.add(step);
    }
  }

  return { ...next, completedSteps, staleSteps };
}

/**
 * 统一特征候选：排除 Y、生存时间、分组变量、名为 id 的列，以及用户标记为 ID 的列。
 * Step2/Step3 与 Step4–9 的“回退到全部变量”分支都使用它（E4d）。
 */
export function featureCandidates(state: WizardState): string[] {
  const excluded = new Set(
    [state.yVariable, state.timeVariable, state.groupVariable, ...(state.idVariables || [])]
      .filter(Boolean),
  );
  return state.allVariables
    .map((v) => v.name)
    .filter((name) => Boolean(name) && !excluded.has(name) && !/^id$/i.test(name));
}

/**
 * 第 5–9 步实际用于建模/评估的特征集。
 * 优先使用 Step4 建模成功时保存的 modelFeatures（含强制纳入变量）；旧快照回退。
 */
export function effectiveModelFeatures(state: WizardState): string[] {
  if (state.modelFeatures.length > 0) return state.modelFeatures;
  const candidates = featureCandidates(state);
  const fallback = state.filterResults.final.length > 0 ? state.filterResults.final : candidates;
  return fallback.filter((name) => candidates.includes(name));
}

function sameStringArray(a: string[] = [], b: string[] = []): boolean {
  if (a.length !== b.length) return false;
  return a.every((value, index) => value === b[index]);
}

function sameFilterResults(a: FilterResults, b: FilterResults): boolean {
  return (['univariate', 'lasso', 'rf', 'boruta', 'final'] as const)
    .every((key) => sameStringArray(a[key], b[key]));
}

type Action =
  | { type: 'SET_DATASET'; payload: { id: string; info: DatasetInfo | null } }
  | { type: 'SET_PREVIEW'; payload: { columns: string[]; data: any[] } }
  | { type: 'SET_Y_VARIABLE'; payload: string }
  | { type: 'SET_SURVIVAL'; payload: { isSurvival: boolean; timeVariable: string } }
  | { type: 'SET_GROUP_VARIABLE'; payload: string }
  | { type: 'SET_ID_VARIABLES'; payload: string[] }
  | { type: 'SET_ALL_VARIABLES'; payload: VariableInfo[] }
  | { type: 'SET_TRANSFORM_CONFIG'; payload: Partial<DataTransformConfig> }
  | { type: 'SET_TRANSFORM_RESULT'; payload: DataTransformResponse | null }
  | { type: 'SET_DIAGNOSIS_CONFIG'; payload: Partial<DiagnosisConfig> }
  | { type: 'SET_DIAGNOSIS_RESULT'; payload: MLResult | null }
  | { type: 'SET_REMOVED_VARS'; payload: string[] }
  | { type: 'SET_FILTER_CONFIG'; payload: Partial<FilterConfig> }
  | { type: 'SET_FILTER_RESULTS'; payload: FilterResults }
  | { type: 'SET_BUILD_MODE'; payload: 'single' | 'compare' }
  | { type: 'SET_SELECTED_MODEL'; payload: string }
  | { type: 'SET_COMPARE_MODELS'; payload: string[] }
  | { type: 'SET_FORCED_INCLUDE_VARS'; payload: string[] }
  | { type: 'SET_MODEL_PARAMS'; payload: Record<string, any> }
  | { type: 'SET_MODEL_FEATURES'; payload: string[] }
  | { type: 'SET_BUILD_RESULT'; payload: MLResult | null }
  | { type: 'SET_MODEL_INFO'; payload: Record<string, any> | null }
  | { type: 'SET_BEST_MODEL'; payload: string }
  | { type: 'SET_EVAL_RESULTS'; payload: MLResult | null }
  | { type: 'SET_VIZ_RESULTS'; payload: MLResult | null }
  | { type: 'SET_EXPLAIN_RESULTS'; payload: MLResult | null }
  | { type: 'SET_ADV_DIAG_RESULTS'; payload: MLResult | null }
  | { type: 'SET_VALIDATION_RESULTS'; payload: MLResult | null }
  | { type: 'SET_STEP'; payload: number }
  | { type: 'MARK_STEP_COMPLETE'; payload: number }
  | { type: 'UNMARK_STEP_COMPLETE'; payload: number }
  | { type: 'RESTORE_SNAPSHOT'; payload: any }
  | { type: 'RESET' };

export function wizardReducer(state: WizardState, action: Action): WizardState {
  switch (action.type) {
    case 'SET_DATASET': {
      const next = { ...state, datasetId: action.payload.id, datasetInfo: action.payload.info };
      if (state.datasetId === action.payload.id) return next;
      return invalidateFrom(next, 1);
    }
    case 'SET_PREVIEW':
      return { ...state, previewColumns: action.payload.columns, previewData: action.payload.data };
    case 'SET_Y_VARIABLE': {
      if (state.yVariable === action.payload) return state;
      return invalidateFrom({ ...state, yVariable: action.payload }, 1);
    }
    case 'SET_SURVIVAL': {
      if (state.isSurvival === action.payload.isSurvival && state.timeVariable === action.payload.timeVariable) {
        return state;
      }
      return invalidateFrom({
        ...state,
        isSurvival: action.payload.isSurvival,
        timeVariable: action.payload.timeVariable,
      }, 1);
    }
    case 'SET_GROUP_VARIABLE': {
      if (state.groupVariable === action.payload) return state;
      return invalidateFrom({ ...state, groupVariable: action.payload }, 1);
    }
    case 'SET_ID_VARIABLES': {
      if (sameStringArray(state.idVariables, action.payload)) return state;
      return invalidateFrom({ ...state, idVariables: action.payload }, 1);
    }
    case 'SET_ALL_VARIABLES':
      // 变量元数据刷新（进入向导/重新登录恢复）不应清空已有分析结果
      return { ...state, allVariables: action.payload };
    case 'SET_TRANSFORM_CONFIG':
      return { ...state, transformConfig: { ...state.transformConfig, ...action.payload } };
    case 'SET_TRANSFORM_RESULT':
      return { ...state, transformResult: action.payload };
    case 'SET_DIAGNOSIS_CONFIG':
      return { ...state, diagnosisConfig: { ...state.diagnosisConfig, ...action.payload } };
    case 'SET_DIAGNOSIS_RESULT':
      return { ...state, diagnosisResult: action.payload };
    case 'SET_REMOVED_VARS': {
      if (sameStringArray(state.removedVars, action.payload)) return state;
      return invalidateFrom({ ...state, removedVars: action.payload }, 2);
    }
    case 'SET_FILTER_CONFIG':
      return { ...state, filterConfig: { ...state.filterConfig, ...action.payload } };
    case 'SET_FILTER_RESULTS': {
      if (sameFilterResults(state.filterResults, action.payload)) return state;
      return invalidateFrom({ ...state, filterResults: action.payload }, 3);
    }
    case 'SET_BUILD_MODE': {
      if (state.buildMode === action.payload) return state;
      return invalidateFrom({ ...state, buildMode: action.payload }, 4);
    }
    case 'SET_SELECTED_MODEL': {
      if (state.selectedModel === action.payload) return state;
      return invalidateFrom({ ...state, selectedModel: action.payload }, 4);
    }
    case 'SET_COMPARE_MODELS': {
      if (sameStringArray(state.compareModels, action.payload)) return state;
      return invalidateFrom({ ...state, compareModels: action.payload }, 4);
    }
    case 'SET_FORCED_INCLUDE_VARS': {
      if (sameStringArray(state.forcedIncludeVars, action.payload)) return state;
      return invalidateFrom({ ...state, forcedIncludeVars: action.payload }, 3);
    }
    case 'SET_MODEL_PARAMS': {
      const modelParams = { ...state.modelParams, ...action.payload };
      if (JSON.stringify(modelParams) === JSON.stringify(state.modelParams)) return state;
      return invalidateFrom({ ...state, modelParams }, 4);
    }
    case 'SET_MODEL_FEATURES': {
      if (sameStringArray(state.modelFeatures, action.payload)) return state;
      return invalidateFrom({ ...state, modelFeatures: action.payload }, 4);
    }
    case 'SET_BUILD_RESULT':
      return invalidateFrom({ ...state, buildResult: action.payload }, 4);
    case 'SET_MODEL_INFO':
      return { ...state, modelInfo: action.payload };
    case 'SET_BEST_MODEL': {
      if (state.bestModel === action.payload) return state;
      return invalidateFrom({ ...state, bestModel: action.payload }, 4);
    }
    case 'SET_EVAL_RESULTS':
      return { ...state, evalResults: action.payload };
    case 'SET_VIZ_RESULTS':
      return { ...state, vizResults: action.payload };
    case 'SET_EXPLAIN_RESULTS':
      return { ...state, explainResults: action.payload };
    case 'SET_ADV_DIAG_RESULTS':
      return { ...state, advDiagResults: action.payload };
    case 'SET_VALIDATION_RESULTS':
      return { ...state, validationResults: action.payload };
    case 'SET_STEP':
      return { ...state, currentStep: action.payload };
    case 'MARK_STEP_COMPLETE':
      return {
        ...state,
        completedSteps: new Set([...state.completedSteps, action.payload]),
        staleSteps: new Set([...state.staleSteps].filter((s) => s !== action.payload)),
      };
    case 'UNMARK_STEP_COMPLETE': {
      const next = new Set([...state.completedSteps]);
      next.delete(action.payload);
      return { ...state, completedSteps: next };
    }
    case 'RESTORE_SNAPSHOT':
      return { ...createDefaultState(), ...deserializeWizardState(action.payload) };
    case 'RESET':
      return createDefaultState();
    default:
      return state;
  }
}

interface WizardContextValue {
  state: WizardState;
  dispatch: React.Dispatch<Action>;
  goToStep: (step: number) => void;
  markComplete: (step: number) => void;
  unmarkComplete: (step: number) => void;
  buildRequest: (base: Record<string, any>) => any;
}

const WizardContext = createContext<WizardContextValue | null>(null);

export const WizardProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(
    wizardReducer,
    undefined,
    () => ({ ...createDefaultState(), ...(loadPersistedWizardState() || {}) }) as WizardState,
  );

  // E4a：向导状态持久化到 sessionStorage（不含 SVG/图表数据与 previewData）
  useEffect(() => {
    try {
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem(WIZARD_STORAGE_KEY, JSON.stringify(serializeWizardState(state)));
      }
    } catch {
      // 存储空间不足或隐私模式：忽略，不影响正常流程
    }
  }, [state]);

  const goToStep = useCallback((step: number) => {
    if (step >= 0 && step <= 9) {
      dispatch({ type: 'SET_STEP', payload: step });
    }
  }, []);

  const markComplete = useCallback((step: number) => {
    dispatch({ type: 'MARK_STEP_COMPLETE', payload: step });
  }, []);

  const unmarkComplete = useCallback((step: number) => {
    dispatch({ type: 'UNMARK_STEP_COMPLETE', payload: step });
  }, []);

  // E4f：请求体只带精简快照（与 sessionStorage 持久化使用同一序列化函数）
  const buildRequest = useCallback((base: Record<string, any>) => {
    return {
      ...base,
      wizard_snapshot: serializeWizardState(state),
    };
  }, [state]);

  return (
    <WizardContext.Provider value={{ state, dispatch, goToStep, markComplete, unmarkComplete, buildRequest }}>
      {children}
    </WizardContext.Provider>
  );
};

export function useWizard() {
  const ctx = useContext(WizardContext);
  if (!ctx) throw new Error('useWizard must be used within WizardProvider');
  return ctx;
}
