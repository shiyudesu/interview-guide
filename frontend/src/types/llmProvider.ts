export interface ProviderItem {
  id: string;
  baseUrl: string;
  maskedApiKey: string;
  hasApiKey: boolean;
  model: string;
  embeddingModel: string | null;
  embeddingDimensions: number | null;
  supportsEmbedding: boolean;
  temperature: number | null;
  defaultChatProvider: boolean;
  defaultEmbeddingProvider: boolean;
}

export interface CreateProviderRequest {
  id: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  embeddingModel?: string;
  embeddingDimensions?: number;
  supportsEmbedding?: boolean;
  temperature?: number;
}

export interface UpdateProviderRequest {
  baseUrl?: string;
  apiKey?: string;
  model?: string;
  embeddingModel?: string;
  embeddingDimensions?: number;
  supportsEmbedding?: boolean;
  temperature?: number;
}

export interface ProviderTestResult {
  success: boolean;
  message: string;
  model: string;
}

export interface ModelDiscoveryRequest {
  providerId?: string;
  baseUrl?: string;
  apiKey?: string;
  refresh?: boolean;
}

export interface ProviderModelList {
  chatModels: string[];
  embeddingModels: string[];
  source: 'remote' | 'configured';
  warning: string | null;
}

export interface DefaultProvider {
  defaultProvider: string;
  defaultEmbeddingProvider: string;
}

export interface AsrConfig {
  providerId: string;
  url: string;
  model: string;
  maskedApiKey: string;
  language: string;
  format: string;
  sampleRate: number;
  enableTurnDetection: boolean;
  turnDetectionType: string;
  turnDetectionThreshold: number;
  turnDetectionSilenceDurationMs: number;
}

export interface TtsConfig {
  providerId: string;
  url: string;
  model: string;
  maskedApiKey: string;
  voice: string;
  format: string;
  sampleRate: number;
  mode: string;
  languageType: string;
  speechRate: number;
  volume: number;
}

export interface AsrConfigRequest {
  providerId?: string;
  url?: string;
  model?: string;
  apiKey?: string;
  language?: string;
  format?: string;
  sampleRate?: number;
  enableTurnDetection?: boolean;
  turnDetectionType?: string;
  turnDetectionThreshold?: number;
  turnDetectionSilenceDurationMs?: number;
}

export interface TtsConfigRequest {
  providerId?: string;
  url?: string;
  model?: string;
  apiKey?: string;
  voice?: string;
  format?: string;
  sampleRate?: number;
  mode?: string;
  languageType?: string;
  speechRate?: number;
  volume?: number;
}
