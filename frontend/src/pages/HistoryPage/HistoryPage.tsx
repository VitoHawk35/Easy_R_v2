import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, message, Card, Spin, Typography } from 'antd';
import { EyeOutlined, DeleteOutlined, RollbackOutlined } from '@ant-design/icons';
import type { HistoryListItem, HistoryDetail } from '@/types';
import { listHistory, getHistory, deleteHistory } from '@/services/api';
import ResultDisplay from '@/components/ResultDisplay/ResultDisplay';

const { Text } = Typography;

interface HistoryPageProps {
  onRestoreWizard?: (snapshot: any) => void;
}

const HistoryPage: React.FC<HistoryPageProps> = ({ onRestoreWizard }) => {
  const [items, setItems] = useState<HistoryListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState<string | null>(null);

  const fetchList = async () => {
    setLoading(true);
    try {
      const data = await listHistory();
      setItems(data);
    } catch {
      message.error('加载历史记录失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, []);

  const handleView = async (id: string) => {
    setDetailLoading(true);
    setDetailOpen(true);
    try {
      const data = await getHistory(id);
      setDetail(data);
    } catch {
      message.error('加载详情失败');
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，是否继续？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteHistory(id);
          message.success('删除成功');
          setItems((prev) => prev.filter((item) => item.id !== id));
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const handleRestoreWizard = async (id: string) => {
    setRestoreLoading(id);
    try {
      const data = await getHistory(id);
      const snapshot = data.wizard_snapshot;
      if (!snapshot || Object.keys(snapshot).length === 0) {
        message.warning('该记录不支持向导恢复');
        return;
      }
      onRestoreWizard?.(snapshot);
      message.success('已恢复向导状态');
    } catch {
      message.error('恢复向导失败');
    } finally {
      setRestoreLoading(null);
    }
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
      width: 180,
    },
    {
      title: '分析方法',
      dataIndex: 'algorithm',
      key: 'algorithm',
      width: 160,
    },
    {
      title: '数据集',
      dataIndex: 'dataset_name',
      key: 'dataset_name',
      width: 160,
    },
    {
      title: 'Y变量',
      dataIndex: 'y_variable',
      key: 'y_variable',
      width: 120,
    },
    {
      title: '特征数',
      dataIndex: 'feature_count',
      key: 'feature_count',
      width: 80,
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      render: (_: any, record: HistoryListItem) => (
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => handleView(record.id)}>
            查看
          </Button>
          <Button
            icon={<RollbackOutlined />}
            size="small"
            loading={restoreLoading === record.id}
            onClick={() => handleRestoreWizard(record.id)}
          >
            恢复向导
          </Button>
          <Button icon={<DeleteOutlined />} size="small" danger onClick={() => handleDelete(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card title="分析历史记录" size="small">
        <Table
          columns={columns}
          dataSource={items}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 'max-content' }}
        />
      </Card>

      <Modal
        title="历史分析详情"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={960}
        destroyOnClose
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin tip="加载中..." />
          </div>
        ) : detail ? (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text strong>方法: </Text>
              <Text>{detail.algorithm}</Text>
              <br />
              <Text strong>数据集: </Text>
              <Text>{detail.dataset_name}</Text>
              <br />
              <Text strong>Y变量: </Text>
              <Text>{detail.y_variable}</Text>
              <br />
              <Text strong>时间: </Text>
              <Text>{new Date(detail.created_at).toLocaleString()}</Text>
            </div>
            <ResultDisplay result={detail.result} loading={false} />
          </Space>
        ) : null}
      </Modal>
    </div>
  );
};

export default HistoryPage;
