import React, { useEffect } from 'react';
import { Layout, Button, Space, Divider } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import { useWizard } from '@/context/WizardContext';
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

const { Sider, Content } = Layout;

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

  return (
    <Layout style={{ minHeight: '100%', background: '#f5f5f5' }}>
      <Sider width={200} style={{ background: 'transparent', marginRight: 16 }}>
        <StepNavigator />
      </Sider>
      <Content style={{ background: '#fff', padding: 24, borderRadius: 8, overflow: 'auto' }}>
        <h2 style={{ marginTop: 0, marginBottom: 16, color: '#2f855a' }}>
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
        <Divider style={{ margin: '24px 0' }} />
        <Space>
          <Button
            icon={<LeftOutlined />}
            disabled={!canGoPrev}
            onClick={() => goToStep(currentStep - 1)}
          >
            上一步
          </Button>
          <Button
            type="primary"
            icon={<RightOutlined />}
            disabled={!canGoNext || currentStep >= 9}
            onClick={() => goToStep(currentStep + 1)}
          >
            下一步
          </Button>
        </Space>
      </Content>
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
