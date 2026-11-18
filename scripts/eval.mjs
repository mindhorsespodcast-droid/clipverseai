// Speech-to-text test (Phase 2A):
//   npm run eval:setup   one-time: installs the extra test packages (large download)
//   npm run eval:draft   makes a draft answer key (.txt) for each sample - you then correct it
//   npm run eval         runs every option and writes eval/report.html
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { root, venvPython, workerDir } from "./worker-python.mjs";

const cmd = process.argv[2] ?? "run";
if (!existsSync(venvPython)) {
  console.log("\nThe video worker isn't installed yet. Run:  npm run setup:worker\n");
  process.exit(1);
}

if (cmd === "setup") {
  console.log("\nInstalling the extra test packages (1-2 GB, can take 5-15 minutes)...\n");
  const r = spawnSync(
    venvPython,
    ["-m", "pip", "install", "--disable-pip-version-check", "-r", path.join(workerDir, "requirements-eval.txt")],
    { stdio: "inherit" },
  );
  if (r.status !== 0) {
    console.log("\n  FIX   Installing failed. Check your internet connection and run this again.\n");
    process.exit(1);
  }
  const check = spawnSync(venvPython, ["-c", "import torch, transformers; print(torch.__version__)"], { encoding: "utf8" });
  if (check.status !== 0) {
    const blocked = /Application Control|blocked/i.test(check.stderr);
    console.log(
      blocked
        ? "\n  FIX   Windows Smart App Control blocked the AI toolkit (PyTorch). The test still works for the\n" +
            "        Groq options; the two laptop models will be skipped. Tell Claude and we'll decide what to do.\n"
        : `\n  FIX   The AI toolkit didn't load:\n${check.stderr.split("\n").slice(-4).join("\n")}\n`,
    );
    process.exit(1);
  }
  console.log("\n  OK    Test packages installed. Next: npm run eval:draft\n");
  process.exit(0);
}

const r = spawnSync(venvPython, ["-u", "-m", "clipverse_worker.evaluation", cmd === "draft" ? "draft" : "run", ...process.argv.slice(3)], {
  cwd: workerDir,
  stdio: "inherit",
  env: { ...process.env, PYTHONIOENCODING: "utf-8", HF_HUB_DISABLE_SYMLINKS_WARNING: "1" },
});
if (cmd !== "draft" && r.status === 0) {
  const report = path.join(root, "eval", "report.html");
  if (existsSync(report)) console.log(`Open this file in your browser: ${report}`);
}
process.exit(r.status ?? 0);
