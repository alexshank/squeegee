import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// the build output is what the Python package ships; nothing else reads this directory
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/squeegee/ui/static",
    emptyOutDir: true,
  },
  server: {
    // `npm run dev` talks to a `squeegee ui` running on its default port
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/testSetup.ts"],
  },
});
