import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Tabs, message, Button, Space, Spin } from 'antd';
import { HistoryOutlined, LogoutOutlined, UserOutlined } from '@ant-design/icons';
import type { VariableInfo, DatasetInfo, VariableType } from '@/types';
import { listDatasets, getVariables } from '@/services/api';
import { useAuth } from '@/context/AuthContext';
import { WizardProvider, useWizard, loadPersistedWizardState } from '@/context/WizardContext';
import Sidebar from '@/components/Layout/Sidebar';
import VariablePanel from '@/components/VariablePanel/VariablePanel';
import MLPage from '@/pages/MLPage/MLPage';
import WizardContainer from '@/components/Wizard/WizardContainer';
import AuthPage from '@/pages/AuthPage/AuthPage';
import HistoryPage from '@/pages/HistoryPage/HistoryPage';

const { Content } = Layout;

interface TabItem {
  key: string;
  label: string;
  datasetId: string;
  algorithm?: string;
  type?: 'algorithm' | 'wizard' | 'history';
}

const WIZARD_TAB_KEY = 'wizard-analysis';
const HISTORY_TAB_KEY = 'history-page';

/**
 * E4a：WizardProvider 提升到 App 层，包住整个标签页区域。
 * 切换标签页时 WizardInner 卸载但 Provider 不卸载，向导状态不会丢失。
 */
