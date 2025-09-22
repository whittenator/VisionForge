import { test, expect } from '@playwright/test';

// T021 Playwright: annotator keyboard-first interactions
// - Focus container and press keys to toggle modes/tags and save
// - Assert state changes via testids and aria-live region

test('annotator supports keyboard-first interactions', async ({ page }) => {
  await page.goto('/annotate/42');

  const container = page.getByTestId('annotator-container');
  await container.click(); // focus

  // Toggle box mode with 'b'
  await page.keyboard.press('b');
  await expect(page.getByTestId('mode')).toHaveText('box');

  // Toggle classification tag with 'c'
  await page.keyboard.press('c');
  await expect(page.getByTestId('tag-cat')).toHaveText('on');

  // Save with Enter
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('status')).toHaveText('Saved');

  // Navigate with ArrowRight
  await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId('status')).toHaveText('Navigated next');
});
