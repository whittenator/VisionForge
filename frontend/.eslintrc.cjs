module.exports = {
  root: true,
  env: { browser: true, es2023: true, node: true },
  extends: ["eslint:recommended", "plugin:react/recommended"],
  settings: { react: { version: "detect" } },
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["react"],
  rules: { "react/react-in-jsx-scope": "off" },
};
