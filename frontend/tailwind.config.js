/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#172554', indigo: '#4F46E5', lavender: '#A5B4FC', canvas: '#F5F3FF',
        muted: '#64748B', income: '#16A34A', expense: '#E57373', line: '#E8EAF2',
      },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
      boxShadow: { card: '0 8px 28px rgba(23,37,84,0.055)', float: '0 20px 70px rgba(23,37,84,0.17)' },
      borderRadius: { '2xl': '1.25rem', '3xl': '1.65rem' },
    },
  },
  plugins: [],
}
