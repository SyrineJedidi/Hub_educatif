import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Libraries change rarely: a separate file stays in the browser cache between releases.
        manualChunks(id) {
          if (/node_modules[\/](react-router|react-router-dom)[\/]/.test(id)) return "router";
          if (/node_modules[\/](react|react-dom|scheduler)[\/]/.test(id)) return "react";
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target:
          loadEnv(mode, ".", "VITE_").VITE_API_TARGET ||
          "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
}));
