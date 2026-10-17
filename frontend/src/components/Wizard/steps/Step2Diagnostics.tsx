import React, { useState } from 'react';
import { Card, Form, InputNumber, Switch, Button, Space, Alert, Badge, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { useWizard, featureCandidates } from '@/context/WizardContext';
import { runML, runDiagnostics } from '@/services/api';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';
import { buildVariableTypes, type MLResult } from '@/types';

const Step2Diagnostics: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, allVariables, diagnosisConfig, diagnosisResult, removedVars } = state;
  const [loadingVif, setLoadingVif] = useState(false);
  const [loadingMissing, setLoadingMissing] = useState(false);

  // E4d：统一特征候选，排除 Y / 时间 / 分组 / ID 变量
  const xVars = featureCandidates(state);

  const runVif = async () => {
    if (!datasetId || !yVariable) {
      message.error('请先完成数据准备步骤');
      return;
    }
    setLoadingVif(true);
    try {
      const payload = {
        dataset_id: datasetId,
        y_variable: yVariable,
        is_survival: isSurvival,
        time_variable: timeVariable || undefined,
        x_variables: xVars,
        filters: [],
        params: {
          vifThreshold: diagnosisConfig.vifThreshold,
          corrThreshold: diagnosisConfig.corrThreshold,
          autoRemove: diagnosisConfig.autoRemove,
          format: 'svg',
        },
        seed: 123,
        variable_types: buildVariableTypes(allVariables),
      };
      const res = await runML('vif', buildRequest(payload));
      dispatch({ type: 'SET_DIAGNOSIS_RESULT', payload: res });

      // E4e：直接从 model_info.removed_vars / removed_vars 读取，不再解析 summary 文本
      const removed = diagnosisConfig.autoRemove
        ? (res.removed_vars ?? res.model_info?.removed_vars ?? [])
        : [];
      dispatch({ type: 'SET_REMOVED_VARS', payload: removed });
      markComplete(1);
      message.success('VIF诊断完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'VIF诊断失败');
    } finally {
      setLoadingVif(false);
    }
  };

  const runMissing = async () => {
    if (!datasetId || !yVariable) {
      message.error('请先完成数据准备步骤');
      return;
    }
    setLoadingMissing(true);
    try {
      const payload = {
        dataset_id: datasetId,
        y_variable: yVariable,
        is_survival: isSurvival,
        time_variable: timeVariable || undefined,
        x_variables: xVars,
        filters: [],
        params: {},
        seed: 123,
        variable_types: buildVariableTypes(allVariables),
      };
      const res = await runDiagnostics('missing', buildRequest(payload));
      // Merge missing result into diagnosis result for display, replacing old missing results
      const merged: MLResult = diagnosisResult
        ? {
            ...diagnosisResult,
            charts: [
              ...diagnosisResult.charts.filter((c) => !c.title.includes('缺失') && !c.title.includes('Missing')),
              ...res.charts,
            ],
            tables: [
              ...diagnosisResult.tables.filter((t) => !t.title.includes('缺失') && !t.title.includes('Missing')),
              ...res.tables,
            ],
            summary: diagnosisResult.summary + ' ' + res.summary,
          }
        : res;
      dispatch({ type: 'SET_DIAGNOSIS_RESULT', payload: merged });
      message.success('缺失值诊断完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '缺失值诊断失败');
    } finally {
      setLoadingMissing(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="共线性诊断配置" size="small">
        <Form layout="vertical" size="small">
          <Form.Item label="VIF阈值">
            <InputNumber
              min={1} max={20} step={0.5}
              value={diagnosisConfig.vifThreshold}
              onChange={(v) => dispatch({ type: 'SET_DIAGNOSIS_CONFIG', payload: { vifThreshold: v || 5 } })}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item label="相关系数阈值">
            <InputNumber
              min={0.1} max={1} step={0.05}
              value={diagnosisConfig.corrThreshold}
              onChange={(v) => dispatch({ type: 'SET_DIAGNOSIS_CONFIG', payload: { corrThreshold: v || 0.7 } })}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item label="自动移除高共线性变量">
            <Switch
              checked={diagnosisConfig.autoRemove}
              onChange={(v) => dispatch({ type: 'SET_DIAGNOSIS_CONFIG', payload: { autoRemove: v } })}
            />
          </Form.Item>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={loadingVif}
            onClick={runVif}
            block
          >
            运行VIF诊断
          </Button>
        </Form>
      </Card>

      <Card title="缺失值诊断" size="small">
        <Button
          icon={<PlayCircleOutlined />}
          loading={loadingMissing}
          onClick={runMissing}
          block
        >
          运行缺失值诊断
        </Button>
      </Card>

      {removedVars.length > 0 && (
        <Alert
          message={`已自动移除 ${removedVars.length} 个高共线性变量: ${removedVars.join(', ')}`}
          type="warning"
          showIcon
        />
      )}

      {diagnosisResult && <ResultDisplay result={diagnosisResult} loading={false} />}
    </Space>
  );
};

export default Step2Diagnostics;
