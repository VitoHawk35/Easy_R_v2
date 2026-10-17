import React from 'react';
import { Steps } from 'antd';
import { CheckOutlined } from '@ant-design/icons';
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

/**
 * 横向步骤条：近黑数字圆圈，当前步下方 2px 绿色指示条。
 * 四种状态：完成（✓）/ 过期（warn pill「需重跑」）/ 当前（进行中）/ 未开始（灰）。
 */
const StepNavigator: React.FC = () => {
  const { state, goToStep } = useWizard();
  const { currentStep, completedSteps, staleSteps } = state;

  return (
    <Steps
      className="wizard-steps"
      direction="horizontal"
      labelPlacement="vertical"
      size="small"
      responsive={false}
      current={currentStep}
      onChange={(step) => {
        // 仅允许跳到已完成步骤或当前步骤（与 E4 行为一致）
        if (completedSteps.has(step) || step === currentStep) {
          goToStep(step);
        }
      }}
      items={stepItems.map((item, idx) => {
        const done = completedSteps.has(idx);
        const stale = staleSteps.has(idx) && !done;
        return {
          title: item.title,
          icon: done ? <CheckOutlined /> : undefined,
          status: done ? 'finish' as const : stale ? 'error' as const : undefined,
          description: stale ? <span className="pill-warn">需重跑</span> : undefined,
        };
      })}
      style={{ padding: 0, background: 'transparent' }}
    />
  );
};

export default StepNavigator;
