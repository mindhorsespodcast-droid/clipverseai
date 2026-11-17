// Starts the video worker (used by "npm run dev"). Pass "check" to only check settings.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { venvPython, workerDir } from "./worker-python.mjs";

if (!existsSync(venvPython)) {
  console.log(
    "\n[worker] The video worker isn't installed yet, so uploads won't be processed.\n" +
      "[worker] Run this once:  npm run setup:worker   (the website still works without it)\n",
  );
  process.exit(0);
}

const child = spawn(venvPython, ["-u", "-m", "clipverse_worker", ...process.argv.slice(2)], {
  cwd: workerDir,
  stdio: "inherit",
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
});
child.on("exit", (code) => process.exit(code ?? 0));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
