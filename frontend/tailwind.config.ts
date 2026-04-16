export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        sm: '0 2px 8px -1px rgba(26, 38, 52, 0.04), 0 1px 2px -1px rgba(26, 38, 52, 0.02)',
        md: '0 8px 24px -4px rgba(26, 38, 52, 0.04), 0 4px 10px -2px rgba(26, 38, 52, 0.02)',
        lg: '0 12px 32px -4px rgba(26, 38, 52, 0.05), 0 6px 14px -2px rgba(26, 38, 52, 0.03)',
      },
    },
  },
}
