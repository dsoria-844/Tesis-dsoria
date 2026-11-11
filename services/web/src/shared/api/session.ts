const KEY = "hp_token";

// Chart granularity chosen on the dashboard: kept while the session lasts, reset on logout.
export const VISTA_KEY = "hp_vista_grafico";

export const session = {
  get token(): string | null {
    return sessionStorage.getItem(KEY);
  },
  set(t: string) {
    sessionStorage.setItem(KEY, t);
  },
  clear() {
    sessionStorage.removeItem(KEY);
    // UI preferences that must last only for the logged-in session
    try {
      sessionStorage.removeItem(VISTA_KEY);
    } catch {
      /* storage unavailable */
    }
  },
};
