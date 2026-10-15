import React, { useEffect, useState } from 'react';
import { Card, Select, Switch, Upload, Button, Table, Alert, Space, message, InputNumber, Input, Divider } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import { useWizard } from '@/context/WizardContext';
import { previewDataset, uploadDataset, getVariables, transformDataset } from '@/services/api';
import type { DatasetInfo, VariableInfo } from '@/types';

interface Step1Props {
  datasets: DatasetInfo[];
  onDatasetChange: (id: string) => void;
  variables: VariableInfo[];
}

const Step1DataPrep: React.FC<Step1Props> = ({ datasets, onDatasetChange, variables }) => {
  const { state, dispatch, markComplete, unmarkComplete } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, groupVariable, previewData, previewColumns, transformConfig, transformResult } = state;
  const [loading, setLoading] = useState(false);
  const [transformEnabled, setTransformEnabled] = useState(false);
  const [transformLoading, setTransformLoading] = useState(false);

  const numericVars = variables.filter((v) => v.type === 'continuous');
  const allVarNames = variables.map((v) => v.name);
  const transformVars = allVarNames.filter((name) => name !== yVariable && name !== timeVariable);
  const isClr = transformConfig.method === 'clr';

  useEffect(() => {
    if (datasetId && previewData.length === 0) {
      loadPreview(datasetId);
    }
  }, [datasetId]);

  useEffect(() => {
    dispatch({ type: 'SET_ALL_VARIABLES', payload: variables });
  }, [variables]);

  useEffect(() => {
    if (!datasetId || transformConfig.dataset_id === datasetId) return;
    dispatch({
      type: 'SET_TRANSFORM_CONFIG',
      payload: {
        dataset_id: datasetId,
        peak_variables: [],
        reference_variable: '',
        y_variable: yVariable,
        output_name: `${datasetId}_ALR`,
      },
    });
  }, [datasetId, variables]);

  useEffect(() => {
    dispatch({ type: 'SET_TRANSFORM_CONFIG', payload: { y_variable: yVariable } });
  }, [yVariable]);

  const loadPreview = async (id: string) => {
    setLoading(true);
    try {
      const res = await previewDataset(id, 20);
      dispatch({ type: 'SET_PREVIEW', payload: { columns: res.columns, data: res.data } });
      const info = datasets.find((d) => d.id === id) || (state.datasetInfo?.id === id ? state.datasetInfo : null);
      dispatch({ type: 'SET_DATASET', payload: { id, info } });
    } catch (e) {
      message.error('加载数据预览失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDatasetChange = (id: string) => {
    dispatch({ type: 'SET_DATASET', payload: { id, info: datasets.find((d) => d.id === id) || null } });
    dispatch({ type: 'SET_PREVIEW', payload: { columns: [], data: [] } });
    onDatasetChange(id);
    loadPreview(id);
  };

  const handleUpload = async (file: File) => {
    try {
      const info = await uploadDataset(file);
      message.success(`上传成功: ${info.name}`);
      onDatasetChange(info.id);
      handleDatasetChange(info.id);
      const varsRes = await getVariables(info.id);
      dispatch({ type: 'SET_ALL_VARIABLES', payload: varsRes.variables });
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '上传失败');
    }
    return false;
  };

  const updateTransformConfig = (payload: Partial<typeof transformConfig>) => {
    dispatch({ type: 'SET_TRANSFORM_CONFIG', payload });
  };

  const handleTransform = async () => {
    if (!datasetId || !yVariable) {
      message.warning('请先选择数据集和响应变量Y');
      return;
    }
    if (isClr) {
      if (transformConfig.peak_variables.length < 2) {
        message.warning('CLR转换请至少选择2个峰变量（无需基准变量）');
        return;
      }
    } else if (transformConfig.peak_variables.length < 1 || !transformConfig.reference_variable) {
      message.warning('请至少选择1个分子变量并指定分母变量');
      return;
    }
    setTransformLoading(true);
    try {
      const transformVariables = isClr
        ? transformConfig.peak_variables
        : Array.from(new Set([...transformConfig.peak_variables, transformConfig.reference_variable]));
      const res = await transformDataset({
        ...transformConfig,
        dataset_id: datasetId,
        y_variable: yVariable,
        peak_variables: transformVariables,
        reference_variable: isClr ? '' : transformConfig.reference_variable,
      });
      message.success('转换数据集生成成功');
      dispatch({ type: 'SET_TRANSFORM_RESULT', payload: res });
      dispatch({ type: 'SET_DATASET', payload: { id: res.dataset.id, info: res.dataset } });
      dispatch({ type: 'SET_ALL_VARIABLES', payload: res.variables });
      dispatch({ type: 'SET_DIAGNOSIS_RESULT', payload: null });
      dispatch({ type: 'SET_REMOVED_VARS', payload: [] });
      dispatch({ type: 'SET_FILTER_RESULTS', payload: { univariate: [], lasso: [], rf: [], boruta: [], final: [] } });
      dispatch({ type: 'SET_BUILD_RESULT', payload: null });
      dispatch({ type: 'SET_MODEL_INFO', payload: null });
      dispatch({ type: 'SET_EVAL_RESULTS', payload: null });
      dispatch({ type: 'SET_VIZ_RESULTS', payload: null });
      dispatch({ type: 'SET_EXPLAIN_RESULTS', payload: null });
      dispatch({ type: 'SET_ADV_DIAG_RESULTS', payload: null });
      dispatch({ type: 'SET_VALIDATION_RESULTS', payload: null });
      onDatasetChange(res.dataset.id);
      const preview = await previewDataset(res.dataset.id, 20);
      dispatch({ type: 'SET_PREVIEW', payload: { columns: preview.columns, data: preview.data } });
      if (res.variables.some((v) => v.name === yVariable)) {
        dispatch({ type: 'SET_Y_VARIABLE', payload: yVariable });
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '转换失败');
    } finally {
      setTransformLoading(false);
    }
  };

  const handleYChange = (val: string) => {
    dispatch({ type: 'SET_Y_VARIABLE', payload: val });
  };

  const handleSurvivalChange = (checked: boolean) => {
    dispatch({ type: 'SET_SURVIVAL', payload: { isSurvival: checked, timeVariable: state.timeVariable } });
  };

  const handleTimeChange = (val: string) => {
    dispatch({ type: 'SET_SURVIVAL', payload: { isSurvival: state.isSurvival, timeVariable: val } });
  };

  useEffect(() => {
    if (datasetId && yVariable) {
      markComplete(0);
    } else {
      unmarkComplete(0);
    }
  }, [datasetId, yVariable]);

  const columns = previewColumns.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    width: 120,
    ellipsis: true,
  }));
  const datasetOptions = [...datasets];
  if (state.datasetInfo && !datasetOptions.some((d) => d.id === state.datasetInfo?.id)) {
    datasetOptions.push(state.datasetInfo);
  }
  const screeningColumns = transformResult?.screening_table.headers.map((header, index) => ({
    title: header,
    dataIndex: index,
    key: header,
  })) || [];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="数据集" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select
            placeholder="选择数据集"
            style={{ width: '100%' }}
            value={datasetId || undefined}
            onChange={handleDatasetChange}
            options={datasetOptions.map((d) => ({ label: `${d.name} (${d.rows}×${d.cols})`, value: d.id }))}
          />
          <Upload beforeUpload={handleUpload} showUploadList={false}>
            <Button icon={<UploadOutlined />} block>上传新数据集 (CSV/Excel)</Button>
          </Upload>
          {state.datasetInfo && (
            <Alert
              message={`已加载: ${state.datasetInfo.rows} 行 × ${state.datasetInfo.cols} 列`}
              type="success"
              showIcon
            />
          )}
        </Space>
      </Card>

      {datasetId && variables.length > 0 && (
        <Card title="峰值转换 / 数据预处理" size="small">
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <span style={{ marginRight: 8 }}>启用峰值转换（ALR/CLR）</span>
              <Switch checked={transformEnabled} onChange={setTransformEnabled} checkedChildren="是" unCheckedChildren="否" />
            </div>
            {transformEnabled && (
              <>
                <Space wrap>
                  <span>转换方法</span>
                  <Select
                    style={{ width: 320 }}
                    value={transformConfig.method}
                    onChange={(value) => updateTransformConfig({
                      method: value,
                      reference_variable: '',
                      output_name: `${datasetId}_${String(value).toUpperCase()}`,
                    })}
                    options={[
                      { label: 'ALR（加性对数比，需指定基准峰）', value: 'alr' },
                      { label: 'CLR（中心化对数比，无需基准峰）', value: 'clr' },
                    ]}
                  />
                </Space>
                {!isClr && (
                  <Select
                    placeholder="先选择分母/基准变量"
                    style={{ width: '100%' }}
                    value={transformConfig.reference_variable || undefined}
                    onChange={(value) => updateTransformConfig({
                      reference_variable: value,
                      peak_variables: transformConfig.peak_variables.filter((name) => name !== value),
                      output_name: `${datasetId}_ALR_${value}`,
                    })}
                    options={transformVars.map((name) => ({ label: name, value: name }))}
                  />
                )}
                <Space wrap>
                  <Button
                    size="small"
                    disabled={!isClr && !transformConfig.reference_variable}
                    onClick={() => updateTransformConfig({
                      peak_variables: isClr
                        ? transformVars
                        : transformVars.filter((name) => name !== transformConfig.reference_variable),
                    })}
                  >
                    {isClr ? '一键选择全部峰变量' : '一键选择其余变量为分子'}
                  </Button>
                  <Button size="small" onClick={() => updateTransformConfig({ peak_variables: [] })}>
                    {isClr ? '清空峰变量' : '清空分子'}
                  </Button>
                  <span>{isClr ? `已选峰变量：${transformConfig.peak_variables.length} 个` : `已选分子：${transformConfig.peak_variables.length} 个`}</span>
                </Space>
                <Select
                  mode="multiple"
                  placeholder={isClr ? '选择峰变量（至少2个）' : '选择分子变量'}
                  style={{ width: '100%' }}
                  maxTagCount="responsive"
                  value={transformConfig.peak_variables}
                  onChange={(value) => updateTransformConfig({ peak_variables: value })}
                  options={transformVars
                    .filter((name) => isClr || name !== transformConfig.reference_variable)
                    .map((name) => ({ label: name, value: name }))}
                />
                <Space wrap>
                  <span>CV阈值</span>
                  <InputNumber
                    min={0}
                    step={0.01}
                    value={transformConfig.cv_threshold}
                    onChange={(value) => updateTransformConfig({ cv_threshold: Number(value ?? 0) })}
                  />
                  <span>p值</span>
                  <Select
                    style={{ width: 80 }}
                    value={transformConfig.p_operator}
                    onChange={(value) => updateTransformConfig({ p_operator: value })}
                    options={[{ label: '>', value: 'gt' }, { label: '<', value: 'lt' }]}
                  />
                  <InputNumber
                    min={0}
                    max={1}
                    step={0.01}
                    value={transformConfig.p_threshold}
                    onChange={(value) => updateTransformConfig({ p_threshold: Number(value ?? 0) })}
                  />
                </Space>
                <Space wrap>
                  <span>p值检验</span>
                  <Select
                    style={{ width: 160 }}
                    value={transformConfig.pvalue_test}
                    onChange={(value) => updateTransformConfig({ pvalue_test: value })}
                    options={[
                      { label: '自动', value: 'auto' },
                      { label: 'Welch t-test', value: 'ttest' },
                      { label: 'ANOVA', value: 'anova' },
                      { label: 'Spearman', value: 'spearman' },
                    ]}
                  />
                  <span>伪计数</span>
                  <InputNumber
                    min={0.000000001}
                    step={0.000001}
                    value={transformConfig.pseudocount}
                    onChange={(value) => updateTransformConfig({ pseudocount: Number(value ?? 0.000001) })}
                  />
                </Space>
                <Input
                  placeholder="输出数据集名称"
                  value={transformConfig.output_name}
                  onChange={(e) => updateTransformConfig({ output_name: e.target.value })}
                />
                <Button type="primary" loading={transformLoading} disabled={transformVars.length === 0} onClick={handleTransform}>
                  生成转换数据集
                </Button>
                {transformResult && (
                  <>
                    <Divider />
                    <Alert type="success" showIcon message={transformResult.summary} />
                    <Table
                      size="small"
                      bordered
                      columns={screeningColumns}
                      dataSource={transformResult.screening_table.rows.map((row, i) => ({ ...row, key: i }))}
                      pagination={{ pageSize: 8 }}
                      scroll={{ x: 'max-content' }}
                    />
                  </>
                )}
              </>
            )}
          </Space>
        </Card>
      )}

      <Card title="变量配置" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select
            placeholder="选择响应变量 (Y)"
            style={{ width: '100%' }}
            value={yVariable || undefined}
            onChange={handleYChange}
            showSearch
            options={allVarNames.map((n) => ({ label: n, value: n }))}
          />
          <div>
            <span style={{ marginRight: 8 }}>是否为生存数据</span>
            <Switch checked={isSurvival} onChange={handleSurvivalChange} checkedChildren="是" unCheckedChildren="否" />
          </div>
          {isSurvival && (
            <Select
              placeholder="选择生存时间变量"
              style={{ width: '100%' }}
              value={timeVariable || undefined}
              onChange={handleTimeChange}
              options={numericVars.map((v) => ({ label: v.name, value: v.name }))}
            />
          )}
          <div>
            <div style={{ marginBottom: 6, color: '#666' }}>
              分组变量（患者ID，可选）——同一患者的多条样本不会跨训练/验证集
            </div>
            <Select
              placeholder="不设置则按样本划分"
              style={{ width: '100%' }}
              value={groupVariable || undefined}
              onChange={(val) => dispatch({ type: 'SET_GROUP_VARIABLE', payload: val || '' })}
              allowClear
              showSearch
              options={allVarNames
                .filter((n) => n !== yVariable && n !== timeVariable)
                .map((n) => ({ label: n, value: n }))}
            />
          </div>
        </Space>
      </Card>

      {previewData.length > 0 && (
        <Card title="数据预览 (前20行)" size="small">
          <Table
            size="small"
            bordered
            loading={loading}
            columns={columns}
            dataSource={previewData.map((row, i) => ({ ...row, key: i }))}
            pagination={false}
            scroll={{ x: 'max-content' }}
          />
        </Card>
      )}
    </Space>
  );
};

export default Step1DataPrep;
