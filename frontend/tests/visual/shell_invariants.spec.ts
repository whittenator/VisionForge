import { test, expect } from '@playwright/test';
import { seedAuth } from './_helpers';

const ROUTES = [
  '/',
  '/projects',
  '/projects/create',
  '/datasets',
  '/datasets/upload',
  '/experiments',
  '/artifacts',
  '/admin/users',
];

test.describe('AppShell structural invariants', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
  });

  for (const path of ROUTES) {
    test(`${path}: single global header + landmarks + skip link`, async ({ page }) => {
      await page.goto(path, { waitUntil: 'domcontentloaded' });

      // Sanity: ProtectedRoute did not bounce us to /login.
      await expect(page).not.toHaveURL(/\/login/);

      const banners = page.getByRole('banner');
      await expect(banners).toHaveCount(1);

      const mains = page.getByRole('main');
      await expect(mains).toHaveCount(1);

      const skipLink = page.getByRole('link', { name: /skip to content/i });
      await expect(skipLink).toHaveCount(1);

      const navs = page.getByRole('navigation', { name: /main navigation/i });
      await expect(navs).toHaveCount(1);
    });
  }
});

test.describe('Empty-state CTAs', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
  });

  test('projects empty state surfaces primary CTA', async ({ page }) => {
    await page.route('**/api/projects', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.goto('/projects', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/projects$/);
    const empty = page.getByRole('status').filter({ hasText: /no projects/i });
    await expect(empty).toBeVisible();
    await expect(empty.getByRole('link', { name: /new project/i })).toBeVisible();
  });

  test('experiments empty state surfaces primary CTA', async ({ page }) => {
    await page.route('**/api/experiments/runs', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.goto('/experiments', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/experiments$/);
    const empty = page.getByRole('status').filter({ hasText: /no training runs/i });
    await expect(empty).toBeVisible();
    await expect(empty.getByRole('link', { name: /training run/i })).toBeVisible();
  });

  test('datasets empty state surfaces primary CTA', async ({ page }) => {
    await page.route('**/api/datasets**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.goto('/datasets', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/datasets$/);
    const empty = page.getByRole('status').filter({ hasText: /no datasets/i });
    await expect(empty).toBeVisible();
    await expect(empty.getByRole('link', { name: /upload dataset/i })).toBeVisible();
  });
});

test.describe('URL-persisted filters', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
  });

  test('datasets project filter survives reload', async ({ page }) => {
    await page.route('**/api/datasets**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );

    await page.goto('/datasets?projectId=p-fixture', { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/datasets\?projectId=p-fixture/);
    await expect(page.getByText(/\(filtered\)/i)).toBeVisible();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/projectId=p-fixture/);
    await expect(page.getByText(/\(filtered\)/i)).toBeVisible();
  });
});
