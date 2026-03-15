const ACCESS_TOKEN_KEY = 'vf_access_token';

export const getStoredToken = (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY);
export const setStoredToken = (t: string) => localStorage.setItem(ACCESS_TOKEN_KEY, t);
export const clearStoredToken = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem('vf_refresh_token');
  localStorage.removeItem('vf_user');
};
