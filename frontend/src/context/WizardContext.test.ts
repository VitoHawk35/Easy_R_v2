import { describe, expect, it } from 'vitest';
import {
  createDefaultState,
  featureCandidates,
  invalidateFrom,
  serializeWizardState,
  wizardReducer,
} from './WizardContext';
import type { MLResult, VariableInfo, WizardState } from '@/types';

function variable(name: string): VariableInfo {
  return {
    name,
    type: 'continuous',
    range_str: '0 ~ 1',
    missing_count: 0,
    unique_count: 10,
  };
}

function mlResult(summary: string): MLResult {
  return {
    success: true,
    charts: [{ type: 'svg', title: 'chart', data: '<svg></svg>' }],
    tables: [],
    summary,
    download_urls: [],
  };
}

/** 构造一个“已经完成到第 9 步”的状态，用于验证失效逻辑 */
function completedState(): WizardState {
  const base = createDefaultState();
  return {
    ...base,
    datasetId: 'ds-1',
    datasetInfo: { id: 'ds-1', name: 'demo', rows: 100, cols: 8 },
    previewData: [{ age: 1 }],
    previewColumns: ['age'],
    yVariable: 'label',
    isSurvival: true,
    timeVariable: 'time',
    groupVariable: 'patient',
    idVariables: ['sample_id'],
    allVariables: [
      variable('label'),
      variable('time'),
      variable('patient'),
      variable('sample_id'),
      variable('id'),
      variable('ID'),
      variable('age'),
      variable('bmi'),
    ],
    diagnosisResult: mlResult('diagnosis'),
    removedVars: ['bmi'],
    filterResults: {
      univariate: ['age'],
      lasso: ['age'],
      rf: ['age'],
      boruta: ['age'],
      final: ['age', 'bmi'],
    },
    buildResult: mlResult('build'),
    modelInfo: { coefficients: { age: 0.1 }, intercept: 0 },
    bestModel: 'logistic',
    modelParams: { logistic: { C: 1 } },
    modelFeatures: ['age', 'bmi'],
    evalResults: mlResult('eval'),
    vizResults: mlResult('viz'),
    explainResults: mlResult('explain'),
    advDiagResults: mlResult('adv'),
    validationResults: mlResult('validation'),
    completedSteps: new Set([0, 1, 2, 3, 4, 5, 6, 7, 8]),
    staleSteps: new Set(),
  };
}

describe('featureCandidates (E4d)', () => {
  it('排除 Y、时间、分组、名为 id 的列和用户标记的 ID 列', () => {
    const state = completedState();
    expect(featureCandidates(state)).toEqual(['age', 'bmi']);
  });

  it('不区分大小写排除 id，且不误伤包含 id 的正常变量名', () => {
    const state = {
      ...createDefaultState(),
      allVariables: [variable('id'), variable('ID'), variable('idx'), variable('patient_id')],
    };
    // patient_id 只有用户显式标记才排除；这里未标记，应保留
    expect(featureCandidates(state)).toEqual(['idx', 'patient_id']);
  });
});

describe('invalidateFrom (E4b)', () => {
  it('从指定步骤起清空所有下游结果，并保留上游结果', () => {
    const state = completedState();
    const next = invalidateFrom(state, 2);

    // 上游（数据准备 + 诊断）保留
    expect(next.datasetId).toBe('ds-1');
    expect(next.diagnosisResult).toEqual(state.diagnosisResult);
    expect(next.removedVars).toEqual(['bmi']);

    // 第 2 步及之后全部清空
    expect(next.filterResults.final).toEqual([]);
    expect(next.buildResult).toBeNull();
    expect(next.modelInfo).toBeNull();
    expect(next.bestModel).toBe('');
    expect(next.modelParams).toEqual({});
    expect(next.modelFeatures).toEqual([]);
    expect(next.evalResults).toBeNull();
    expect(next.vizResults).toBeNull();
    expect(next.explainResults).toBeNull();
    expect(next.advDiagResults).toBeNull();
    expect(next.validationResults).toBeNull();

    // 完成标记只保留上游，下游标记为需重跑
    expect([...next.completedSteps]).toEqual([0, 1]);
    for (let step = 2; step <= 8; step += 1) {
      expect(next.staleSteps.has(step)).toBe(true);
    }
  });

  it('不修改传入的状态对象', () => {
    const state = completedState();
    const snapshot = JSON.stringify(serializeWizardState(state));
    invalidateFrom(state, 1);
    expect(JSON.stringify(serializeWizardState(state))).toBe(snapshot);
  });
});

