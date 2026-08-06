import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

// eslint-config-next 15.3.6 ships eslintrc-format configs only, so they are
// translated through FlatCompat. Drop the wrapper once it exports eslint.config
// entries directly (Next 15.5+).
const config = [
  {
    ignores: [
      ".next/**",
      "artifacts/**",
      "playwright-report/**",
      "tmp/**",
      "next-env.d.ts",
    ],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    // Playwright specs run in Node, not the browser, and are not part of the
    // Next build, so the framework rules that assume a page do not apply.
    files: ["e2e/**/*.ts", "playwright*.ts"],
    rules: {
      "@next/next/no-html-link-for-pages": "off",
    },
  },
];

export default config;
