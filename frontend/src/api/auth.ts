import request from './request';

export interface AuthConfig {
  authEnabled: boolean;
  registrationEnabled: boolean;
}

export interface AuthUser {
  id: string;
  email: string;
  displayName: string | null;
  role: string;
  status: string;
  createdAt: string;
}

export interface AuthSession {
  user: AuthUser;
  csrfToken: string;
}

export interface RegistrationResult {
  email: string;
  verificationRequired: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest extends LoginRequest {
  displayName?: string;
}

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

export const authApi = {
  config(): Promise<AuthConfig> {
    return request.get<AuthConfig>('/api/auth/config');
  },

  me(): Promise<AuthSession> {
    return request.get<AuthSession>('/api/auth/me');
  },

  login(payload: LoginRequest): Promise<AuthSession> {
    return request.post<AuthSession>('/api/auth/login', payload);
  },

  register(payload: RegisterRequest): Promise<RegistrationResult> {
    return request.post<RegistrationResult>('/api/auth/register', payload);
  },

  requestEmailVerification(email: string): Promise<void> {
    return request.post<void>('/api/auth/email/verification/request', { email });
  },

  confirmEmailVerification(token: string): Promise<void> {
    return request.post<void>('/api/auth/email/verification/confirm', { token });
  },

  requestPasswordReset(email: string): Promise<void> {
    return request.post<void>('/api/auth/password/reset/request', { email });
  },

  confirmPasswordReset(token: string, newPassword: string): Promise<void> {
    return request.post<void>('/api/auth/password/reset/confirm', { token, newPassword });
  },

  logout(): Promise<void> {
    return request.post<void>('/api/auth/logout');
  },

  changePassword(payload: ChangePasswordRequest): Promise<void> {
    return request.post<void>('/api/auth/password/change', payload);
  },

  revokeSessions(): Promise<void> {
    return request.post<void>('/api/auth/sessions/revoke');
  },
};
