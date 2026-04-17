// eslint.config.js (ESM, flat config)
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import vue from "eslint-plugin-vue";
import vueParser from "vue-eslint-parser";
import globals from "globals";
import prettierConfig from "eslint-config-prettier";

export default [
  // Ignorer les artefacts
  { ignores: ["frontend/dist", "frontend/coverage", "node_modules", ".vite", ".output", "frontend/src/**/*.js", "vite.config.js"] },

  // Bases JS
  js.configs.recommended,

  // TypeScript (règles de base sans projet TS config)
  ...tseslint.configs.recommended,

  // Vue 3 (flat config)
  ...vue.configs["flat/recommended"],

  {
    files: [
      "**/*.config.{js,cjs,mjs,ts}",
      "vite.config.*",
      "postcss.config.*",
      "eslint.config.*",
    ],
    languageOptions: {
      globals: { ...globals.node },
    },
  },

  // Forcer le mode CommonJS pour les .cjs
  {
    files: ["**/*.cjs"],
    languageOptions: {
      sourceType: "commonjs",
    },
  },

  // Réglages communs + règles projet
  {
    files: ["frontend/**/*.{ts,tsx,vue}"],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: "latest",
        sourceType: "module",
        extraFileExtensions: [".vue"],
      },
    },
    rules: {
      "vue/multi-word-component-names": "off",
    },
  },

  // Disable ESLint formatting rules that conflict with prettier — must be last
  prettierConfig,
];
