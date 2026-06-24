import type { Config } from 'tailwindcss'
const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        scam: { 50: '#fef2f2', 500: '#ef4444', 700: '#b91c1c' },
        safe: { 50: '#f0fdf4', 500: '#22c55e', 700: '#15803d' },
        suspicious: { 50: '#fffbeb', 500: '#f59e0b', 700: '#b45309' },
      },
    },
  },
  plugins: [],
}
export default config
