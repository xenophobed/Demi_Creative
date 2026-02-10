/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#FF6B6B',
          light: '#FF8E8E',
          dark: '#E55A5A',
        },
        secondary: {
          DEFAULT: '#4ECDC4',
          light: '#6ED8D0',
          dark: '#3DBAB2',
        },
        accent: {
          DEFAULT: '#FFE66D',
          light: '#FFEC8A',
          dark: '#E6CF5A',
        },
        warm: {
          DEFAULT: '#FFF9F5',
          50: '#FFFDFB',
          100: '#FFF9F5',
          200: '#FFF0E6',
        },
        kid: {
          purple: '#A78BFA',
          blue: '#60A5FA',
          green: '#34D399',
          orange: '#FB923C',
          pink: '#F472B6',
        },
      },
      fontFamily: {
        rounded: ['Nunito', 'Quicksand', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'btn': '20px',
        'card': '16px',
        'input': '12px',
      },
      boxShadow: {
        'kid': '0 4px 14px 0 rgba(255, 107, 107, 0.25)',
        'card': '0 8px 30px rgba(0, 0, 0, 0.08)',
        'button': '0 4px 15px rgba(255, 107, 107, 0.4)',
      },
      animation: {
        'bounce-slow': 'bounce 2s infinite',
        'wiggle': 'wiggle 1s ease-in-out infinite',
        'float': 'float 3s ease-in-out infinite',
        'sparkle': 'sparkle 1.5s ease-in-out infinite',
      },
      keyframes: {
        wiggle: {
          '0%, 100%': { transform: 'rotate(-3deg)' },
          '50%': { transform: 'rotate(3deg)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        sparkle: {
          '0%, 100%': { opacity: 1, transform: 'scale(1)' },
          '50%': { opacity: 0.5, transform: 'scale(0.8)' },
        },
      },
    },
  },
  plugins: [],
}
