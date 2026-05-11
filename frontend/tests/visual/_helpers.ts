import type { Page } from '@playwright/test';

/**
 * Seed an authenticated session into localStorage so ProtectedRoute renders the
 * target page instead of redirecting to /login. Must be called BEFORE the first
 * `page.goto()` of a test (uses Playwright's addInitScript).
 *
 * Storage keys mirror `frontend/src/services/token-store.ts` and
 * `frontend/src/services/auth-store.tsx`.
 */
export async function seedAuth(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem('vf_access_token', 'token-test');
    window.localStorage.setItem('vf_refresh_token', 'refresh-test');
    window.localStorage.setItem(
      'vf_user',
      JSON.stringify({ id: 'u-test', email: 'demo@example.com', name: 'Demo User' })
    );
  });
}
