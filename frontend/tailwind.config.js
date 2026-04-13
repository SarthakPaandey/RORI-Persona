/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        neon: {
          green: '#00ff41',
          cyan: '#00d9ff',
          purple: '#ff00ff',
          pink: '#ff0080',
          blue: '#0099ff',
        },
      },
      animation: {
        'bounce-dot': 'bounce 1.4s infinite ease-in-out',
        'pulse-glow': 'pulseGlow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-border': 'glowBorder 3s linear infinite',
        'float': 'float 3s ease-in-out infinite',
        'flicker': 'flicker 0.15s infinite',
        'scan': 'scan 8s linear infinite',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { 
            opacity: '1',
            textShadow: '0 0 5px rgb(0, 255, 65), 0 0 10px rgba(0, 255, 65, 0.5)'
          },
          '50%': { 
            opacity: '0.8',
            textShadow: '0 0 2px rgb(0, 255, 65), 0 0 5px rgba(0, 255, 65, 0.3)'
          },
        },
        glowBorder: {
          '0%': { boxShadow: '0 0 5px rgba(0, 255, 65, 0.5), 0 0 10px rgba(0, 217, 255, 0.3)' },
          '50%': { boxShadow: '0 0 15px rgba(0, 255, 65, 0.8), 0 0 25px rgba(0, 217, 255, 0.5)' },
          '100%': { boxShadow: '0 0 5px rgba(0, 255, 65, 0.5), 0 0 10px rgba(0, 217, 255, 0.3)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        flicker: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
        scan: {
          '0%': { transform: 'translateY(0)' },
          '100%': { transform: 'translateY(10px)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
};
