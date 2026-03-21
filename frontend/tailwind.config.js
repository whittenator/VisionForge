/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      container: { center: true, padding: '1rem' },
      borderRadius: {
        DEFAULT: '0.1875rem',
        sm: '0.125rem',
        md: '0.25rem',
        lg: '0.25rem',
        xl: '0.375rem',
      },
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
};
