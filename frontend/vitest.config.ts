import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// Vitest config kept separate from vite.config.ts so the production build never
// depends on test-only settings. Only the tests/unit/*.test.* files run here;
// the Playwright *.spec.ts suites are owned by playwright.config.ts.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/unit/setup.ts'],
    include: ['tests/unit/**/*.{test,spec}.{ts,tsx}'],
  },
});
