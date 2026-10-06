import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const build = path.join(root, "build");
fs.mkdirSync(build, { recursive: true });
const src = path.join(root, "src", "styles.css");
for (const name of ["speaker_id-styles.css", "corrections-styles.css", "viewer_edit-styles.css"]) {
  fs.copyFileSync(src, path.join(build, name));
  console.log(`copied styles.css → build/${name}`);
}
