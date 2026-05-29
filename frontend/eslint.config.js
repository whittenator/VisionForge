// ESLint v9 flat config
import js from "@eslint/js";
import react from "eslint-plugin-react";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx,ts,tsx}", "vite.config.ts"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      // A flat config needs real global names (console, setInterval,
      // structuredClone, Image, ...), not env flags like `browser: true`
      // (which would just declare a single global literally named "browser").
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: { react },
    rules: {
      ...react.configs.recommended.rules,
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
    },
    settings: { react: { version: "detect" } },
  },
];