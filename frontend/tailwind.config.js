/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef6ff",
          100: "#d9eaff",
          400: "#3b9dff",
          500: "#1a7fe6",
          600: "#0f63b8",
          700: "#0d4f92",
        },
      },
    },
  },
  plugins: [],
};
