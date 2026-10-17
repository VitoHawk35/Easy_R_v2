import React, { useState, useEffect } from 'react';
import {
  Card, Form, Select, Switch, InputNumber, Button, Space, Tag, Slider, message, Row, Col, Checkbox, Radio, Input,
} from 'antd';
import { PlayCircleOutlined, ClearOutlined, CopyOutlined } from '@ant-design/icons';
import { ALGORITHMS, type AlgorithmConfig, type VariableInfo } from '@/types';

interface AlgorithmFormProps {
  algorithm: string;
  variables: VariableInfo[];
  selectedVars: Set<string>;
  onRun: (values: any) => void;
  onToggleVar: (name: string, checked: boolean) => void;
  loading: boolean;
}

const AlgorithmForm: React.FC<AlgorithmFormProps> = ({
  algorithm,
  variables,
  selectedVars,
  onRun,
  onToggleVar,
  loading,
}) => {
  const [form] = Form.useForm();
  const [yVar, setYVar] = useState<string>('');
  const [isSurvival, setIsSurvival] = useState(false);
  const [timeVar, setTimeVar] = useState('');
  const [imageFormat, setImageFormat] = useState('svg');

  const config = ALGORITHMS.find((a) => a.key === algorithm);

  useEffect(() => {
    if (config) {
      const defaults: Record<string, any> = {};
      config.params.forEach((p) => {
        defaults[p.name] = p.default;
      });
      defaults.format = 'svg';
      form.setFieldsValue(defaults);
    }
  }, [config, form]);

  const numericVars = variables.filter((v) => v.type === 'continuous');
  const allVarNames = variables.map((v) => v.name);

  const handleRun = () => {
    if (!yVar) {
      message.error('请选择响应变量(Y)');
      return;
    }
    if (selectedVars.size === 0) {
      message.error('请至少选择一个特征变量');
      return;
    }
    const params = form.getFieldsValue();
    params.format = imageFormat;
    onRun({
      y_variable: yVar,
      is_survival: isSurvival,
      time_variable: timeVar || undefined,
      x_variables: Array.from(selectedVars),
      params,
      seed: params.seed || 123,
    });
  };

  const renderParam = (p: AlgorithmConfig['params'][0]) => {
    switch (p.type) {
      case 'number':
        return (
          <InputNumber
            style={{ width: '100%' }}
            min={p.min}
            max={p.max}
            step={p.step}
            changeOnWheel
          />
        );
      case 'slider':
        return (
          <Slider
            min={p.min}
            max={p.max}
            step={p.step}
            marks={{ [p.min!]: String(p.min), [p.max!]: String(p.max) }}
          />
        );
      case 'select':
        return (
          <Select
            options={p.options?.map((o) => ({ label: o.label, value: o.value }))}
            style={{ width: '100%' }}
          />
        );
      case 'boolean':
        return <Switch />;
      case 'array':
        return (
          <Checkbox.Group options={[
            { label: 'LR', value: 'LR' },
            { label: 'DT', value: 'DT' },
            { label: 'RF', value: 'RF' },
            { label: 'SVM', value: 'SVM' },
            { label: 'KNN', value: 'KNN' },
            { label: 'GBDT', value: 'GBDT' },
            { label: 'CatBoost', value: 'CatBoost' },
          ]} />
        );
      default:
        return <Input />;
    }
  };

  if (!config) return null;

  return (
    <Card
      title={`${config.label} - 参数配置`}
      size="small"
      style={{ marginBottom: 16 }}
      extra={
        <Space>
          <Button icon={<ClearOutlined />} size="small" onClick={() => form.resetFields()}>重置</Button>
          <Button type="primary" icon={<PlayCircleOutlined />} size="small" loading={loading} onClick={handleRun}>运行分析</Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" size="small" initialValues={{ seed: 123 }}>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="响应变量(Y)" required>
              <Select
                placeholder="选择Y变量"
                value={yVar}
                onChange={setYVar}
                showSearch
                options={allVarNames.map((n) => ({ label: n, value: n }))}
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="是否为生存数据">
              <Switch checked={isSurvival} onChange={setIsSurvival} checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          </Col>
        </Row>
        {isSurvival && (
          <Form.Item label="生存时间变量">
            <Select
              placeholder="选择时间变量"
              value={timeVar}
              onChange={setTimeVar}
              options={numericVars.map((v) => ({ label: v.name, value: v.name }))}
            />
          </Form.Item>
        )}

        <Form.Item label="特征变量">
          <div style={{ minHeight: 40, border: '1px dashed var(--c-line)', borderRadius: 4, padding: 6, background: 'var(--c-canvas-soft)' }}>
            {selectedVars.size === 0 ? (
              <span style={{ color: 'var(--c-mute)' }}>请从右侧面板选择特征变量</span>
            ) : (
              <Space size={[0, 4]} wrap>
                {Array.from(selectedVars).map((name) => (
                  <Tag key={name} closable onClose={() => onToggleVar(name, false)}>{name}</Tag>
                ))}
              </Space>
            )}
          </div>
        </Form.Item>

        {config.params.map((p) => (
          <Form.Item
            key={p.name}
            name={p.name}
            label={p.label}
            valuePropName={p.type === 'boolean' ? 'checked' : 'value'}
            initialValue={p.default}
          >
            {renderParam(p)}
          </Form.Item>
        ))}

        <Form.Item label="图片格式">
          <Radio.Group value={imageFormat} onChange={(e) => setImageFormat(e.target.value)}>
            <Radio.Button value="svg">SVG</Radio.Button>
            <Radio.Button value="png">PNG</Radio.Button>
          </Radio.Group>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default AlgorithmForm;
