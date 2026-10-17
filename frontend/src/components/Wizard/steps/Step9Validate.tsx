import React, { useState } from 'react';
import { Card, Checkbox, InputNumber, Upload, Button, Space, message } from 'antd';
import { PlayCircleOutlined, UploadOutlined } from '@ant-design/icons';
import { useWizard, effectiveModelFeatures } from '@/context/WizardContext';
import { runML, runExternalValidation } from '@/services/api';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';
import { buildVariableTypes } from '@/types';

const Step9Validate: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, groupVariable, bestModel, modelParams } = state;
  const [useBootstrap, setUseBootstrap] = useState(true);
  const [useExternal, setUseExternal] = useState(false);
  const [nBootstrap, setNBootstrap] = useState(200);
  const [externalFile, setExternalFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  // E4c：使用 Step4 实际建模的特征集（含强制纳入变量）与超参数
  const finalVars = effectiveModelFeatures(state);

  const runValidation = async () => {
    if (!datasetId || !yVariable) {
      message.error('请先完成前面的步骤');
      return;
    }
    setLoading(true);
    const allResults: any = { charts: [], tables: [], summary: '', success: true };
    let didRunAny = false;
    try {
      if (useBootstrap) {
        const res = await runML('bootstrap', buildRequest({
          dataset_id: datasetId,
          y_variable: yVariable,
          is_survival: isSurvival,
          time_variable: timeVariable || undefined,
          x_variables: finalVars,
          filters: [],
          params: {
            modelType: bestModel || 'logistic',
            model_params: { [bestModel || 'logistic']: modelParams[bestModel || 'logistic'] || {} },
            nBootstrap,
            testSize: 0.3,
            format: 'svg',
            ...(groupVariable ? { group_variable: groupVariable } : {}),
          },
          seed: 123,
          variable_types: buildVariableTypes(state.allVariables),
        }));
        allResults.charts.push(...res.charts);
        allResults.tables.push(...res.tables);
        allResults.summary += res.summary + ' ';
        didRunAny = true;
      }

      if (useExternal && externalFile && bestModel) {
        const params = modelParams[bestModel] || {};
        const res = await runExternalValidation(externalFile, datasetId, bestModel, yVariable, finalVars, params, 123, buildVariableTypes(state.allVariables));
        allResults.charts.push(...res.charts);
        allResults.tables.push(...res.tables);
        allResults.summary += res.summary + ' ';
        didRunAny = true;
      }

      // E4f：什么都没跑时不写入结果、不标记完成
      if (!didRunAny) {
        message.warning(
          useExternal && !externalFile
            ? '已勾选外部验证但尚未上传验证文件，未运行任何验证'
            : '请至少选择并运行一项验证',
        );
        return;
      }

      dispatch({ type: 'SET_VALIDATION_RESULTS', payload: allResults });
      markComplete(8);
      message.success('模型验证完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '验证失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="验证方法" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Checkbox checked={useBootstrap} onChange={(e) => setUseBootstrap(e.target.checked)}>
            内部验证 (Bootstrap)
          </Checkbox>
          {useBootstrap && (
            <div>
              <label style={{ marginRight: 8 }}>Bootstrap次数</label>
              <InputNumber min={50} max={2000} step={50} value={nBootstrap} onChange={(v) => setNBootstrap(v || 200)} />
            </div>
          )}

          <Checkbox checked={useExternal} onChange={(e) => setUseExternal(e.target.checked)}>
            外部验证 (测试集)
          </Checkbox>

          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={loading}
            onClick={runValidation}
            block
          >
            运行验证
          </Button>
        </Space>
      </Card>

      <Card title="独立外部验证" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <p>使用独立数据集验证模型泛化能力</p>
          <Upload
            beforeUpload={(file) => {
              setExternalFile(file);
              return false;
            }}
            maxCount={1}
            accept=".csv,.xlsx,.xls"
          >
            <Button icon={<UploadOutlined />}>上传外部验证数据</Button>
          </Upload>
          {externalFile && <span>已选择: {externalFile.name}</span>}
        </Space>
      </Card>

      {state.validationResults && <ResultDisplay result={state.validationResults} loading={false} />}
    </Space>
  );
};

export default Step9Validate;
