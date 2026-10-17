import React, { useState } from 'react';
import { Card, Checkbox, InputNumber, Select, Button, Space, Tag, Alert, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { useWizard, featureCandidates } from '@/context/WizardContext';
import { runML } from '@/services/api';
import { buildVariableTypes, type MLResult } from '@/types';

const Step3VarFilter: React.FC = () => {
  const { state, dispatch, markComplete, buildRequest } = useWizard();
  const { datasetId, yVariable, isSurvival, timeVariable, allVariables, filterConfig, removedVars, filterResults } = state;
  const [loading, setLoading] = useState(false);

  // E4d：统一特征候选，排除 Y / 时间 / 分组 / ID 变量，再去掉诊断阶段已移除的变量
  const availableVars = featureCandidates(state).filter((n) => !removedVars.includes(n));

  const mapToAvailableVars = (vars: string[]) => Array.from(new Set(vars
    .map((name) => {
      if (availableVars.includes(name)) return name;
      return availableVars.find((v) => name.startsWith(`${v}_`)) || '';
    })
    .filter(Boolean)));

  const isSelectedValue = (value: any) => value === true || value === 1 || ['true', 'yes', '是', 'selected'].includes(String(value).toLowerCase());

  const extractSelectedByColumn = (res: MLResult, titleKeywords: string[], fallbackCoefIndex = 1) => {
    const table = res.tables.find((t) => titleKeywords.some((keyword) => t.title.toLowerCase().includes(keyword.toLowerCase())));
    if (!table) return null;
    const selectedIndex = table.headers.findIndex((header) => header.toLowerCase() === 'selected');
    const selectedVars = selectedIndex >= 0
      ? table.rows.filter((row) => isSelectedValue(row[selectedIndex])).map((row) => String(row[0]))
      : table.rows.filter((row) => Number(row[fallbackCoefIndex]) !== 0).map((row) => String(row[0]));
    return mapToAvailableVars(selectedVars);
  };

  const runFilter = async () => {
    if (!datasetId || !yVariable) {
      message.error('请先完成数据准备步骤');
      return;
    }
    setLoading(true);
    const results = { univariate: [] as string[], lasso: [] as string[], rf: [] as string[], boruta: [] as string[], final: [] as string[] };

    try {
      // Logistic univariate screening
      if (filterConfig.useUnivariate) {
        const res = await runML('logistic-screening', buildRequest({
          dataset_id: datasetId,
          y_variable: yVariable,
          is_survival: isSurvival,
          time_variable: timeVariable || undefined,
          x_variables: availableVars,
          filters: [],
          params: { pValue: filterConfig.univariateP, format: 'svg' },
          seed: 123,
          variable_types: buildVariableTypes(allVariables),
        }));
        const selected = extractSelectedByColumn(res, ['Logistic单因素筛选', 'screening']);
        results.univariate = selected || [];
        if (!selected) {
          message.warning('Logistic单因素筛选结果解析失败，未加入变量');
        }
      }

      // LASSO feature screening
      if (filterConfig.useLasso) {
        const res = await runML('lasso-screening', buildRequest({
          dataset_id: datasetId,
          y_variable: yVariable,
          is_survival: isSurvival,
          time_variable: timeVariable || undefined,
          x_variables: availableVars,
          filters: [],
          params: { cv: 10, standardize: true, format: 'svg' },
          seed: 123,
          variable_types: buildVariableTypes(allVariables),
        }));
        const selected = extractSelectedByColumn(res, ['系数', 'coef']);
        if (selected) {
          results.lasso = selected;
        } else {
          results.lasso = [];
          message.warning('LASSO特征筛选结果解析失败，未加入变量');
        }
      }

      // Random Forest importance
      if (filterConfig.useRF) {
        const res = await runML('random-forest', buildRequest({
          dataset_id: datasetId,
          y_variable: yVariable,
          is_survival: isSurvival,
          time_variable: timeVariable || undefined,
          x_variables: availableVars,
          filters: [],
          params: { nEstimators: 200, maxDepth: 10, testSize: 0.3, format: 'svg' },
          seed: 123,
          variable_types: buildVariableTypes(allVariables),
        }));
        const impTable = res.tables.find((t) => t.title.includes('重要性') || t.title.includes('Importance'));
        if (impTable) {
          // E4d：按重要性降序取前 K 个（默认 10，可配置），不再用“重要性 > 0”几乎全选
          const topK = Math.max(1, filterConfig.rfTopK || 10);
          const ranked = impTable.rows
            .map((row) => ({ name: String(row[0]), importance: Number(row[1]) }))
            .filter((row) => Number.isFinite(row.importance))
            .sort((a, b) => b.importance - a.importance)
            .slice(0, topK)
            .map((row) => row.name);
          results.rf = mapToAvailableVars(ranked);
        } else {
          results.rf = availableVars;
          message.warning('随机森林重要性解析失败，已回退到全部可用变量');
        }
      }

      // Boruta
      if (filterConfig.useBoruta) {
        const res = await runML('boruta', buildRequest({
          dataset_id: datasetId,
          y_variable: yVariable,
          is_survival: isSurvival,
          time_variable: timeVariable || undefined,
          x_variables: availableVars,
          filters: [],
          params: { maxRuns: filterConfig.borutaRuns, pValue: filterConfig.borutaP, format: 'svg' },
          seed: 123,
          variable_types: buildVariableTypes(allVariables),
        }));
        const borutaTable = res.tables.find((t) => t.title.includes('Boruta') || t.headers.includes('Decision'));
        if (borutaTable) {
          const decisionIndex = borutaTable.headers.findIndex((header) => header.toLowerCase() === 'decision');
          const selectedBoruta = decisionIndex >= 0
            ? borutaTable.rows
              .filter((row) => ['confirmed', 'tentative'].includes(String(row[decisionIndex]).toLowerCase()))
              .map((row) => String(row[0]))
            : borutaTable.rows.map((row) => String(row[0]));
          results.boruta = mapToAvailableVars(selectedBoruta);
        } else {
          results.boruta = [];
          message.warning('Boruta结果解析失败，未加入变量');
        }
      }

      // Final = union of all selected methods
      const sets: string[][] = [];
      if (filterConfig.useUnivariate) sets.push(results.univariate);
      if (filterConfig.useLasso) sets.push(results.lasso);
      if (filterConfig.useRF) sets.push(results.rf);
      if (filterConfig.useBoruta) sets.push(results.boruta);
      results.final = sets.length > 0
        ? Array.from(new Set(sets.flat()))
        : availableVars;

      dispatch({ type: 'SET_FILTER_RESULTS', payload: results });
      markComplete(2);
      message.success('变量筛选完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '变量筛选失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="变量筛选方法" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Checkbox
            checked={filterConfig.useUnivariate}
            onChange={(e) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { useUnivariate: e.target.checked } })}
          >
            Logistic单因素筛选
          </Checkbox>
          {filterConfig.useUnivariate && (
            <div style={{ marginLeft: 24, marginTop: 8 }}>
              <label style={{ marginRight: 8 }}>Logistic单因素P值阈值</label>
              <InputNumber
                min={0.001} max={1} step={0.01}
                value={filterConfig.univariateP}
                onChange={(v) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { univariateP: v || 0.1 } })}
              />
            </div>
          )}

          <Checkbox
            checked={filterConfig.useLasso}
            onChange={(e) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { useLasso: e.target.checked } })}
          >
            LASSO特征筛选
          </Checkbox>
          {filterConfig.useLasso && (
            <div style={{ marginLeft: 24, marginTop: 8 }}>
              <label style={{ marginRight: 8 }}>LASSO λ选择</label>
              <Select
                value={filterConfig.lassoLambda}
                onChange={(v) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { lassoLambda: v } })}
                options={[{ label: 'lambda.min', value: 'min' }, { label: 'lambda.1se', value: '1se' }]}
                style={{ width: 200 }}
              />
            </div>
          )}

          <Checkbox
            checked={filterConfig.useRF}
            onChange={(e) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { useRF: e.target.checked } })}
          >
            随机森林
          </Checkbox>
          {filterConfig.useRF && (
            <div style={{ marginLeft: 24, marginTop: 8 }}>
              <div style={{ marginBottom: 6, color: 'var(--c-mute)' }}>
                入选用“按重要性降序取前 K 个”（默认 10），不再按“重要性 &gt; 0”几乎全选
              </div>
              <label style={{ marginRight: 8 }}>保留变量数 K</label>
              <InputNumber
                min={1} max={1000} step={1}
                value={filterConfig.rfTopK}
                onChange={(v) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { rfTopK: v || 10 } })}
              />
            </div>
          )}

          <Checkbox
            checked={filterConfig.useBoruta}
            onChange={(e) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { useBoruta: e.target.checked } })}
          >
            Boruta算法
          </Checkbox>
          {filterConfig.useBoruta && (
            <Space direction="vertical" style={{ marginLeft: 24, width: '100%' }}>
              <div style={{ marginBottom: 8 }}>
                <label style={{ marginRight: 8 }}>Boruta最大迭代次数</label>
                <InputNumber
                  min={10} max={1000} step={10}
                  value={filterConfig.borutaRuns}
                  onChange={(v) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { borutaRuns: v || 100 } })}
                />
              </div>
              <div>
                <label style={{ marginRight: 8 }}>Boruta显著性水平</label>
                <InputNumber
                  min={0.001} max={0.5} step={0.01}
                  value={filterConfig.borutaP}
                  onChange={(v) => dispatch({ type: 'SET_FILTER_CONFIG', payload: { borutaP: v || 0.05 } })}
                />
              </div>
            </Space>
          )}

          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={loading}
            onClick={runFilter}
            block
          >
            运行变量筛选
          </Button>
        </Space>
      </Card>

      {filterResults.final.length > 0 && (
        <Card title="筛选结果" size="small">
          <Space direction="vertical" style={{ width: '100%' }}>
            {filterConfig.useUnivariate && (
              <div>
                <strong>Logistic单因素筛选 ({filterResults.univariate.length}个):</strong>
                <Space size={[0, 4]} wrap style={{ marginTop: 4 }}>
                  {filterResults.univariate.map((v) => (
                    <Tag key={v} color="blue">{v}</Tag>
                  ))}
                </Space>
              </div>
            )}
            {filterConfig.useLasso && (
              <div>
                <strong>LASSO特征筛选 ({filterResults.lasso.length}个):</strong>
                <Space size={[0, 4]} wrap style={{ marginTop: 4 }}>
                  {filterResults.lasso.map((v) => (
                    <Tag key={v} color="green">{v}</Tag>
                  ))}
                </Space>
              </div>
            )}
            {filterConfig.useRF && (
              <div>
                <strong>随机森林 ({filterResults.rf.length}个):</strong>
                <Space size={[0, 4]} wrap style={{ marginTop: 4 }}>
                  {filterResults.rf.map((v) => (
                    <Tag key={v} color="orange">{v}</Tag>
                  ))}
                </Space>
              </div>
            )}
            {filterConfig.useBoruta && (
              <div>
                <strong>Boruta ({filterResults.boruta.length}个):</strong>
                <Space size={[0, 4]} wrap style={{ marginTop: 4 }}>
                  {filterResults.boruta.map((v) => (
                    <Tag key={v} color="purple">{v}</Tag>
                  ))}
                </Space>
              </div>
            )}
            <Alert
              type="success"
              showIcon={false}
              style={{ marginTop: 12 }}
              message={<strong>最终筛选变量 ({filterResults.final.length}个):</strong>}
              description={
                <Space size={[0, 4]} wrap style={{ marginTop: 4 }}>
                  {filterResults.final.map((v) => (
                    <Tag key={v} closable onClose={() => {
                      const next = filterResults.final.filter((x) => x !== v);
                      dispatch({ type: 'SET_FILTER_RESULTS', payload: { ...filterResults, final: next } });
                    }}>
                      {v}
                    </Tag>
                  ))}
                </Space>
              }
            />
          </Space>
        </Card>
      )}
    </Space>
  );
};

export default Step3VarFilter;
