import type { Config } from 'tailwindcss'
import flowbite from 'flowbite/plugin'

export default {
  content: [
    './index.html',
    './src/**/*.{vue,ts,tsx}',
    './node_modules/flowbite/**/*.{js,ts}',
    './node_modules/flowbite-vue/**/*.{js,ts}'
  ],
  theme: {
    extend: {
      colors: {
        gold: {
          50:  '#FFFAE5',
          100: '#FFF3CC',
          200: '#FFE699',
          300: '#FFD966',
          400: '#FFCC33',
          500: '#FFD700',
          600: '#E6C200',
          700: '#B39700',
          800: '#806B00',
          900: '#4D4000',
        },
      },

    }
  },
  plugins: [flowbite],
} satisfies Config
