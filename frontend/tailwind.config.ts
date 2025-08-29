import type { Config } from 'tailwindcss'
import flowbite from 'flowbite/plugin'

export default {
  content: [
    './index.html',
    './src/**/*.{vue,ts,tsx}',
    './node_modules/flowbite/**/*.{js,ts}',
    './node_modules/flowbite-vue/**/*.{js,ts}'
  ],
  theme: { extend: {} },
  plugins: [flowbite],
} satisfies Config
