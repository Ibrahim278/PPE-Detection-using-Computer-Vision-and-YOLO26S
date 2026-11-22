import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API runs on :8000; proxy it so the app uses same-origin URLs
// (no CORS, and the WebSocket goes through the same proxy).
const API = process.env.VITE_DEV_API ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API, changeOrigin: true, ws: true },
      "/media": { target: API, changeOrigin: true },
    },
  },
});
