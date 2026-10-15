import React, { useState } from 'react';
import { Card, Checkbox, Radio, Slider, Button, Space, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { useWizard } from '@/context/WizardContext';
import { runML } from '@/services/api';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';
import { buildVariableTypes } from '@/types';

const Step5Eval: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, filterResults, bestModel, modelParams } = state;
  const [evalDataset, setEvalDataset] = useState<'test' | 'train' | 'both'>('test');
  const [metrics, setMetrics] = useState<string[]>(['roc', 'confusion', 'calibration', 'dca']);
  const [threshold, setThreshold] = useState(0.5);
  const [loading, setLoading] = useState(false);

  const finalVars = filterResults.final.length > 0 ? filterResults.final : state.allVariables.map((v) => v.name).filter((n) => n !== yVariable && n !== timeVariable);

  const runEval = async () => {
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

      const commonParams = {
        modelType: bestModel,
        testSize: evalDataset === 'train' ? 0.0 : 0.3,
        evalDataset,
        threshold,
        format: 'svg',
      };

      if (metrics.includes('roc')) {
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
          message.warning('ROC曲线未在模型训练结果中找到，请先完成模型构建');
        }
      }

      if (metrics.includes('confusion')) {
        const allTables = state.buildResult?.tables || [];
        const cmTables = allTables.filter((t: any) =>
          /混淆|confusion/i.test(t.title || '')
        );
        if (cmTables.length > 0) {
          allResults.tables.push(...cmTables);
        } else if (allTables.length > 0) {
          // fallback: 模型 service 把混淆矩阵嵌在汇总表里，展示训练结果表
          allResults.tables.push(...allTables);
        } else {
          message.warning('混淆矩阵未在模型训练结果中找到，请先完成模型构建');
        }
      }

      if (metrics.includes('brier')) {
        const brierRows = state.buildResult?.tables?.flatMap((t: any) => t.rows).filter((r: any) =>
          String(r[0]).toLowerCase().includes('brier')
        ) || [];
        if (brierRows.length > 0) {
          allResults.tables.push({ title: 'Brier分数', headers: ['Metric', 'Value'], rows: brierRows });
        } else {
          message.warning('Brier分数未在模型训练结果中找到');
        }
      }

      if (metrics.includes('calibration')) {
        const res = await runML('calibration', buildRequest({
          ...basePayload,
          params: commonParams,
        } as any));
        allResults.charts.push(...res.charts);
        allResults.tables.push(...res.tables);
        allResults.summary += res.summary + ' ';
      }

      if (metrics.includes('dca')) {
        const res = await runML('dca', buildRequest({
          ...basePayload,
          params: commonParams,
        } as any));
        allResults.charts.push(...res.charts);
        allResults.tables.push(...res.tables);
        allResults.summary += res.summary + ' ';
      }

      dispatch({ type: 'SET_EVAL_RESULTS', payload: allResults });
      markComplete(4);
      message.success('模型评估完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '评估失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="评估指标" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <strong>评估数据集:</strong>
            <Radio.Group value={evalDataset} onChange={(e) => setEvalDataset(e.target.value)} style={{ marginLeft: 12 }}>
              <Radio value="test">测试集</Radio>
              <Radio value="train">训练集</Radio>
              <Radio value="both">两者对比</Radio>
            </Radio.Group>
          </div>
          <div>
            <strong>选择指标:</strong>
            <Checkbox.Group
              value={metrics}
              onChange={(vals) => setMetrics(vals as string[])}
              style={{ marginLeft: 12 }}
              options={[
                { label: 'ROC曲线/AUC', value: 'roc' },
                { label: '混淆矩阵', value: 'confusion' },
                { label: '校准曲线', value: 'calibration' },
                { label: 'DCA曲线', value: 'dca' },
                { label: 'Brier分数', value: 'brier' },
              ]}
            />
          </div>
          <div>
            <strong>分类阈值:</strong>
            <Slider min={0} max={1} step={0.01} value={threshold} onChange={setThreshold} style={{ width: 200, marginLeft: 12 }} />
            <span style={{ marginLeft: 8 }}>{threshold}</span>
          </div>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={loading}
            onClick={runEval}
            block
          >
            运行评估
          </Button>
        </Space>
      </Card>

      {state.evalResults && <ResultDisplay result={state.evalResults} loading={false} />}
    </Space>
  );
};

export default Step5Eval;
