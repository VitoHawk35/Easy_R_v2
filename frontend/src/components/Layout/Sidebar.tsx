import React from 'react';
import { Layout, Menu } from 'antd';
import {
  BarChartOutlined,
  ApartmentOutlined,
  MedicineBoxOutlined,
  RobotOutlined,
  BranchesOutlined,
  DotChartOutlined,
  LineChartOutlined,
  PartitionOutlined,
  ClusterOutlined,
  HeatMapOutlined,
  RadarChartOutlined,
  StockOutlined,
  TrophyOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  FireOutlined,
  BulbOutlined,
  SafetyOutlined,
  CheckCircleOutlined,
  FileSearchOutlined,
  AreaChartOutlined,
  FundOutlined,
  CalculatorOutlined,
} from '@ant-design/icons';
import { ALGORITHMS } from '@/types';

const { Sider } = Layout;

interface SidebarProps {
  onSelectAlgorithm: (label: string, key: string) => void;
  onEnterWizard: () => void;
}

const iconMap: Record<string, React.ReactNode> = {
  boruta: <BranchesOutlined />,
  'lasso-screening': <LineChartOutlined />,
  'logistic-screening': <CheckCircleOutlined />,
  compare: <DotChartOutlined />,
  vif: <FileSearchOutlined />,
  lasso: <LineChartOutlined />,
  'lasso-predict': <LineChartOutlined />,
  'elastic-net': <LineChartOutlined />,
  logistic: <CheckCircleOutlined />,
  cox: <SafetyOutlined />,
  bkm: <PartitionOutlined />,
  'decision-tree': <ClusterOutlined />,
  'random-forest': <HeatMapOutlined />,
  xgboost: <FireOutlined />,
  lightgbm: <FireOutlined />,
  svm: <RadarChartOutlined />,
  knn: <StockOutlined />,
  lda: <TrophyOutlined />,
  qda: <ThunderboltOutlined />,
  catboost: <RobotOutlined />,
  mlp: <ExperimentOutlined />,
  tabpfn: <ThunderboltOutlined />,
  'naive-bayes': <CalculatorOutlined />,
  shap: <BulbOutlined />,
  pdp: <AreaChartOutlined />,
  calibration: <FundOutlined />,
  dca: <FundOutlined />,
  bootstrap: <SafetyOutlined />,
};

const categoryOrder = ['特征筛选', '变量诊断', '模型对比', '回归模型', '分类模型', '树模型', '梯度提升', '神经网络', '生存分析', '模型解释', '模型评估', '模型验证'];

const Sidebar: React.FC<SidebarProps> = ({ onSelectAlgorithm, onEnterWizard }) => {
  // Group algorithms by category
  const grouped: Record<string, typeof ALGORITHMS> = {};
  ALGORITHMS.forEach((alg) => {
    const cat = alg.category || '其他';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(alg);
  });

  const mlChildren = categoryOrder
    .filter((cat) => grouped[cat])
    .map((cat) => ({
      key: `cat-${cat}`,
      label: cat,
      type: 'group' as const,
      children: grouped[cat].map((alg) => ({
        key: alg.key,
        label: alg.label,
        icon: iconMap[alg.key] || <RobotOutlined />,
      })),
    }));

  const items = [
    {
      key: 'basic',
      icon: <BarChartOutlined />,
      label: '基础统计与画图',
      children: [
        { key: 'desc', label: '描述性统计' },
        { key: 'plot', label: '基础画图' },
      ],
    },
    {
      key: 'stats',
      icon: <ApartmentOutlined />,
      label: '统计模型',
      children: [
        { key: 't-test', label: 'T检验' },
        { key: 'anova', label: '方差分析' },
        { key: 'regression', label: '线性回归' },
      ],
    },
    {
      key: 'clinical',
      icon: <MedicineBoxOutlined />,
      label: '临床诊断与决策分析',
      children: [
        { key: 'roc', label: 'ROC分析' },
        { key: 'nomogram', label: '列线图' },
      ],
    },
    {
      key: 'ml',
      icon: <RobotOutlined />,
      label: '机器学习',
      children: [
        {
          key: 'ml-wizard',
          label: '向导式分析',
          icon: <RobotOutlined />,
        },
        ...mlChildren as any,
      ],
    },
  ];

  const handleClick = (e: any) => {
    if (e.key === 'ml-wizard') {
      onEnterWizard();
      return;
    }
    const alg = ALGORITHMS.find((a) => a.key === e.key);
    if (alg) {
      onSelectAlgorithm(alg.label, alg.key);
    }
  };

  return (
    <Sider
      theme="dark"
      width={200}
      style={{
        overflow: 'auto',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
      }}
    >
      <div style={{ color: '#fff', fontSize: 18, fontWeight: 'bold', padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ width: 32, height: 32, background: '#2f855a', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ color: '#fff', fontWeight: 900 }}>R</span>
        </div>
        EasyR
      </div>
      <Menu
        theme="dark"
        mode="inline"
        defaultOpenKeys={['ml']}
        items={items as any}
        onClick={handleClick}
      />
    </Sider>
  );
};

export default Sidebar;
