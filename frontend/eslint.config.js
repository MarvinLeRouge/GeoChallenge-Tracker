// For more info, see https://github.com/storybookjs/eslint-plugin-storybook#configuration-flat-config-format
import storybook from "eslint-plugin-storybook";

// eslint.config.js (ESM, flat config)
import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import vue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import globals from 'globals'

export default [// Ignorer les artefacts
{ ignores: ['dist', 'coverage', 'node_modules', '.vite', '.output'] }, // Bases JS
js.configs.recommended, // TypeScript (règles de base sans projet TS config)
...tseslint.configs.recommended, // Vue 3 (flat config)
...vue.configs['flat/recommended'], {
  files: [
    '**/*.config.{js,cjs,mjs,ts}',
    'vite.config.*',
    'postcss.config.*',
    'eslint.config.*'
  ],
  languageOptions: {
    globals: { ...globals.node }
  }
}, // Forcer le mode CommonJS pour les .cjs
{
  files: ['**/*.cjs'],
  languageOptions: {
    sourceType: 'commonjs'
  }
}, // Réglages communs + règles projet
{
  files: ['**/*.{ts,tsx,vue}'],
  languageOptions: {
    // Parser des SFC .vue
    parser: vueParser,
    parserOptions: {
      parser: tseslint.parser, // pour les blocs <script lang="ts">
      ecmaVersion: 'latest',
      sourceType: 'module',
      extraFileExtensions: ['.vue']
    }
  },
  rules: {
    // Ajuste selon ton projet :
    'vue/multi-word-component-names': 'off'
  }
}, ...storybook.configs["flat/recommended"]];
