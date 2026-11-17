// Shared helper: where the worker's private Python lives (Windows vs Mac/Linux).
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const workerDir = path.join(root, "worker");
export const venvDir = path.join(workerDir, ".venv");
export const venvPython =
  process.platform === "win32" ? path.join(venvDir, "Scripts", "python.exe") : path.join(venvDir, "bin", "python");
