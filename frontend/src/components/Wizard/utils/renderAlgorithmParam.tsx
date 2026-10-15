import React from 'react';
import { InputNumber, Select, Switch, Slider, Checkbox, Input } from 'antd';
import type { AlgorithmParam } from '@/types';

export function renderAlgorithmParam(p: AlgorithmParam) {
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
        <Checkbox.Group
          options={[
            { label: 'Logistic回归', value: 'logistic' },
            { label: '决策树', value: 'decision-tree' },
            { label: '随机森林', value: 'random-forest' },
            { label: 'XGBoost', value: 'xgboost' },
            { label: 'LightGBM', value: 'lightgbm' },
            { label: 'SVM', value: 'svm' },
            { label: 'K近邻', value: 'knn' },
            { label: 'CatBoost', value: 'catboost' },
            { label: '朴素贝叶斯', value: 'naive-bayes' },
            { label: '神经网络', value: 'mlp' },
            { label: '弹性网络', value: 'elastic-net' },
            { label: 'Cox回归', value: 'cox' },
          ]}
        />
      );
    case 'string':
    default:
      return <Input style={{ width: '100%' }} />;
  }
}
