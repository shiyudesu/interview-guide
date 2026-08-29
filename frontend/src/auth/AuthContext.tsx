import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  authApi,
  type AuthSession,
  type AuthUser,
  type ChangePasswordRequest,
  type LoginRequest,
  type RegisterRequest,
  type RegistrationResult,
} from '../api/auth';
import { AUTH_UNAUTHORIZED_EVENT, setCsrfToken } from '../api/request';

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  authenticationEnabled: boolean;
  registrationEnabled: boolean;
  competitionMode: boolean;
  login: (payload: LoginRequest) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<RegistrationResult>;
  logout: () => Promise<void>;
  changePassword: (payload: ChangePasswordRequest) => Promise<void>;
  revokeSessions: () => Promise<void>;
}

const LEGACY_USER: AuthUser = {
  id: 'legacy-single-user',
  email: '本地单用户模式',
  displayName: '本地用户',
  role: 'ADMIN',
  status: 'ACTIVE',
  createdAt: '',
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authenticationEnabled, setAuthenticationEnabled] = useState(true);
  const [registrationEnabled, setRegistrationEnabled] = useState(false);
  const [competitionMode, setCompetitionMode] = useState(false);

  const applySession = useCallback((session: AuthSession) => {
    setCsrfToken(session.csrfToken);
    setUser(session.user);
  }, []);

  const clearSession = useCallback(() => {
    setCsrfToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    let active = true;

    const bootstrap = async () => {
      try {
        const config = await authApi.config();
        if (!active) return;
        const enabled = config.authEnabled;
        setAuthenticationEnabled(enabled);
        setRegistrationEnabled(config.registrationEnabled);
        setCompetitionMode(config.competitionMode);
        if (!enabled) {
          setCsrfToken(null);
          setUser(LEGACY_USER);
          return;
        }
        const session = await authApi.me();
        if (active) applySession(session);
      } catch {
        if (active) clearSession();
      } finally {
        if (active) setLoading(false);
      }
    };

    void bootstrap();
    return () => {
      active = false;
    };
  }, [applySession, clearSession]);

  useEffect(() => {
    const handleUnauthorized = () => {
      if (authenticationEnabled) clearSession();
    };
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
  }, [authenticationEnabled, clearSession]);

  const login = useCallback(async (payload: LoginRequest) => {
    applySession(await authApi.login(payload));
  }, [applySession]);

  const register = useCallback(async (payload: RegisterRequest) => {
    return authApi.register(payload);
  }, []);

  const logout = useCallback(async () => {
    try {
      if (authenticationEnabled) await authApi.logout();
    } finally {
      clearSession();
    }
  }, [authenticationEnabled, clearSession]);

  const changePassword = useCallback(async (payload: ChangePasswordRequest) => {
    await authApi.changePassword(payload);
    clearSession();
  }, [clearSession]);

  const revokeSessions = useCallback(async () => {
    await authApi.revokeSessions();
    clearSession();
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    authenticationEnabled,
    registrationEnabled,
    competitionMode,
    login,
    register,
    logout,
    changePassword,
    revokeSessions,
  }), [
    user,
    loading,
    authenticationEnabled,
    registrationEnabled,
    competitionMode,
    login,
    register,
    logout,
    changePassword,
    revokeSessions,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
