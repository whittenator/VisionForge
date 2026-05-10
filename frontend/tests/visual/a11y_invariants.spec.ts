import { test, expect } from '@playwright/test';
import { seedAuth } from './_helpers';

const ROUTES_WITH_SHELL = [
  '/',
  '/projects',
  '/datasets',
  '/experiments',
  '/artifacts',
  '/admin/users',
];

test.describe('Accessibility invariants — protected routes', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
    // Stub all API calls so empty-state pages render deterministically.
    await page.route('**/api/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
  });

  for (const path of ROUTES_WITH_SHELL) {
    test(`${path}: exactly one <h1>`, async ({ page }) => {
      await page.goto(path, { waitUntil: 'domcontentloaded' });
      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.locator('h1')).toHaveCount(1);
    });
  }

  test('skip-to-content link becomes visible on focus and targets #main', async ({ page }) => {
    await page.goto('/projects', { waitUntil: 'domcontentloaded' });
    await expect(page).not.toHaveURL(/\/login/);

    const skip = page.getByRole('link', { name: /skip to content/i });

    // Off-screen until focused
    await expect(skip).toHaveClass(/sr-only/);
    await page.keyboard.press('Tab');
    await expect(skip).toBeFocused();

    await expect(skip).toHaveAttribute('href', '#main');
    await expect(page.locator('#main')).toBeVisible();
  });

  test('logout button has an accessible name', async ({ page }) => {
    await page.goto('/projects', { waitUntil: 'domcontentloaded' });
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole('button', { name: /logout/i })).toBeVisible();
  });
});

test.describe('Accessibility invariants — public routes', () => {
  test('login form: every input has an associated label', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'domcontentloaded' });

    for (const id of ['email', 'password']) {
      const input = page.locator(`#${id}`);
      await expect(input).toBeVisible();
      const label = page.locator(`label[for="${id}"]`);
      await expect(label).toBeVisible();
    }

    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });
});
