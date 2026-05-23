import { create } from "zustand";
import type { TokenResponse, UserOut } from "../api/types";

const ACCESS = "qf_access";
const REFRESH = "qf_refresh";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserOut | null;
  setTokens: (t: TokenResponse) => void;
  setUser: (u: UserOut | null) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  accessToken: localStorage.getItem(ACCESS),
  refreshToken: localStorage.getItem(REFRESH),
  user: null,
  setTokens: (t) => {
    localStorage.setItem(ACCESS, t.access_token);
    localStorage.setItem(REFRESH, t.refresh_token);
    set({ accessToken: t.access_token, refreshToken: t.refresh_token });
  },
  setUser: (u) => set({ user: u }),
  logout: () => {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
    set({ accessToken: null, refreshToken: null, user: null });
  },
}));
