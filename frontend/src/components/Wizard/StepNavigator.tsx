import React from 'react';
import { Steps } from 'antd';
import { useWizard } from '@/context/WizardContext';

const stepItems = [
  { title: '数据准备' },
  { title: '变量诊断' },
  { title: '变量筛选' },
  { title: '模型构建' },
  { title: '模型评估' },
  { title: '可视化' },
  { title: '模型解释性' },
  { title: '高级诊断' },
  { title: '模型验证' },
  { title: '导出报告' },
];

const StepNavigator: React.FC = () => {
  const { state, goToStep } = useWizard();
  const { currentStep, completedSteps } = state;

  return (
    <Steps
      direction="vertical"
      current={currentStep}
      onChange={(step) => {
        // Only allow navigation to completed steps or current step
        if (completedSteps.has(step) || step === currentStep) {
          goToStep(step);
        }
      }}
      items={stepItems.map((item, idx) => ({
        title: item.title,
        description: completedSteps.has(idx) ? '已完成' : idx === currentStep ? '进行中' : '',
      }))}
      style={{ padding: '16px 8px', background: '#fff', borderRadius: 8 }}
    />
  );
};

export default StepNavigator;
