export interface VoiceWebSocketPageLocation {
  protocol: string;
  host: string;
}

export function resolveVoiceWebSocketUrl(
  sessionId: number,
  configuredUrl: string | null | undefined,
  pageLocation: VoiceWebSocketPageLocation = window.location,
): string {
  const websocketProtocol = pageLocation.protocol === 'https:' ? 'wss:' : 'ws:';
  const websocketPath = `/ws/voice-interview/${sessionId}`;
  const sameOriginUrl = `${websocketProtocol}//${pageLocation.host}${websocketPath}`;

  if (!configuredUrl) {
    return sameOriginUrl;
  }

  try {
    const parsed = new URL(configuredUrl, sameOriginUrl);
    if (parsed.protocol !== 'ws:' && parsed.protocol !== 'wss:') {
      return sameOriginUrl;
    }
    return parsed.toString();
  } catch {
    return sameOriginUrl;
  }
}
