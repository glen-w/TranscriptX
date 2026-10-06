import process from "node:process";
import { defineConfig, type UserConfig } from "vite";

export default defineConfig(() => {
  const isProd = process.env.NODE_ENV === "production";
  const isDev = !isProd;

  return {
    base: "./",
    define: {
      "process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV),
    },
    build: {
      minify: isDev ? false : "esbuild",
      outDir: "build",
      emptyOutDir: true,
      sourcemap: isDev,
      lib: {
        entry: {
          speaker_id: "./src/speaker_id.ts",
          corrections: "./src/corrections.ts",
          viewer_edit: "./src/viewer_edit.ts",
        },
        formats: ["es"],
        fileName: "[name]-[hash]",
      },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.ts"],
    },
  } satisfies UserConfig;
});
