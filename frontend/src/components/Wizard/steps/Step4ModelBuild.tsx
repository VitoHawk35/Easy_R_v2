import React, { useState } from 'react';
import { Card, Form, Select, Radio, Button, Space, Tag, Checkbox, InputNumber, Divider, Alert, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { useWizard, featureCandidates } from '@/context/WizardContext';
import { runML } from '@/services/api';
import { ALGORITHMS, buildVariableTypes } from '@/types';
import { renderAlgorithmParam } from '../utils/renderAlgorithmParam';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';

const modelAlgorithms = ALGORITHMS.filter(
  (a) => !['vif', 'compare', 'shap', 'pdp', 'calibration', 'dca', 'bootstrap'].includes(a.key)
);

const compareModelKeys = [
  'logistic', 'decision-tree', 'random-forest', 'gbdt', 'xgboost', 'lightgbm',
  'svm', 'knn', 'catboost', 'naive-bayes', 'mlp', 'tabpfn',
];

const Step4ModelBuild: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, groupVariable, filterResults, buildMode, selectedModel, compareModels, forcedIncludeVars, allVariables } = state;
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  // E4d：统一特征候选（排除 Y / 时间 / 分组 / ID 变量）
  const candidates = featureCandidates(state);
  const finalVars = (filterResults.final.length > 0 ? filterResults.final : candidates)
    .filter((name) => candidates.includes(name));
  const availableVars = candidates;
  const forcedVars = forcedIncludeVars.filter((name) => candidates.includes(name));
  const mergedVars = Array.from(new Set([...finalVars, ...forcedVars]));
  const currentConfig = modelAlgorithms.find((a) => a.key === selectedModel);

  const handleModelChange = (val: string) => {
    dispatch({ type: 'SET_SELECTED_MODEL', payload: val });
    const cfg = modelAlgorithms.find((a) => a.key === val);
    if (cfg) {
      const defaults: Record<string, any> = {};
      cfg.params.forEach((p) => { defaults[p.name] = p.default; });
      form.setFieldsValue(defaults);
    }
  };

  const runBuild = async () => {
    if (!datasetId || !yVariable || finalVars.length === 0) {
      message.error('请先完成前面的步骤');
      return;
    }
    setLoading(true);
    try {
      if (buildMode === 'single') {
        if (!selectedModel) {
          message.error('请选择模型');
          setLoading(false);
          return;
        }
        const params = form.getFieldsValue();
        params.format = 'svg';
        if (groupVariable) params.group_variable = groupVariable;
        const res = await runML(selectedModel, buildRequest({
          dataset_id: datasetId,
          y_variable: yVariable,
          is_survival: isSurvival,
          time_variable: timeVariable || undefined,
          x_variables: mergedVars,
          filters: [],
          params,
          seed: params.seed || 123,
          variable_types: buildVariableTypes(state.allVariables),
        }));
        dispatch({ type: 'SET_BUILD_RESULT', payload: res });
        // E4c：记录本次建模实际使用的特征集（含强制纳入变量），供第 5–9 步复用
        dispatch({ type: 'SET_MODEL_FEATURES', payload: mergedVars });
        dispatch({ type: 'SET_BEST_MODEL', payload: selectedModel });
        dispatch({ type: 'SET_MODEL_PARAMS', payload: { [selectedModel]: params } });
        if (res.model_info) {
          dispatch({ type: 'SET_MODEL_INFO', payload: res.model_info });
        }
      } else {
        if (compareModels.length === 0) {
          message.error('请至少选择一个模型');
          setLoading(false);
          return;
        }
        const params = form.getFieldsValue();
        params.format = 'svg';
        const res = await runML('compare', buildRequest({
          dataset_id: datasetId,
          y_variable: yVariable,
          is_survival: isSurvival,
          time_variable: timeVariable || undefined,
          x_variables: mergedVars,
          filters: [],
          params: {
            models: compareModels.map((k) => {
              const map: Record<string, string> = {
                logistic: 'LR', 'decision-tree': 'DT', 'random-forest': 'RF',
                gbdt: 'GBDT', xgboost: 'XGB', lightgbm: 'LGBM', svm: 'SVM', knn: 'KNN',
                catboost: 'CatBoost', 'naive-bayes': 'NB', mlp: 'MLP', tabpfn: 'TabPFN',
              };
              return map[k] || k;
            }).filter((v, i, a) => a.indexOf(v) === i),
            cvFolds: params.cv || 5,
            repeats: params.repeats || 5,
            testSize: params.testSize || 0.3,
            seed: params.seed || 123,
            ...(groupVariable ? { group_variable: groupVariable } : {}),
          },
          seed: params.seed || 123,
          variable_types: buildVariableTypes(state.allVariables),
        }));
        dispatch({ type: 'SET_BUILD_RESULT', payload: res });
        dispatch({ type: 'SET_MODEL_FEATURES', payload: mergedVars });
        const bestModelFromSummary = res.summary?.match(/最佳(?:AUC)?模型[:：]\s*([A-Za-z]+)/)?.[1] || '';
        const reverseMap: Record<string, string> = {
          LR: 'logistic', DT: 'decision-tree', RF: 'random-forest',
          GBDT: 'gbdt', XGB: 'xgboost', LGBM: 'lightgbm', SVM: 'svm', KNN: 'knn',
          CatBoost: 'catboost', NB: 'naive-bayes', MLP: 'mlp', TabPFN: 'tabpfn',
        };
        const bestKey = reverseMap[bestModelFromSummary] || compareModels[0] || '';
        dispatch({ type: 'SET_BEST_MODEL', payload: bestKey });
        dispatch({ type: 'SET_MODEL_PARAMS', payload: { [bestKey]: params } });
      }
      markComplete(3);
      message.success('模型训练完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '模型训练失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="模型选择" size="small">
        <Radio.Group
          value={buildMode}
          onChange={(e) => dispatch({ type: 'SET_BUILD_MODE', payload: e.target.value })}
          style={{ marginBottom: 16 }}
        >
          <Radio.Button value="single">单模型</Radio.Button>
          <Radio.Button value="compare">多模型对比</Radio.Button>
        </Radio.Group>

        {finalVars.length === 0 ? (
          <Alert
            type="warning"
            showIcon
            message="尚未确定特征变量"
            description="请先在前面步骤中完成变量筛选，或确保数据集中存在可用变量。"
            style={{ marginBottom: 16 }}
          />
        ) : (
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8, color: 'var(--c-mute)' }}>当前特征变量 ({finalVars.length})：</div>
            <div>
              {finalVars.map((v) => (
                <Tag key={v} color="blue" style={{ marginBottom: 4 }}>{v}</Tag>
              ))}
            </div>
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8, color: 'var(--c-mute)' }}>强制纳入变量（将额外加入模型）：</div>
          <Select
            mode="multiple"
            allowClear
            placeholder="选择强制纳入模型的变量"
            value={forcedIncludeVars}
            onChange={(vals) => dispatch({ type: 'SET_FORCED_INCLUDE_VARS', payload: vals })}
            options={availableVars.map((v) => ({ label: v, value: v }))}
            style={{ width: '100%' }}
          />
        </div>

        {mergedVars.length !== finalVars.length && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8, color: 'var(--c-mute)' }}>最终纳入变量 ({mergedVars.length})：</div>
            <div>
              {mergedVars.map((v) => (
                <Tag key={v} color={finalVars.includes(v) ? 'blue' : 'orange'} style={{ marginBottom: 4 }}>{v}</Tag>
              ))}
            </div>
          </div>
        )}

        <Divider style={{ margin: '12px 0' }} />

        {buildMode === 'single' ? (
          <>
            <div style={{ marginBottom: 12 }}>
              <div style={{ marginBottom: 6, fontWeight: 500 }}>选择算法</div>
              <Select
                style={{ width: '100%' }}
                placeholder="请选择建模算法"
                value={selectedModel || undefined}
                onChange={handleModelChange}
                options={modelAlgorithms.map((a) => ({
                  label: `${a.label}${a.category ? ` (${a.category})` : ''}`,
                  value: a.key,
                }))}
                showSearch
                optionFilterProp="label"
              />
            </div>

            {currentConfig && currentConfig.params.length > 0 && (
              <Form form={form} layout="vertical" size="small">
                {currentConfig.params.map((p) => (
                  <Form.Item
                    key={p.name}
                    name={p.name}
                    label={p.label}
                    initialValue={p.default}
                    valuePropName={p.type === 'boolean' ? 'checked' : 'value'}
                  >
                    {renderAlgorithmParam(p)}
                  </Form.Item>
                ))}
              </Form>
            )}
          </>
        ) : (
          <>
            <div style={{ marginBottom: 12 }}>
              <div style={{ marginBottom: 6, fontWeight: 500 }}>选择要对比的模型</div>
              <Checkbox.Group
                value={compareModels}
                onChange={(vals) => dispatch({ type: 'SET_COMPARE_MODELS', payload: vals as string[] })}
                options={compareModelKeys.map((k) => {
                  const alg = ALGORITHMS.find((a) => a.key === k);
                  return { label: alg?.label || k, value: k };
                })}
              />
            </div>

            <Form form={form} layout="vertical" size="small">
              <Form.Item name="cv" label="交叉验证折数（每次重复）" initialValue={5}>
                <InputNumber min={2} max={20} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="repeats" label="重复次数（重复交叉验证）" initialValue={5}>
                <InputNumber min={2} max={50} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="seed" label="随机种子" initialValue={123}>
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Form>
          </>
        )}

        <Button type="primary" icon={<PlayCircleOutlined />} loading={loading} onClick={runBuild} block style={{ marginTop: 16 }}>
          {buildMode === 'single' ? '训练模型' : '训练并对比模型'}
        </Button>
      </Card>
      {state.buildResult && <ResultDisplay result={state.buildResult} loading={false} />}
    </Space>
  );
};

export default Step4ModelBuild;