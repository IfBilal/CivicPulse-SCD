import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "public/mockServiceWorker.js", "src/api/schema.d.ts"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx,js}"],
    languageOptions: { ecmaVersion: 2022, globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // HARD rule 9: the frontend owns no business rules. Mirrors the grep in `make lint`.
      "no-restricted-syntax": [
        "error",
        {
          selector: "Identifier[name=/^(TRANSITIONS|allowedNext|ALLOWED_TRANSITIONS)$/]",
          message: "Transition rules live on the server (CLAUDE.md HARD rule 9).",
        },
      ],
    },
  },
  {
    files: ["tests/**", "mocks/**"],
    rules: { "react-refresh/only-export-components": "off", "no-restricted-syntax": "off" },
  },
);
