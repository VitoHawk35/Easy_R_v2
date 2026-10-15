import React, { createContext, useContext, useReducer, useCallback } from 'react';
import type { WizardState, MLResult, DatasetInfo, VariableInfo, DiagnosisConfig, FilterConfig, FilterResults, DataTransformConfig, DataTransformResponse } from '@/types';

export function serializeWizardState(state: WizardState): any {
  return JSON.parse(JSON.stringify({
    ...state,
    completedSteps: Array.from(state.completedSteps),
  }));
}

function deserializeWizardState(snapshot: any): Partial<WizardState> {
  return {
    ...snapshot,
    completedSteps: new Set(snapshot.completedSteps || []),
  };
}

const initialState: WizardState = {
  datasetId: '',
  datasetInfo: null,
  previewData: [],
  previewColumns: [],
  yVariable: '',
  isSurvival: false,
  timeVariable: '',
  groupVariable: '',
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
    useRF: true,
    useBoruta: true, borutaRuns: 100, borutaP: 0.05,
  },
  filterResults: { univariate: [], lasso: [], rf: [], boruta: [], final: [] },
  buildMode: 'single',
  selectedModel: '',
  compareModels: [],
  forcedIncludeVars: [],
  modelParams: {},
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
};

type Action =
  | { type: 'SET_DATASET'; payload: { id: string; info: DatasetInfo | null } }
  | { type: 'SET_PREVIEW'; payload: { columns: string[]; data: any[] } }
  | { type: 'SET_Y_VARIABLE'; payload: string }
  | { type: 'SET_SURVIVAL'; payload: { isSurvival: boolean; timeVariable: string } }
  | { type: 'SET_GROUP_VARIABLE'; payload: string }
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

function wizardReducer(state: WizardState, action: Action): WizardState {
  switch (action.type) {
    case 'SET_DATASET':
      return { ...state, datasetId: action.payload.id, datasetInfo: action.payload.info };
    case 'SET_PREVIEW':
      return { ...state, previewColumns: action.payload.columns, previewData: action.payload.data };
    case 'SET_Y_VARIABLE':
      return { ...state, yVariable: action.payload };
    case 'SET_SURVIVAL':
      return { ...state, isSurvival: action.payload.isSurvival, timeVariable: action.payload.timeVariable };
    case 'SET_GROUP_VARIABLE':
      return { ...state, groupVariable: action.payload };
    case 'SET_ALL_VARIABLES':
      return { ...state, allVariables: action.payload };
    case 'SET_TRANSFORM_CONFIG':
      return { ...state, transformConfig: { ...state.transformConfig, ...action.payload } };
    case 'SET_TRANSFORM_RESULT':
      return { ...state, transformResult: action.payload };
    case 'SET_DIAGNOSIS_CONFIG':
      return { ...state, diagnosisConfig: { ...state.diagnosisConfig, ...action.payload } };
    case 'SET_DIAGNOSIS_RESULT':
      return { ...state, diagnosisResult: action.payload };
    case 'SET_REMOVED_VARS':
      return { ...state, removedVars: action.payload };
    case 'SET_FILTER_CONFIG':
      return { ...state, filterConfig: { ...state.filterConfig, ...action.payload } };
    case 'SET_FILTER_RESULTS':
      return { ...state, filterResults: action.payload };
    case 'SET_BUILD_MODE':
      return { ...state, buildMode: action.payload };
    case 'SET_SELECTED_MODEL':
      return { ...state, selectedModel: action.payload };
    case 'SET_COMPARE_MODELS':
      return { ...state, compareModels: action.payload };
    case 'SET_FORCED_INCLUDE_VARS':
      return { ...state, forcedIncludeVars: action.payload };
    case 'SET_MODEL_PARAMS':
      return { ...state, modelParams: { ...state.modelParams, ...action.payload } };
    case 'SET_BUILD_RESULT':
      return { ...state, buildResult: action.payload };
    case 'SET_MODEL_INFO':
      return { ...state, modelInfo: action.payload };
    case 'SET_BEST_MODEL':
      return { ...state, bestModel: action.payload };
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
      return { ...state, completedSteps: new Set([...state.completedSteps, action.payload]) };
    case 'UNMARK_STEP_COMPLETE': {
      const next = new Set([...state.completedSteps]);
      next.delete(action.payload);
      return { ...state, completedSteps: next };
    }
    case 'RESTORE_SNAPSHOT':
      return { ...initialState, ...deserializeWizardState(action.payload) };
    case 'RESET':
      return initialState;
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
  const [state, dispatch] = useReducer(wizardReducer, initialState);

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