describe('wizardReducer 上游变更失效 (E4b)', () => {
  it('修改 Y 后清空第 1–9 步的结果和完成标记', () => {
    const state = completedState();
    const next = wizardReducer(state, { type: 'SET_Y_VARIABLE', payload: 'new_label' });

    expect(next.yVariable).toBe('new_label');
    expect(next.diagnosisResult).toBeNull();
    expect(next.removedVars).toEqual([]);
    expect(next.filterResults.final).toEqual([]);
    expect(next.buildResult).toBeNull();
    expect(next.modelFeatures).toEqual([]);
    expect(next.evalResults).toBeNull();
    expect(next.vizResults).toBeNull();
    expect(next.explainResults).toBeNull();
    expect(next.advDiagResults).toBeNull();
    expect(next.validationResults).toBeNull();

    expect([...next.completedSteps]).toEqual([0]);
    for (let step = 1; step <= 8; step += 1) {
      expect(next.staleSteps.has(step)).toBe(true);
    }
  });

  it('Y 值未变化时不触发失效', () => {
    const state = completedState();
    const next = wizardReducer(state, { type: 'SET_Y_VARIABLE', payload: 'label' });
    expect(next).toBe(state);
  });

  it('剔除变量从第 2 步开始失效（保留诊断结果）', () => {
    const state = completedState();
    const next = wizardReducer(state, { type: 'SET_REMOVED_VARS', payload: ['bmi', 'age'] });
    expect(next.diagnosisResult).toEqual(state.diagnosisResult);
    expect(next.filterResults.final).toEqual([]);
    expect(next.buildResult).toBeNull();
    expect([...next.completedSteps]).toEqual([0, 1]);
    expect(next.staleSteps.has(2)).toBe(true);
  });

  it('筛选结果变化从第 3 步开始失效（保留诊断和筛选前的完成标记）', () => {
    const state = completedState();
    const next = wizardReducer(state, {
      type: 'SET_FILTER_RESULTS',
      payload: { univariate: ['age'], lasso: [], rf: [], boruta: [], final: ['age'] },
    });
    expect(next.diagnosisResult).toEqual(state.diagnosisResult);
    expect(next.filterResults.final).toEqual(['age']);
    expect(next.buildResult).toBeNull();
    expect([...next.completedSteps]).toEqual([0, 1, 2]);
    expect(next.staleSteps.has(3)).toBe(true);
  });

  it('强制纳入变量变化从第 3 步开始失效', () => {
    const state = completedState();
    const next = wizardReducer(state, { type: 'SET_FORCED_INCLUDE_VARS', payload: ['bmi'] });
    expect(next.buildResult).toBeNull();
    expect([...next.completedSteps]).toEqual([0, 1, 2]);
  });

  it('模型参数变化从第 4 步开始失效（保留第 4 步构建结果）', () => {
    const state = completedState();
    const next = wizardReducer(state, {
      type: 'SET_MODEL_PARAMS',
      payload: { logistic: { C: 0.5 } },
    });
    expect(next.buildResult).toEqual(state.buildResult);
    expect(next.modelParams.logistic.C).toBe(0.5);
    expect(next.evalResults).toBeNull();
    expect(next.vizResults).toBeNull();
    expect([...next.completedSteps]).toEqual([0, 1, 2, 3]);
    expect(next.staleSteps.has(4)).toBe(true);
  });

  it('相同值重复 dispatch 不清空下游', () => {
    const state = completedState();
    const nextParams = wizardReducer(state, {
      type: 'SET_MODEL_PARAMS',
      payload: { logistic: { C: 1 } },
    });
    expect(nextParams).toBe(state);

    const nextGroup = wizardReducer(state, { type: 'SET_GROUP_VARIABLE', payload: 'patient' });
    expect(nextGroup).toBe(state);
  });

  it('MARK_STEP_COMPLETE 会把“需重跑”恢复为已完成', () => {
    const state = invalidateFrom(completedState(), 4);
    expect(state.staleSteps.has(4)).toBe(true);
    const next = wizardReducer(state, { type: 'MARK_STEP_COMPLETE', payload: 4 });
    expect(next.completedSteps.has(4)).toBe(true);
    expect(next.staleSteps.has(4)).toBe(false);
  });
});

describe('serializeWizardState (E4a / E4f)', () => {
  it('去掉 previewData 和所有 SVG/图表数据，Set 转数组', () => {
    const state = completedState();
    const snapshot = serializeWizardState(state);

    expect(snapshot.previewData).toEqual([]);
    expect(snapshot.diagnosisResult.charts).toEqual([]);
    expect(snapshot.buildResult.charts).toEqual([]);
    expect(snapshot.evalResults.charts).toEqual([]);
    expect(snapshot.vizResults.charts).toEqual([]);
    expect(snapshot.explainResults.charts).toEqual([]);
    expect(snapshot.advDiagResults.charts).toEqual([]);
    expect(snapshot.validationResults.charts).toEqual([]);

    expect(snapshot.completedSteps).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8]);
    expect(Array.isArray(snapshot.staleSteps)).toBe(true);

    // 非图表信息仍保留
    expect(snapshot.diagnosisResult.summary).toBe('diagnosis');
    expect(snapshot.modelInfo.coefficients).toEqual({ age: 0.1 });
  });
});
