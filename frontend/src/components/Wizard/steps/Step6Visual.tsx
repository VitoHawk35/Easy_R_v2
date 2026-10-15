import React, { useState, useMemo } from 'react';
import { Card, Checkbox, Button, Space, message, Tabs, Slider, InputNumber, Tag, Divider, Alert } from 'antd';
import { PlayCircleOutlined, CalculatorOutlined } from '@ant-design/icons';
import { useWizard } from '@/context/WizardContext';
import { runML } from '@/services/api';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';
import { buildVariableTypes } from '@/types';

const Step6Visual: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, filterResults, bestModel, modelInfo, allVariables } = state;
  const [vizOptions, setVizOptions] = useState<string[]>(['forest', 'roc', 'calibration', 'dca']);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('viz');

  const finalVars = filterResults.final.length > 0 ? filterResults.final : state.allVariables.map((v) => v.name).filter((n) => n !== yVariable && n !== timeVariable);

  // Web calculator state
  const [calcValues, setCalcValues] = useState<Record<string, number>>({});

  const hasCoefficients = modelInfo && modelInfo.coefficients && modelInfo.intercept !== undefined;
  const modelType = modelInfo?.model_type || bestModel;

  // Initialize calc values from modelInfo ranges or variable ranges
  const variableRanges = useMemo(() => {
    const ranges: Record<string, { min: number; max: number }> = {};
    if (modelInfo?.ranges) {
      Object.entries(modelInfo.ranges).forEach(([k, v]: [string, any]) => {
        ranges[k] = { min: v[0], max: v[1] };
      });
    } else {
      allVariables.forEach((v) => {
        if (finalVars.includes(v.name)) {
          const parts = v.range_str.split(' ~ ');
          if (parts.length === 2) {
            const min = parseFloat(parts[0]);
            const max = parseFloat(parts[1]);
            if (!isNaN(min) && !isNaN(max)) {
              ranges[v.name] = { min, max };
            }
          }
        }
      });
    }
    return ranges;
  }, [modelInfo, allVariables, finalVars]);

  // Initialize default slider values once
  React.useEffect(() => {
    if (Object.keys(calcValues).length === 0 && Object.keys(variableRanges).length > 0) {
      const defaults: Record<string, number> = {};
      Object.entries(variableRanges).forEach(([k, v]) => {
        defaults[k] = parseFloat(((v.min + v.max) / 2).toFixed(2));
      });
      setCalcValues(defaults);
    }
  }, [variableRanges]);

  const calculatedProbability = useMemo(() => {
    if (!hasCoefficients) return null;
    const coeffs = modelInfo.coefficients as Record<string, number>;
    let lp = modelInfo.intercept as number;
    Object.entries(coeffs).forEach(([varName, coef]) => {
      const val = calcValues[varName] || 0;
      lp += coef * val;
    });
    if (modelType === 'logistic') {
      const prob = 1 / (1 + Math.exp(-lp));
      return { lp, prob };
    }
    return { lp, prob: null };
  }, [calcValues, modelInfo, hasCoefficients, modelType]);

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
        const res = await runML('nomogram', buildRequest({
          ...basePayload,
          params: { modelType: bestModel, testSize: 0.3, format: 'svg' }
        } as any));
        allResults.charts.push(...res.charts);
        allResults.tables.push(...res.tables);
        if (res.model_info) {
          dispatch({ type: 'SET_MODEL_INFO', payload: { ...modelInfo, ...res.model_info } });
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
            {!hasCoefficients ? (
              <Alert
                message="Web计算器暂不可用"
                description="当前模型类型不支持在线预测计算器（需要线性系数模型，如Logistic回归、LASSO、弹性网络）。请在模型构建步骤选择支持系数的模型，或先生成Nomogram以获取系数。"
                type="warning"
                showIcon
              />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ marginBottom: 8 }}>
                  <Tag color="green">模型: {bestModel}</Tag>
                  <Tag color="blue">截距: {(modelInfo.intercept as number).toFixed(4)}</Tag>
                </div>
                {Object.entries(variableRanges).map(([varName, range]) => {
                  const val = calcValues[varName] ?? (range.min + range.max) / 2;
                  const coef = (modelInfo.coefficients as Record<string, number>)[varName] || 0;
                  return (
                    <div key={varName} style={{ marginBottom: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <strong>{varName}</strong>
                        <span style={{ color: '#666' }}>
                          β={coef.toFixed(3)} | 值: {val.toFixed(2)}
                        </span>
                      </div>
                      <Slider
                        min={range.min}
                        max={range.max}
                        step={(range.max - range.min) / 100}
                        value={val}
                        onChange={(v) => setCalcValues((prev) => ({ ...prev, [varName]: v }))}
                        tooltip={{ formatter: (v) => String(v) }}
                      />
                    </div>
                  );
                })}
                <Divider />
                {calculatedProbability && (
                  <div style={{ textAlign: 'center', padding: 16, background: '#f6ffed', borderRadius: 8, border: '1px solid #b7eb8f' }}>
                    <div style={{ fontSize: 14, color: '#666' }}>预测概率</div>
                    <div style={{ fontSize: 36, fontWeight: 'bold', color: '#2f855a' }}>
                      {calculatedProbability.prob !== null
                        ? `${(calculatedProbability.prob * 100).toFixed(2)}%`
                        : calculatedProbability.lp.toFixed(3)}
                    </div>
                    <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                      线性预测值 (LP): {calculatedProbability.lp.toFixed(4)}
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
