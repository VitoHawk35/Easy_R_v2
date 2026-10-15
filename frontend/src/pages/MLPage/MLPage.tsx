import React, { useState } from 'react';
import { Spin, message } from 'antd';
import AlgorithmForm from '@/components/AlgorithmForm/AlgorithmForm';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';
import { runML } from '@/services/api';
import { buildVariableTypes, type MLResult, type VariableInfo } from '@/types';

interface MLPageProps {
  datasetId: string;
  algorithm: string;
  variables: VariableInfo[];
  selectedVars: Set<string>;
  onToggleVar: (name: string, checked: boolean) => void;
}

const MLPage: React.FC<MLPageProps> = ({ datasetId, algorithm, variables, selectedVars, onToggleVar }) => {
  const [result, setResult] = useState<MLResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleRun = async (values: any) => {
    setLoading(true);
    try {
      const payload = {
        dataset_id: datasetId,
        y_variable: values.y_variable,
        is_survival: values.is_survival,
        time_variable: values.time_variable,
        x_variables: values.x_variables,
        filters: [],
        params: values.params,
        seed: values.seed,
        variable_types: buildVariableTypes(variables),
      };
      const res = await runML(algorithm, payload);
      setResult(res);
      message.success('分析完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '分析失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <AlgorithmForm
        algorithm={algorithm}
        variables={variables}
        selectedVars={selectedVars}
        onRun={handleRun}
        onToggleVar={onToggleVar}
        loading={loading}
      />
      <Spin spinning={loading} tip="分析中...">
        <ResultDisplay result={result} loading={loading} />
      </Spin>
    </div>
  );
};

export default MLPage;
