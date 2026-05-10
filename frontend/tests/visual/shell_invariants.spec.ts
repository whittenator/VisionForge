import { test, expect } from '@playwright/test';

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
  for (const path of ROUTES) {
    test(`${path}: single global header + landmarks + skip link`, async ({ page }) => {
      await page.goto(path, { waitUntil: 'domcontentloaded' });

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
  test('projects empty state surfaces primary CTA', async ({ page }) => {
    await page.route('**/api/projects', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.goto('/projects', { waitUntil: 'domcontentloaded' });
    const empty = page.getByRole('status').filter({ hasText: /no projects/i });
    await expect(empty).toBeVisible();
    await expect(empty.getByRole('link', { name: /new project/i })).toBeVisible();
  });

  test('experiments empty state surfaces primary CTA', async ({ page }) => {
    await page.route('**/api/experiments/runs', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.goto('/experiments', { waitUntil: 'domcontentloaded' });
    const empty = page.getByRole('status').filter({ hasText: /no training runs/i });
    await expect(empty).toBeVisible();
    await expect(empty.getByRole('link', { name: /training run/i })).toBeVisible();
  });

  test('datasets empty state surfaces primary CTA', async ({ page }) => {
    await page.route('**/api/datasets**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.goto('/datasets', { waitUntil: 'domcontentloaded' });
    const empty = page.getByRole('status').filter({ hasText: /no datasets/i });
    await expect(empty).toBeVisible();
    await expect(empty.getByRole('link', { name: /upload dataset/i })).toBeVisible();
  });
});

test.describe('URL-persisted filters', () => {
  test('datasets project filter survives reload', async ({ page }) => {
    await page.route('**/api/datasets**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );

    await page.goto('/datasets?projectId=p-fixture', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText(/\(filtered\)/i)).toBeVisible();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/projectId=p-fixture/);
    await expect(page.getByText(/\(filtered\)/i)).toBeVisible();
  });
});
