import React, { useEffect } from 'react';
import { Layout, Button, Divider, Space } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import { useWizard, effectiveModelFeatures } from '@/context/WizardContext';
import StepNavigator from './StepNavigator';
import Step1DataPrep from './steps/Step1DataPrep';
import Step2Diagnostics from './steps/Step2Diagnostics';
import Step3VarFilter from './steps/Step3VarFilter';
import Step4ModelBuild from './steps/Step4ModelBuild';
import Step5Eval from './steps/Step5Eval';
import Step6Visual from './steps/Step6Visual';
import Step7Explain from './steps/Step7Explain';
import Step8AdvDiag from './steps/Step8AdvDiag';
import Step9Validate from './steps/Step9Validate';
import Step10Report from './steps/Step10Report';
import type { VariableInfo, DatasetInfo } from '@/types';

const { Content } = Layout;

const stepComponents = [
  Step1DataPrep,
  Step2Diagnostics,
  Step3VarFilter,
  Step4ModelBuild,
  Step5Eval,
  Step6Visual,
  Step7Explain,
  Step8AdvDiag,
  Step9Validate,
  Step10Report,
];

const stepTitles = [
  '数据准备',
  '变量诊断',
  '变量筛选',
  '模型构建',
  '模型评估',
  '可视化',
  '模型解释性',
  '高级诊断',
  '模型验证',
  '导出报告',
];

interface WizardInnerProps {
  datasets: DatasetInfo[];
  onDatasetChange: (id: string) => void;
  variables: VariableInfo[];
}

/** 可点击的配置摘要 pill；仅做导航，不修改状态。 */
const SummaryPill: React.FC<{ label: string; value: string; onClick: () => void }> = ({
  label,
  value,
  onClick,
}) => (
  <span
    role="button"
    tabIndex={0}
    className="pill-soft"
    style={{ cursor: 'pointer' }}
    onClick={onClick}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') onClick();
    }}
  >
    {label} <strong>{value}</strong>
  </span>
);

const WizardInner: React.FC<WizardInnerProps> = ({ datasets, onDatasetChange, variables }) => {
  const { state, dispatch, goToStep } = useWizard();
  const { currentStep, completedSteps } = state;

  useEffect(() => {
    // 变量列表尚未加载完成时不要覆盖从 sessionStorage 恢复的 allVariables
    if (variables.length > 0) {
      dispatch({ type: 'SET_ALL_VARIABLES', payload: variables });
    }
  }, [variables, dispatch]);

  // 使用 any 类型断言，绕过严苛的 props 检查
  const CurrentStepComponent = stepComponents[currentStep] as any;

  const canGoNext = completedSteps.has(currentStep);
  const canGoPrev = currentStep > 0;

  // 配置摘要（Appearance only：数据全部来自现有 WizardState）
  const datasetName = state.datasetInfo?.name || state.datasetId || '未选择';
  const yName = state.yVariable || '未选择';
  const groupName = state.groupVariable || '未设置';
  const featureCount = effectiveModelFeatures(state).length;
  const modelName = state.selectedModel
    || state.bestModel
    || (state.buildMode === 'compare' && state.compareModels.length > 0
      ? `${state.compareModels.length} 个模型对比`
      : '未选择');

  return (
    <Layout
      style={{
        height: '100%',
        minHeight: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--c-canvas-soft)',
      }}
    >
      <div style={{ background: 'var(--c-canvas)', borderRadius: 12, padding: '16px 16px 10px', marginBottom: 12 }}>
        <StepNavigator />
        <Divider style={{ margin: '8px 0 10px' }} />
        <Space size={[8, 8]} wrap>
          <SummaryPill label="数据集" value={datasetName} onClick={() => goToStep(0)} />
          <SummaryPill label="结局" value={`Y=${yName}`} onClick={() => goToStep(0)} />
          <SummaryPill label="分组" value={groupName} onClick={() => goToStep(0)} />
          <SummaryPill label="特征" value={`${featureCount}`} onClick={() => goToStep(2)} />
          <SummaryPill label="模型" value={modelName} onClick={() => goToStep(3)} />
        </Space>
      </div>

      <Content
        style={{
          background: 'var(--c-canvas)',
          padding: 24,
          borderRadius: 12,
          overflow: 'auto',
          flex: 1,
          minHeight: 0,
        }}
      >
        <h2 style={{ marginTop: 0, marginBottom: 16, color: 'var(--c-ink)' }}>
          {stepTitles[currentStep]}
        </h2>
        <Divider style={{ margin: '12px 0' }} />
        {currentStep === 0 ? (
          <CurrentStepComponent
            datasets={datasets}
            onDatasetChange={onDatasetChange}
            variables={variables}
          />
        ) : (
          <CurrentStepComponent />
        )}
      </Content>

      <footer
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          height: 64,
          marginTop: 12,
          padding: '0 24px',
          background: 'var(--c-canvas)',
          borderTop: '1px solid var(--c-line-cool)',
          boxShadow: '0 -1px 3px rgba(0,0,0,.06)',
          borderRadius: 12,
        }}
      >
        <Button
          icon={<LeftOutlined />}
          disabled={!canGoPrev}
          onClick={() => goToStep(currentStep - 1)}
        >
          上一步
        </Button>
        <span className="mono-num" style={{ fontSize: 12, color: 'var(--c-mute)' }}>
          已完成 {completedSteps.size}/10 步
        </span>
        <Button
          type="primary"
          disabled={!canGoNext || currentStep >= 9}
          onClick={() => goToStep(currentStep + 1)}
        >
          运行并继续 <RightOutlined />
        </Button>
      </footer>
    </Layout>
  );
};

interface WizardContainerProps {
  datasets: DatasetInfo[];
  onDatasetChange: (id: string) => void;
  variables: VariableInfo[];
}

/** WizardProvider 已提升到 App 层，这里只负责渲染向导内部（E4a）。 */
const WizardContainer: React.FC<WizardContainerProps> = (props) => {
  return <WizardInner {...props} />;
};

export default WizardContainer;
