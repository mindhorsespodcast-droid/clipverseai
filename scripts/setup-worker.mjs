// One-time setup for the video worker:  npm run setup:worker
// Finds Python 3.12+, makes a private Python folder (worker/.venv), installs the worker's packages.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { venvDir, venvPython, workerDir } from "./worker-python.mjs";

const say = (m) => console.log(m);
const fail = (m) => {
  console.log(`\n  FIX   ${m}\n`);
  process.exit(1);
};

say("\nSetting up the ClipVerse AI video worker...\n");

// 1. FFmpeg
const ff = spawnSync("ffmpeg", ["-version"], { encoding: "utf8" });
if (ff.status !== 0) {
  fail(
    "FFmpeg isn't installed (or not found).\n" +
      "        Windows: run  winget install Gyan.FFmpeg  then CLOSE and REOPEN PowerShell.\n" +
      "        Mac:     run  brew install ffmpeg",
  );
}
say("  OK    FFmpeg is installed");

// 2. Python 3.12+
const candidates =
  process.platform === "win32"
    ? [["py", ["-3.12"]], ["py", ["-3.13"]], ["py", ["-3.14"]], ["py", ["-3"]], ["python", []]]
    : [["python3.12", []], ["python3.13", []], ["python3.14", []], ["python3", []], ["python", []]];
let python = null;
for (const [cmd, args] of candidates) {
  const r = spawnSync(cmd, [...args, "-c", "import sys; print(sys.version_info[:2] >= (3, 12))"], { encoding: "utf8" });
  if (r.status === 0 && r.stdout.trim() === "True") {
    python = [cmd, args];
    break;
  }
}
if (!python) {
  fail(
    "Python 3.12 or newer isn't installed.\n" +
      "        Windows: run  winget install Python.Python.3.12  then CLOSE and REOPEN PowerShell.\n" +
      "        Mac:     run  brew install python@3.12",
  );
}
say(`  OK    Found Python (${[python[0], ...python[1]].join(" ")})`);

// 3. Private Python folder + packages
if (!existsSync(venvPython)) {
  say("  ...   Creating the worker's private Python folder (worker/.venv)");
  const r = spawnSync(python[0], [...python[1], "-m", "venv", venvDir], { stdio: "inherit" });
  if (r.status !== 0) fail("Couldn't create worker/.venv. Try deleting the worker/.venv folder and run this again.");
}
say("  ...   Installing worker packages (first time takes a minute or two)");
const pip = spawnSync(
  venvPython,
  ["-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", path.join(workerDir, "requirements.txt")],
  { stdio: "inherit" },
);
if (pip.status !== 0) fail("Installing packages failed. Check your internet connection and run this again.");
say("  OK    Worker packages installed");
say("\nDone! Next: add your Groq and Gemini keys to .env, then run:  npm run check-worker\n");
