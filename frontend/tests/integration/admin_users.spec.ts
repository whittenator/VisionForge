import { test, expect } from '@playwright/test';

// T022 Playwright: admin creates users/roles

test('admin can create users and assign roles', async ({ page }) => {
  await page.goto('/admin/users');

  await page.getByLabel('Email').fill('alice@example.com');
  await page.getByLabel('Role').selectOption('admin');
  await page.getByRole('button', { name: 'Create user' }).click();

  const row = page.getByTestId('user-row');
  await expect(row).toContainText('alice@example.com');
  await expect(row).toContainText('admin');
});
