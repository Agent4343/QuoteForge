import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API and web are served from one origin in production (§6). In dev we proxy
// /api to the FastAPI server so the SPA can use same-origin relative URLs.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
