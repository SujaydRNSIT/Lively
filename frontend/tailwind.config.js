/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#090b10',
        surface: '#111522',
        'surface-border': '#1e2638',
        'surface-hover': '#182033',
        brand: {
          50: '#f4f4f5',
          100: '#e4e4e7',
          400: '#71717a',
          500: '#27272a',
          600: '#18181b',
          700: '#09090b',
        },
        agora: {
          blue: '#099dfd',
          dark: '#03538c'
        }
      },
      fontFamily: {
        sans: ['Outfit', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace']
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'wave': 'wave 1.2s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        wave: {
          '0%, 100%': { transform: 'scaleY(0.4)' },
          '50%': { transform: 'scaleY(1.0)' },
        },
        glow: {
          '0%': { boxShadow: '0 0 15px rgba(24, 24, 27, 0.3)' },
          '100%': { boxShadow: '0 0 30px rgba(24, 24, 27, 0.7)' },
        }
      }
    },
  },
  plugins: [],
}
