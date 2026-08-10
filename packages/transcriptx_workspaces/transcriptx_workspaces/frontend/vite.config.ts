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
      emptyOutDir: false,
      sourcemap: isDev,
      lib: {
        entry: "./src/index.ts",
        name: "SpeakerIdWorkspace",
        formats: ["es"],
        fileName: "index-[hash]",
      },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.ts"],
    },
  } satisfies UserConfig;
});
