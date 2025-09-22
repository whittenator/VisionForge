import { test, expect } from '@playwright/test';

const BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';

test('login page visual check', async ({ page }) => {
  await page.goto(`${BASE}/login`);
  await page.setViewportSize({ width: 1440, height: 900 });
  const consoleMessages: string[] = [];
  page.on('console', (msg) => consoleMessages.push(msg.text()));
  await expect(page).toHaveScreenshot('login-desktop.png', { fullPage: true });
  expect(consoleMessages.join('\n')).not.toMatch(/error|warning/i);
});

test('homepage visual check (post-login)', async ({ page }) => {
  await page.goto(`${BASE}/login`);
  await page.getByLabel('Email').fill('demo@example.com');
  await page.getByLabel('Password').fill('password123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL(`${BASE}/`);
  await page.setViewportSize({ width: 1440, height: 900 });
  const consoleMessages: string[] = [];
  page.on('console', (msg) => consoleMessages.push(msg.text()));
  await expect(page).toHaveScreenshot('home-desktop.png', { fullPage: true });
  expect(consoleMessages.join('\n')).not.toMatch(/error|warning/i);
});
