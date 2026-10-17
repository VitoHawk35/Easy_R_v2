import React, { useState } from 'react';
import { Card, Select, Button, Space, message, Tabs, Alert } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { useWizard, effectiveModelFeatures } from '@/context/WizardContext';
import { runML } from '@/services/api';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';
import { buildVariableTypes } from '@/types';

const Step7Explain: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, bestModel, modelParams } = state;
  const [activeTab, setActiveTab] = useState('shap');
  const [shapResult, setShapResult] = useState<any>(null);
  const [pdpResult, setPdpResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // E4c：使用 Step4 实际建模的特征集（含强制纳入变量）与超参数
  const finalVars = effectiveModelFeatures(state);
  const modelParamsPayload = { [bestModel]: modelParams[bestModel] || {} };
  const [pdpFeature, setPdpFeature] = useState(finalVars[0] || '');

  const runShap = async () => {
    if (!datasetId || !yVariable) return;
    setLoading(true);
    try {
      const res = await runML('shap', buildRequest({
        dataset_id: datasetId,
        y_variable: yVariable,
        is_survival: isSurvival,
        time_variable: timeVariable || undefined,
        x_variables: finalVars,
        filters: [],
        params: { modelType: bestModel || 'random-forest', model_params: modelParamsPayload, testSize: 0.3, format: 'svg' },
        seed: 123,
        variable_types: buildVariableTypes(state.allVariables),
      }));
      setShapResult(res);
      dispatch({ type: 'SET_EXPLAIN_RESULTS', payload: res });
      message.success('SHAP分析完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'SHAP分析失败');
    } finally {
      setLoading(false);
    }
  };

  const runPdp = async () => {
    if (!datasetId || !yVariable || !pdpFeature) return;
    setLoading(true);
    try {
      const res = await runML('pdp', buildRequest({
        dataset_id: datasetId,
        y_variable: yVariable,
        is_survival: isSurvival,
        time_variable: timeVariable || undefined,
        x_variables: finalVars,
        filters: [],
        params: { modelType: bestModel || 'random-forest', model_params: modelParamsPayload, feature: pdpFeature, testSize: 0.3, format: 'svg' },
        seed: 123,
        variable_types: buildVariableTypes(state.allVariables),
      }));
      setPdpResult(res);
      dispatch({ type: 'SET_EXPLAIN_RESULTS', payload: res });
      message.success('PDP/ICE分析完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'PDP分析失败');
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'shap',
      label: 'SHAP',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Button icon={<PlayCircleOutlined />} loading={loading} onClick={runShap}>运行SHAP分析</Button>
          {shapResult && <ResultDisplay result={shapResult} loading={false} />}
        </Space>
      ),
    },
    {
      key: 'pdp',
      label: 'PDP / ICE',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select
            placeholder="选择分析特征"
            value={pdpFeature}
            onChange={setPdpFeature}
            options={finalVars.map((v) => ({ label: v, value: v }))}
            style={{ width: 200 }}
          />
          <Button icon={<PlayCircleOutlined />} loading={loading} onClick={runPdp}>运行PDP/ICE分析</Button>
          {pdpResult && <ResultDisplay result={pdpResult} loading={false} />}
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="模型解释性分析" size="small">
        <Alert
          message="关于模型解释性"
          description={
            <ul>
              <li>SHAP (SHapley Additive exPlanations): 基于博弈论的模型解释方法，揭示每个特征对预测的贡献</li>
              <li>PDP (Partial Dependence Plot): 展示特征与预测结果的平均关系</li>
              <li>ICE (Individual Conditional Expectation): 展示每个样本的特征-预测关系</li>
            </ul>
          }
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        <Button
          type="primary"
          onClick={() => markComplete(6)}
          disabled={!shapResult && !pdpResult}
          style={{ marginTop: 16 }}
        >
          确认完成解释性分析
        </Button>
      </Card>
    </Space>
  );
};

export default Step7Explain;
