import React from 'react';
import { Card, Table, Typography, Space, Alert, Tabs, Button } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import type { MLResult } from '@/types';

const { Text } = Typography;

interface ResultDisplayProps {
  result: MLResult | null;
  loading: boolean;
}

const ResultDisplay: React.FC<ResultDisplayProps> = ({ result, loading }) => {
  if (!result) return null;

  const handleDownloadTable = (table: { title: string; headers: string[]; rows: any[][] }) => {
    const csv = [
      table.headers.join(','),
      ...table.rows.map((row) => row.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${table.title}.csv`;
    link.click();
  };

  const chartItems = result.charts.map((chart, idx) => ({
    key: `chart-${idx}`,
    label: chart.title || `图${idx + 1}`,
    children: (
      <Card size="small" title={chart.title}>
        {chart.type === 'svg' ? (
          <div dangerouslySetInnerHTML={{ __html: chart.data }} style={{ maxWidth: '100%', overflow: 'auto' }} />
        ) : (
          <img src={`data:image/png;base64,${chart.data}`} alt={chart.title} style={{ maxWidth: '100%' }} />
        )}
      </Card>
    ),
  }));

  const tableItems = result.tables.map((table, idx) => ({
    key: `table-${idx}`,
    label: table.title || `表${idx + 1}`,
    children: (
      <Card
        size="small"
        title={table.title}
        extra={
          <Button icon={<DownloadOutlined />} size="small" onClick={() => handleDownloadTable(table)}>下载</Button>
        }
      >
        <Table
          size="small"
          bordered
          pagination={{ pageSize: 20 }}
          columns={table.headers.map((h) => ({ title: h, dataIndex: h, key: h }))}
          dataSource={table.rows.map((row, i) => {
            const obj: Record<string, any> = { key: i };
            table.headers.forEach((h, j) => {
              obj[h] = row[j];
            });
            return obj;
          })}
          scroll={{ x: 'max-content' }}
        />
      </Card>
    ),
  }));

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* E7a 过渡措施（不需方案确认）：固定警示语 */}
      <Alert
        type="warning"
        showIcon
        message="变量筛选在全部数据上完成，内部验证结果偏乐观"
      />
      {result.summary && (
        <Alert message={result.summary} type="info" showIcon />
      )}
      {result.charts.length > 0 && (
        <Tabs type="card" items={chartItems} />
      )}
      {result.tables.length > 0 && (
        <Tabs type="card" items={tableItems} />
      )}
    </Space>
  );
};

export default ResultDisplay;
