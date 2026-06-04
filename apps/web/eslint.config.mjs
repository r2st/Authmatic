// Flat ESLint config (ticket 0032). `pnpm --filter authmatic-web lint`.
//
// Policy: `recommended` (correctness) as the error baseline, plus Next's
// recommended + core-web-vitals rules. The aggressive TYPE-AWARE rules
// (recommendedTypeChecked) flag ~50 pre-existing patterns — mostly the
// InsForge SDK's `any`-typed returns — and would block every build. Rather
// than gate the build on that debt, we keep the *highest-value* type-aware
// rules on as WARNINGS (visible, non-blocking): the floating-/misused-promise
// pair that catches the fire-and-forget bug class (ticket 0027 fixes the real
// sites). Promote these to "error" once the promise debt is paid.
import nextPlugin from "@next/eslint-plugin-next";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: [".next/**", "node_modules/**", "scripts/**", "next-env.d.ts", "*.config.*"] },
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: { "@next/next": nextPlugin },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      // Honor the `_`-prefix convention for intentionally-unused args/vars.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
      // High-value, type-aware — kept on as warnings (see header note).
      "@typescript-eslint/no-floating-promises": "warn",
      "@typescript-eslint/no-misused-promises": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
    },
  }
);
