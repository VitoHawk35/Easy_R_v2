import React, { useState } from 'react';
import { Card, Checkbox, Radio, Button, Space, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { useWizard } from '@/context/WizardContext';
import { generateReport, downloadReportFile } from '@/services/api';

const Step10Report: React.FC = () => {
  const { state, markComplete } = useWizard();
  const [format, setFormat] = useState<'pdf' | 'word'>('word');
  const [sections, setSections] = useState<string[]>([
    'diagnosis', 'filter', 'build', 'eval', 'viz', 'explain', 'validation'
  ]);
  const [loading, setLoading] = useState(false);
  const [filename, setFilename] = useState('');
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');

  const runGenerate = async () => {
    setLoading(true);
    try {
      const reportData: any = {
        dataset_name: state.datasetInfo?.name || '',
        y_variable: state.yVariable,
        group_variable: state.groupVariable || undefined,
        model_type: state.bestModel,
        sections: [],
      };

      if (sections.includes('diagnosis') && state.diagnosisResult) {
        reportData.sections.push({ title: '变量诊断', ...state.diagnosisResult });
      }
      if (sections.includes('filter') && state.filterResults) {
        reportData.sections.push({
          title: '变量筛选',
          summary: `最终筛选变量: ${state.filterResults.final.join(', ')}`,
          tables: [{ title: '筛选结果', headers: ['方法', '变量数', '变量列表'], rows: [
            ['单因素', state.filterResults.univariate.length, state.filterResults.univariate.join(', ')],
            ['LASSO', state.filterResults.lasso.length, state.filterResults.lasso.join(', ')],
            ['随机森林', state.filterResults.rf.length, state.filterResults.rf.join(', ')],
            ['Boruta', state.filterResults.boruta.length, state.filterResults.boruta.join(', ')],
          ]}],
          charts: [],
        });
      }
      if (sections.includes('build') && state.buildResult) {
        reportData.sections.push({ title: '模型构建', ...state.buildResult });
      }
      if (sections.includes('eval') && state.evalResults) {
        reportData.sections.push({ title: '模型评估', ...state.evalResults });
      }
      if (sections.includes('viz') && state.vizResults) {
        reportData.sections.push({ title: '可视化', ...state.vizResults });
      }
      if (sections.includes('explain') && state.explainResults) {
        reportData.sections.push({ title: '模型解释性', ...state.explainResults });
      }
      if (sections.includes('validation') && state.validationResults) {
        reportData.sections.push({ title: '模型验证', ...state.validationResults });
      }

      const res = await generateReport(reportData, format);
      setFilename(res.filename);
      setPreviewHtml(res.preview_html || '');
      markComplete(9);
      message.success('报告生成完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '报告生成失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!filename) return;
    setDownloadLoading(true);
    try {
      // 必须走 axios，带 Authorization 头；直接打开 URL 会 401。
      await downloadReportFile(filename);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '下载失败');
    } finally {
      setDownloadLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="报告内容" size="small">
        <Checkbox.Group
          value={sections}
          onChange={(vals) => setSections(vals as string[])}
          options={[
            { label: '变量诊断', value: 'diagnosis' },
            { label: '变量筛选', value: 'filter' },
            { label: '模型构建', value: 'build' },
            { label: '模型评估', value: 'eval' },
            { label: '可视化', value: 'viz' },
            { label: '模型解释性', value: 'explain' },
            { label: '模型验证', value: 'validation' },
          ]}
        />
      </Card>

      <Card title="报告格式" size="small">
        <Radio.Group value={format} onChange={(e) => setFormat(e.target.value)}>
          <Radio.Button value="word">Word</Radio.Button>
          <Radio.Button value="pdf">PDF</Radio.Button>
        </Radio.Group>
      </Card>

      <Button
        type="primary"
        icon={<DownloadOutlined />}
        loading={loading}
        onClick={runGenerate}
        block
      >
        生成报告
      </Button>

      {filename && (
        <Button
          type="default"
          loading={downloadLoading}
          onClick={handleDownload}
          block
        >
          下载报告
        </Button>
      )}

      {previewHtml && (
        <Card title="报告预览" size="small">
          <iframe
            title="报告预览"
            srcDoc={previewHtml}
            sandbox=""
            style={{ width: '100%', height: 600, border: '1px solid var(--c-line-cool)', borderRadius: 4 }}
          />
        </Card>
      )}
    </Space>
  );
};

export default Step10Report;