const AppShell: React.FC = () => {
  const { user, logout } = useAuth();
  const { dispatch } = useWizard();
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [activeDataset, setActiveDataset] = useState<string>('');
  const [variables, setVariables] = useState<VariableInfo[]>([]);
  const [selectedVars, setSelectedVars] = useState<Set<string>>(new Set());
  const [tabs, setTabs] = useState<TabItem[]>([]);
  const [activeTab, setActiveTab] = useState<string>('');

  useEffect(() => {
    if (!user) return;
    listDatasets().then((ds) => {
      setDatasets(ds);
      if (ds.length > 0) {
        const first = ds[0].id;
        setActiveDataset(first);
        loadVars(first);
      }
    }).catch(() => message.error('加载数据集失败'));
  }, [user]);

  const loadVars = useCallback((datasetId: string, clearSelection = true) => {
    getVariables(datasetId).then((res) => {
      setVariables(res.variables);
      if (clearSelection) setSelectedVars(new Set());
    }).catch(() => message.error('加载变量失败'));
  }, []);

  const handleDatasetChange = (datasetId: string) => {
    setActiveDataset(datasetId);
    loadVars(datasetId);
  };

  const handleAddTab = (label: string, algorithm: string) => {
    const key = `${algorithm}-${Date.now()}`;
    const newTab: TabItem = { key, label, datasetId: activeDataset, algorithm, type: 'algorithm' };
    setTabs((prev) => [...prev, newTab]);
    setActiveTab(key);
  };

  const handleEnterWizard = (snapshot?: any) => {
    // 从历史记录恢复：直接 dispatch RESTORE_SNAPSHOT（Provider 已在 App 层）
    if (snapshot) {
      dispatch({ type: 'RESTORE_SNAPSHOT', payload: snapshot });
    }
    // 刷新/重登后从 sessionStorage 恢复向导时，同步其数据集，避免变量列表不匹配
    const restored = !snapshot ? loadPersistedWizardState() : null;
    const targetDatasetId = snapshot?.datasetId || (restored as any)?.datasetId || activeDataset;

    setTabs((prev) => {
      const next = prev.filter((t) => t.key !== WIZARD_TAB_KEY);
      next.push({
        key: WIZARD_TAB_KEY,
        label: '机器学习向导',
        datasetId: targetDatasetId,
        type: 'wizard',
      });
      return next;
    });
    setActiveTab(WIZARD_TAB_KEY);
    if (targetDatasetId && targetDatasetId !== activeDataset) {
      setActiveDataset(targetDatasetId);
      loadVars(targetDatasetId, false);
    }
  };

  const handleEnterHistory = () => {
    const existing = tabs.find((t) => t.key === HISTORY_TAB_KEY);
    if (existing) {
      setActiveTab(HISTORY_TAB_KEY);
    } else {
      const newTab: TabItem = { key: HISTORY_TAB_KEY, label: '分析历史', datasetId: activeDataset, type: 'history' };
      setTabs((prev) => [...prev, newTab]);
      setActiveTab(HISTORY_TAB_KEY);
    }
  };

  useEffect(() => {
    // When switching tabs, sync dataset to the tab's dataset
    if (currentTab && currentTab.datasetId !== activeDataset) {
      setActiveDataset(currentTab.datasetId);
      loadVars(currentTab.datasetId, false);
    }
  }, [activeTab]);

  const handleCloseTab = (targetKey: string) => {
    setTabs((prev) => {
      const next = prev.filter((t) => t.key !== targetKey);
      if (activeTab === targetKey) {
        setActiveTab(next.length > 0 ? next[next.length - 1].key : '');
      }
      return next;
    });
  };

  const handleSelectVar = (name: string, checked: boolean) => {
    setSelectedVars((prev) => {
      const next = new Set(prev);
      if (checked) next.add(name);
      else next.delete(name);
      return next;
    });
  };

  const handleVariableTypeChange = (name: string, type: VariableType) => {
    setVariables((prev) => prev.map((variable) => (
      variable.name === name ? { ...variable, type } : variable
    )));
  };

  const currentTab = tabs.find((t) => t.key === activeTab);

  const renderContent = () => {
    if (!currentTab) {
      return (
        <div style={{ textAlign: 'center', marginTop: 120, color: '#999' }}>
          <h2>EasyR 临床数据分析系统</h2>
          <p>请从左侧导航选择功能开始分析</p>
        </div>
      );
    }

    if (currentTab.type === 'wizard') {
      return (
        <WizardContainer
          datasets={datasets}
          onDatasetChange={handleDatasetChange}
          variables={variables}
        />
      );
    }

    if (currentTab.algorithm) {
      return (
        <MLPage
          datasetId={currentTab.datasetId}
          algorithm={currentTab.algorithm}
          variables={variables}
          selectedVars={selectedVars}
          onToggleVar={handleSelectVar}
        />
      );
    }

    if (currentTab.type === 'history') {
      return <HistoryPage onRestoreWizard={handleEnterWizard} />;
    }

    return (
      <div style={{ textAlign: 'center', marginTop: 120, color: '#999' }}>
        <h2>{currentTab.label}</h2>
        <p>该功能正在开发中</p>
      </div>
    );
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar onSelectAlgorithm={handleAddTab} onEnterWizard={handleEnterWizard} />
      <Layout style={{ marginLeft: 200 }}>
        <Content style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
          <div style={{ background: '#fff', padding: '8px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div />
            <Space>
              <Button icon={<HistoryOutlined />} onClick={handleEnterHistory}>分析历史</Button>
              <span style={{ color: '#666' }}><UserOutlined /> {user?.username}</span>
              <Button icon={<LogoutOutlined />} onClick={logout}>退出登录</Button>
            </Space>
          </div>
          <div style={{ background: '#fff', padding: '8px 16px', borderBottom: '1px solid #f0f0f0' }}>
            <Tabs
              type="editable-card"
              hideAdd
              activeKey={activeTab}
              onChange={setActiveTab}
              onEdit={(targetKey, action) => {
                if (action === 'remove') handleCloseTab(targetKey as string);
              }}
              items={tabs.map((t) => ({
                key: t.key,
                label: t.label,
                closable: true,
              }))}
            />
          </div>
          <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              {renderContent()}
            </div>
            <VariablePanel
              datasets={datasets}
              activeDataset={activeDataset}
              variables={variables}
              selectedVars={selectedVars}
              onDatasetChange={handleDatasetChange}
              onSelectVar={handleSelectVar}
              onTypeChange={handleVariableTypeChange}
            />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

const App: React.FC = () => {
  const { user, loading: authLoading } = useAuth();

  if (authLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="正在恢复登录状态..." />
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  return (
    <WizardProvider>
      <AppShell />
    </WizardProvider>
  );
};

export default App;
