import axios from 'axios';
import type { DatasetInfo, VariableInfo, MLRequest, MLResult, DataTransformConfig, DataTransformResponse, VariableType, AuthRequest, AuthResponse, User, HistoryListItem, HistoryDetail, PredictionResponse } from '@/types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('easyr_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('easyr_token');
    }
    return Promise.reject(error);
  }
);

export async function listDatasets(): Promise<DatasetInfo[]> {
  const res = await api.get('/datasets');
  return res.data;
}

export async function getVariables(datasetId: string): Promise<{ total: number; selected: number; variables: VariableInfo[] }> {
  const res = await api.get(`/datasets/${datasetId}/variables`);
  return res.data;
}

export async function runML(algorithm: string, request: MLRequest): Promise<MLResult> {
  const res = await api.post(`/ml/${algorithm}`, request);
  return res.data;
}

export async function predict(request: MLRequest): Promise<PredictionResponse> {
  const res = await api.post('/ml/predict', request);
  return res.data;
}

export async function uploadDataset(file: File): Promise<DatasetInfo> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post('/datasets/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function previewDataset(datasetId: string, limit: number = 20): Promise<{ rows: number; cols: number; columns: string[]; data: any[] }> {
  const res = await api.post(`/datasets/${datasetId}/preview?limit=${limit}`);
  return res.data;
}

export async function transformDataset(request: DataTransformConfig): Promise<DataTransformResponse> {
  const res = await api.post('/datasets/transform', request);
  return res.data;
}

export async function runDiagnostics(type: 'missing' | 'correlation', request: MLRequest): Promise<MLResult> {
  const res = await api.post(`/diagnostics/${type}`, request);
  return res.data;
}

export async function runExternalValidation(file: File, datasetId: string, modelType: string, yVariable: string, xVariables: string[], params: Record<string, any>, seed: number = 123, variableTypes: Record<string, VariableType> = {}): Promise<MLResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('dataset_id', datasetId);
  formData.append('model_type', modelType);
  formData.append('y_variable', yVariable);
  formData.append('x_variables', xVariables.join(','));
  formData.append('params', JSON.stringify(params));
  formData.append('seed', String(seed));
  formData.append('variable_types', JSON.stringify(variableTypes));
  const res = await api.post('/eval/external', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function generateReport(reportData: any, format: 'pdf' | 'word' = 'word'): Promise<{ success: boolean; download_url: string; filename: string; preview_html?: string }> {
  const res = await api.post('/report/generate', { ...reportData, format });
  return res.data;
}

export async function downloadReportFile(filename: string): Promise<void> {
  const res = await api.get(`/report/download/${encodeURIComponent(filename)}`, {
    responseType: 'blob',
  });
  const contentType = (res.headers['content-type'] as string) || 'application/octet-stream';
  const blob = new Blob([res.data], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function login(request: AuthRequest): Promise<AuthResponse> {
  const res = await api.post('/auth/login', request);
  return res.data;
}

export async function register(request: AuthRequest): Promise<AuthResponse> {
  const res = await api.post('/auth/register', request);
  return res.data;
}

export async function getMe(): Promise<User> {
  const res = await api.get('/auth/me');
  return res.data;
}

export async function listHistory(): Promise<HistoryListItem[]> {
  const res = await api.get('/history');
  return res.data;
}

export async function getHistory(historyId: string): Promise<HistoryDetail> {
  const res = await api.get(`/history/${historyId}`);
  return res.data;
}

export async function deleteHistory(historyId: string): Promise<void> {
  await api.delete(`/history/${historyId}`);
}

export default api;
