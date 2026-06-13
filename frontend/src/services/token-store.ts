const ACCESS_TOKEN_KEY = 'vf_access_token';
const REFRESH_TOKEN_KEY = 'vf_refresh_token';

export const getStoredToken = (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY);
export const setStoredToken = (t: string) => localStorage.setItem(ACCESS_TOKEN_KEY, t);
export const getStoredRefreshToken = (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY);
export const clearStoredToken = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem('vf_user');
};
