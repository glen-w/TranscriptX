import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const build = path.join(root, "build");
fs.mkdirSync(build, { recursive: true });
fs.copyFileSync(
  path.join(root, "src", "styles.css"),
  path.join(build, "index-styles.css"),
);
console.log("copied styles.css → build/index-styles.css");
