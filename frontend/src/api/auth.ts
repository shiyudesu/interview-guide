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

  register(payload: RegisterRequest): Promise<AuthSession> {
    return request.post<AuthSession>('/api/auth/register', payload);
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
