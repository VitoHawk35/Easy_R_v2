import React, { useState } from 'react';
import { Card, Select, Checkbox, Input, Button, Space, Typography, message } from 'antd';
import { SearchOutlined, ClearOutlined, CopyOutlined, SnippetsOutlined } from '@ant-design/icons';
import type { VariableInfo, DatasetInfo } from '@/types';

const { Text } = Typography;

interface VariablePanelProps {
  datasets: DatasetInfo[];
  activeDataset: string;
  variables: VariableInfo[];
  selectedVars: Set<string>;
  onDatasetChange: (id: string) => void;
  onSelectVar: (name: string, checked: boolean) => void;
  onTypeChange?: (name: string, type: VariableInfo['type']) => void;
}

const VariablePanel: React.FC<VariablePanelProps> = ({
  datasets,
  activeDataset,
  variables,
  selectedVars,
  onDatasetChange,
  onSelectVar,
  onTypeChange,
}) => {
  const [search, setSearch] = useState('');
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const filtered = variables.filter((v) => v.name.toLowerCase().includes(search.toLowerCase()));
  const ds = datasets.find((d) => d.id === activeDataset);

  const handleCheck = (e: any, name: string) => {
    const checked = e.target.checked;
    if (e.nativeEvent.shiftKey && lastChecked) {
      const names = filtered.map((v) => v.name);
      const start = names.indexOf(lastChecked);
      const end = names.indexOf(name);
      const [a, b] = start < end ? [start, end] : [end, start];
      for (let i = a; i <= b; i++) {
        onSelectVar(names[i], true);
      }
    } else {
      onSelectVar(name, checked);
    }
    if (checked) setLastChecked(name);
  };

  return (
    <Card
      size="small"
      style={{ width: 350, borderRadius: 0, borderLeft: '1px solid #f0f0f0', height: '100%', display: 'flex', flexDirection: 'column' }}
      bodyStyle={{ padding: 12, flex: 1, overflow: 'auto' }}
      title={
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text strong>变量列表</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>已选{selectedVars.size}项/共{variables.length}项</Text>
          </div>
          <Select
            size="small"
            style={{ width: '100%' }}
            value={activeDataset}
            onChange={onDatasetChange}
            options={datasets.map((d) => ({ label: `${d.name} (${d.rows}×${d.cols})`, value: d.id }))}
          />
          <Input
            size="small"
            placeholder="搜索变量"
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <Button size="small" icon={<ClearOutlined />} onClick={() => {
              variables.forEach((v) => onSelectVar(v.name, false));
              message.success('已清除全部选择');
            }}>清除</Button>
            <Button size="small" icon={<CopyOutlined />} onClick={() => {
              const text = Array.from(selectedVars).join('\n');
              navigator.clipboard.writeText(text).then(() => message.success('已复制到剪贴板'));
            }}>复制</Button>
            <Button size="small" icon={<SnippetsOutlined />} onClick={async () => {
              try {
                const text = await navigator.clipboard.readText();
                const names = text.split(/[\n,]/).map((s) => s.trim()).filter((s) => s);
                const valid = names.filter((n) => variables.some((v) => v.name === n));
                valid.forEach((n) => onSelectVar(n, true));
                message.success(`粘贴了${valid.length}个变量`);
              } catch {
                message.error('无法读取剪贴板');
              }
            }}>粘贴</Button>
          </div>
        </Space>
      }
    >
      <Space direction="vertical" size={2} style={{ width: '100%' }}>
        {filtered.map((v) => (
          <div
            key={v.name}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '4px 6px',
              borderRadius: 4,
              background: selectedVars.has(v.name) ? '#f6ffed' : 'transparent',
              cursor: 'pointer',
            }}
            onClick={() => onSelectVar(v.name, !selectedVars.has(v.name))}
          >
            <Checkbox
              checked={selectedVars.has(v.name)}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => handleCheck(e, v.name)}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Text style={{ fontSize: 13 }} ellipsis>{v.name}</Text>
                <Select
                  size="small"
                  value={v.type}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(type) => onTypeChange?.(v.name, type)}
                  options={[
                    { label: '连续', value: 'continuous' },
                    { label: '分类', value: 'categorical' },
                    { label: '逻辑', value: 'logical' },
                  ]}
                  style={{ width: 64 }}
                  styles={{ popup: { root: { minWidth: 80 } } }}
                />
              </div>
              <Text type="secondary" style={{ fontSize: 11 }}>{v.range_str} | 缺失{v.missing_count}</Text>
            </div>
          </div>
        ))}
      </Space>
    </Card>
  );
};

export default VariablePanel;
