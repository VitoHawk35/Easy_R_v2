import React, { useState } from 'react';
import { Card, Button, Space, message, Alert } from 'antd';
import { PlayCircleOutlined, ForwardOutlined } from '@ant-design/icons';
import { useWizard } from '@/context/WizardContext';
import { runML } from '@/services/api';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';
import { buildVariableTypes } from '@/types';

const Step8AdvDiag: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, filterResults, bestModel } = state;
  const [loading, setLoading] = useState(false);

  const finalVars = filterResults.final.length > 0 ? filterResults.final : state.allVariables.map((v) => v.name).filter((n) => n !== yVariable && n !== timeVariable);
  const isLogistic = bestModel === 'logistic';

  const runAdvDiag = async () => {
    if (!datasetId || !yVariable) {
      message.error('请先完成前面的步骤');
      return;
    }
    setLoading(true);
    try {
      const res = await runML('adv-diag', buildRequest({
        dataset_id: datasetId,
        y_variable: yVariable,
        is_survival: isSurvival,
        time_variable: timeVariable || undefined,
        x_variables: finalVars,
        filters: [],
        params: { modelType: bestModel || 'logistic', testSize: 0.3, format: 'svg' },
        seed: 123,
        variable_types: buildVariableTypes(state.allVariables),
      }));
      dispatch({ type: 'SET_ADV_DIAG_RESULTS', payload: res });
      markComplete(7);
      message.success('高级诊断完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '高级诊断失败');
    } finally {
      setLoading(false);
    }
  };

  const skipStep = () => {
    markComplete(7);
    message.info('已跳过高级诊断步骤，可继续下一步');
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="高级诊断" size="small">
        <Alert
          message="残差分析与影响点检测"
          description="分析模型残差分布、Q-Q图、Cook距离和杠杆值，检测异常样本和影响点。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        {!isLogistic && (
          <Alert
            message={`当前模型为 "${bestModel || '未选择'}"，高级诊断仅适用于 Logistic 回归（基于 GLM 残差/Cook距离/杠杆值的诊断方法对非 GLM 模型在统计上没有定义）。`}
            description="如需进行高级诊断，请返回 Step4 训练 Logistic 回归模型；否则可直接跳过此步骤继续后续流程。"
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
        <Space style={{ width: '100%' }} direction="vertical">
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={loading}
            onClick={runAdvDiag}
            disabled={!isLogistic}
            block
          >
            运行高级诊断
          </Button>
          <Button
            icon={<ForwardOutlined />}
            onClick={skipStep}
            block
          >
            跳过此步骤
          </Button>
        </Space>
      </Card>

      {state.advDiagResults && <ResultDisplay result={state.advDiagResults} loading={false} />}
    </Space>
  );
};

export default Step8AdvDiag;
