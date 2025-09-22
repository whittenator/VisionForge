import { test, expect, type Page } from '@playwright/test';

const BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';

// Helper to login via UI once implemented
async function doLogin(page: Page) {
  await page.goto(`${BASE}/login`);
  await page.getByLabel('Email').fill('demo@example.com');
  await page.getByLabel('Password').fill('password123');
  await page.getByRole('button', { name: 'Sign in' }).click();
}

test.describe('Auth flow', () => {
  test('unauthenticated user is redirected to /login when visiting /', async ({ page }) => {
    await page.goto(`${BASE}/`);
    await page.waitForURL('**/login');
    await expect(page.getByRole('heading', { name: /Login/i })).toBeVisible();
  });

  test('valid login redirects to homepage', async ({ page }) => {
    await doLogin(page);
    await page.waitForURL(`${BASE}/`);
    await expect(page.locator('h1')).toContainText(/Build vision products faster/i);
  });

  test('logout returns to login', async ({ page }) => {
    await doLogin(page);
    await page.getByRole('button', { name: 'Logout' }).click();
    await page.waitForURL('**/login');
  });
});
