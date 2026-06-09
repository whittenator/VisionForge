import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';

// Keep tests isolated: localStorage carries auth state between cases.
afterEach(() => {
  localStorage.clear();
});
