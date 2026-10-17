import React, { useState, useMemo } from 'react';
import { Card, Checkbox, Button, Space, message, Tabs, InputNumber, Select, Tag, Alert } from 'antd';
import { PlayCircleOutlined, CalculatorOutlined } from '@ant-design/icons';
import { useWizard } from '@/context/WizardContext';
import { runML, predict } from '@/services/api';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';
import { buildVariableTypes, type PredictionResponse } from '@/types';

// E3a：只有这些线性二分类模型支持原始尺度计算器/列线图
const CALCULATOR_MODELS = ['logistic', 'lasso', 'lasso-predict', 'elastic-net'];

interface CalcField {
  name: string;
  kind: 'continuous' | 'categorical';
  min?: number;
  max?: number;
  levels: string[];
}

const Step6Visual: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, filterResults, bestModel, modelInfo, modelParams, allVariables } = state;
  const [vizOptions, setVizOptions] = useState<string[]>(['forest', 'roc', 'calibration', 'dca']);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('viz');

  const finalVars = filterResults.final.length > 0 ? filterResults.final : state.allVariables.map((v) => v.name).filter((n) => n !== yVariable && n !== timeVariable);
  const modelType = modelInfo?.model_type || bestModel;
  const calculatorSupported = CALCULATOR_MODELS.includes(bestModel) || CALCULATOR_MODELS.includes(modelType);

  // E3a Web 计算器状态：表单值 + 后端预测结果（不在前端还原系数）
  const [calcValues, setCalcValues] = useState<Record<string, any>>({});
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [calcLoading, setCalcLoading] = useState(false);

  // 表单字段来自 allVariables 的变量类型/水平；分类变量用 Select，连续变量用 InputNumber
  const calcFields = useMemo<CalcField[]>(() => {
    return finalVars.map((name) => {
      const v = allVariables.find((item) => item.name === name);
      if (!v) return { name, kind: 'continuous', min: 0, max: 1, levels: [] };
      if (v.type === 'categorical' || v.type === 'logical') {
        return { name, kind: 'categorical', levels: v.levels || [] };
      }
      let min = v.min_value ?? undefined;
      let max = v.max_value ?? undefined;
      if (min === undefined || max === undefined) {
        // 兼容旧后端：range_str 形如 "3.22-74.00连续"
        const m = v.range_str.match(/(-?\d+(?:\.\d+)?)\s*[-~]\s*(-?\d+(?:\.\d+)?)/);
        if (m) {
          min = parseFloat(m[1]);
          max = parseFloat(m[2]);
        }
      }
      return { name, kind: 'continuous', min: min ?? 0, max: max ?? 1, levels: [] };
    });
  }, [finalVars, allVariables]);

  // 初始化默认值（连续变量取范围中点，分类变量取第一个水平）
  React.useEffect(() => {
    setCalcValues((prev) => {
      const next = { ...prev };
      calcFields.forEach((f) => {
        if (next[f.name] !== undefined) return;
        if (f.kind === 'categorical') {
          next[f.name] = f.levels[0] ?? '';
        } else {
          next[f.name] = parseFloat((((f.min ?? 0) + (f.max ?? 1)) / 2).toFixed(4));
        }
      });
      return next;
    });
  }, [calcFields]);

  const runCalculator = async () => {
    if (!datasetId || !yVariable || !bestModel) {
      message.error('请先完成模型构建步骤');
      return;
    }
    setCalcLoading(true);
    try {
      const modelP = modelParams[bestModel] || modelParams[modelType] || {};
      const res = await predict(buildRequest({
        dataset_id: datasetId,
        y_variable: yVariable,
        is_survival: isSurvival,
        time_variable: timeVariable || undefined,
        x_variables: finalVars,
        filters: [],
        params: {
          ...modelP,
          modelType: bestModel || modelType,
          input: calcValues,
          format: 'svg',
        },
        seed: modelP.seed || 123,
        variable_types: buildVariableTypes(allVariables),
      } as any));
      setPrediction(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '预测失败');
    } finally {
      setCalcLoading(false);
    }
  };

  const runVisual = async () => {
    if (!datasetId || !yVariable || !bestModel) {
      message.error('请先完成模型构建步骤');
      return;
    }
    setLoading(true);
    const allResults: any = { charts: [], tables: [], summary: '', success: true };
    try {
      const basePayload = {
        dataset_id: datasetId,
        y_variable: yVariable,
        is_survival: isSurvival,
        time_variable: timeVariable || undefined,
        x_variables: finalVars,
        filters: [],
        seed: 123,
        variable_types: buildVariableTypes(state.allVariables),
      };

      if (vizOptions.includes('nomogram')) {
        const modelP = modelParams[bestModel] || {};
        const res = await runML('nomogram', buildRequest({
          ...basePayload,
          params: { ...modelP, modelType: bestModel, modelParams: modelParams, testSize: 0.3, format: 'svg' }
        } as any));
        allResults.charts.push(...res.charts);
        allResults.tables.push(...res.tables);
        if (res.model_info) {
          dispatch({ type: 'SET_MODEL_INFO', payload: { ...(modelInfo || {}), ...res.model_info } });
        }
      }
      if (vizOptions.includes('forest')) {
        const allCharts = state.buildResult?.charts || [];
        const forestCharts = allCharts.filter((c: any) =>
          /重要性|importance|森林|forest/i.test(c.title || '')
        );
        if (forestCharts.length > 0) {
          allResults.charts.push(...forestCharts);
        } else if (allCharts.length > 0) {
          // fallback: 模型 service 把重要性嵌在汇总图里，直接展示训练结果图
          allResults.charts.push(...allCharts);
        } else {
          message.warning('变量重要性森林图未在模型训练结果中找到');
        }
      }
      if (vizOptions.includes('roc')) {
        const allCharts = state.buildResult?.charts || [];
        const rocCharts = allCharts.filter((c: any) =>
          /roc|auc/i.test(c.title || '')
        );
        if (rocCharts.length > 0) {
          allResults.charts.push(...rocCharts);
        } else if (allCharts.length > 0) {
          // fallback: 模型 service 把 ROC 嵌在汇总图里，直接展示训练结果图
          allResults.charts.push(...allCharts);
        } else {
          message.warning('ROC曲线未在模型训练结果中找到');
        }
      }
      if (vizOptions.includes('calibration')) {
        const res = await runML('calibration', buildRequest({ ...basePayload, params: { modelType: bestModel, testSize: 0.3, format: 'svg' } } as any));
        allResults.charts.push(...res.charts);
      }
      if (vizOptions.includes('dca')) {
        const res = await runML('dca', buildRequest({ ...basePayload, params: { modelType: bestModel, testSize: 0.3, format: 'svg' } } as any));
        allResults.charts.push(...res.charts);
      }

      // 去重：基于 title 去除重复图表（forest 与 roc 都 fallback 到训练结果时会产生重复）
      const seenTitles = new Set<string>();
      allResults.charts = allResults.charts.filter((c: any) => {
        const key = c.title || '';
        if (seenTitles.has(key)) return false;
        seenTitles.add(key);
        return true;
      });

      dispatch({ type: 'SET_VIZ_RESULTS', payload: allResults });
      markComplete(5);
      message.success('可视化生成完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '可视化生成失败');
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'viz',
      label: '可视化选项',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Card title="可视化选项" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Checkbox.Group
                value={vizOptions}
                onChange={(vals) => setVizOptions(vals as string[])}
                options={[
                  { label: 'Nomogram列线图', value: 'nomogram' },
                  { label: '变量重要性森林图', value: 'forest' },
                  { label: 'ROC曲线对比', value: 'roc' },
                  { label: '校准曲线', value: 'calibration' },
                  { label: 'DCA曲线', value: 'dca' },
                ]}
              />
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={loading}
                onClick={runVisual}
                block
              >
                生成可视化
              </Button>
            </Space>
          </Card>

          {state.vizResults && <ResultDisplay result={state.vizResults} loading={false} />}
        </Space>
      ),
    },
    {
      key: 'calculator',
      label: (
        <span>
          <CalculatorOutlined /> Web计算器
        </span>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Card title="基于模型的在线预测计算器" size="small">
            {!calculatorSupported ? (
              <Alert
                message="Web计算器暂不可用"
                description="当前模型类型不支持在线预测计算器：仅支持 Logistic回归、LASSO、弹性网络。请重新训练模型或改用列线图支持的类型。"
                type="warning"
                showIcon
              />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ marginBottom: 8 }}>
                  <Tag color="green">模型: {bestModel || modelType}</Tag>
                  <Tag color="blue">原始尺度预测（后端 /api/ml/predict）</Tag>
                </div>
                {calcFields.map((f) => (
                  <div key={f.name} style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
                    <strong style={{ width: 140 }}>{f.name}</strong>
                    {f.kind === 'categorical' && f.levels.length > 0 ? (
                      <Select
                        style={{ width: 220 }}
                        value={calcValues[f.name]}
                        options={f.levels.map((lv) => ({ label: lv, value: lv }))}
                        onChange={(v) => setCalcValues((prev) => ({ ...prev, [f.name]: v }))}
                      />
                    ) : (
                      <InputNumber
                        style={{ width: 220 }}
                        min={f.min}
                        max={f.max}
                        step={(f.max !== undefined && f.min !== undefined && f.max > f.min) ? (f.max - f.min) / 100 : 0.01}
                        value={Number(calcValues[f.name])}
                        onChange={(v) => setCalcValues((prev) => ({ ...prev, [f.name]: v }))}
                      />
                    )}
                  </div>
                ))}
                <Button type="primary" icon={<CalculatorOutlined />} loading={calcLoading} onClick={runCalculator}>
                  计算
                </Button>
                {prediction && (
                  <div style={{ textAlign: 'center', padding: 16, background: '#f6ffed', borderRadius: 8, border: '1px solid #b7eb8f', marginTop: 12 }}>
                    <div style={{ fontSize: 14, color: '#666' }}>预测概率</div>
                    <div style={{ fontSize: 36, fontWeight: 'bold', color: '#2f855a' }}>
                      {(prediction.probability * 100).toFixed(2)}%
                    </div>
                    <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                      线性预测值 (LP): {prediction.linear_predictor.toFixed(4)}
                    </div>
                  </div>
                )}
              </Space>
            )}
          </Card>
        </Space>
      ),
    },
  ];

  return <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />;
};

export default Step6Visual;
