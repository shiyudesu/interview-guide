import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

export interface ApiProblem {
  code?: number;
  detail: string;
}

export interface PageOptions {
  limit?: number;
  offset?: number;
}

const PROBLEM_BLOB_PARSE_LIMIT = 64 * 1024;
const MUTATING_METHODS = new Set(['post', 'put', 'patch', 'delete']);

export const AUTH_UNAUTHORIZED_EVENT = 'interview-guide:auth-unauthorized';

let csrfToken: string | null = null;

export const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL ?? '';

const instance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  withCredentials: true,
});

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

instance.interceptors.request.use(config => {
  const method = config.method?.toLowerCase();
  if (csrfToken && method && MUTATING_METHODS.has(method)) {
    config.headers.set('X-CSRF-Token', csrfToken);
  }
  return config;
});

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}

export function isApiProblem(value: unknown): value is ApiProblem {
  return isRecord(value) && typeof value.detail === 'string';
}

function parseProblemText(text: string): ApiProblem | null {
  const trimmed = text.trim();
  if (!trimmed.startsWith('{')) {
    return null;
  }
  try {
    const value = JSON.parse(trimmed) as unknown;
    return isApiProblem(value) ? value : null;
  } catch {
    return null;
  }
}

function shouldTryParseBlob(blob: Blob): boolean {
  const type = blob.type.toLowerCase();
  return type.includes('json')
    || type.startsWith('text/')
    || blob.size <= PROBLEM_BLOB_PARSE_LIMIT;
}

export async function parseProblemPayload(payload: unknown): Promise<ApiProblem | null> {
  if (isApiProblem(payload)) {
    return payload;
  }
  if (payload instanceof Blob && shouldTryParseBlob(payload)) {
    return parseProblemText(await payload.text());
  }
  if (typeof payload === 'string') {
    return parseProblemText(payload);
  }
  return null;
}

export function getApiProblemError(value: unknown): Error | null {
  return isApiProblem(value) ? new Error(value.detail) : null;
}

export async function resolveBlobDownload(blob: Blob): Promise<Blob> {
  const problem = await parseProblemPayload(blob);
  if (problem) {
    throw new Error(problem.detail || '文件下载失败');
  }
  return blob;
}

instance.interceptors.response.use(
  response => response,
  async (error) => {
    if (error.response) {
      if (error.response.status === 401 && typeof window !== 'undefined') {
        window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
      }
      const problem = await parseProblemPayload(error.response.data);
      if (problem) {
        return Promise.reject(new Error(problem.detail));
      }
      if (typeof error.response.data === 'string' && error.response.data.trim()) {
        return Promise.reject(new Error(error.response.data.trim()));
      }
      return Promise.reject(new Error(`请求失败 (${error.response.status})`));
    }

    const config = error.config;
    const isUpload = config && (
      config.url?.includes('/upload')
      || config.headers?.['Content-Type']?.toString().includes('multipart')
    );
    if (isUpload) {
      return Promise.reject(new Error('上传失败，可能是网络超时或连接中断，请重试'));
    }
    return Promise.reject(new Error('网络连接失败，请检查网络'));
  },
);

export const request = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.get<T>(url, config).then(response => response.data);
  },

  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.post<T>(url, data, config).then(response => response.data);
  },

  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.put<T>(url, data, config).then(response => response.data);
  },

  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.patch<T>(url, data, config).then(response => response.data);
  },

  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.delete<T>(url, config).then(response => response.data);
  },

  upload<T>(url: string, formData: FormData, config?: AxiosRequestConfig): Promise<T> {
    return instance.post<T>(url, formData, {
      timeout: 300000,
      headers: { 'Content-Type': 'multipart/form-data' },
      ...config,
    }).then(response => response.data);
  },

  async download(url: string, config?: AxiosRequestConfig): Promise<Blob> {
    const response = await instance.get<Blob>(url, {
      ...config,
      responseType: 'blob',
    });
    return resolveBlobDownload(response.data);
  },

  getInstance(): AxiosInstance {
    return instance;
  },
};

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '未知错误';
}

export default request;
