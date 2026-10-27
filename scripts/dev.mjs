import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = path.join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
if (!existsSync(python)) {
  console.error("Install Python dependencies first: uv sync --group dev");
  process.exit(1);
}
const children = [];
const api = spawn(
  python,
  [
    "-m",
    "uvicorn",
    "backend.app.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8000",
  ],
  { cwd: root, stdio: "inherit" },
);
children.push(api);
const next = path.join(root, "node_modules/next/dist/bin/next");
const web = spawn(
  process.execPath,
  [next, "dev", "--hostname", "127.0.0.1", "--port", "3000"],
  {
    cwd: path.join(root, "frontend"),
    stdio: "inherit",
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
  },
);
children.push(web);
let closing = false;
function stop(code = 0) {
  if (closing) return;
  closing = true;
  for (const child of children) {
    if (child.exitCode === null) {
      if (process.platform === "win32")
        spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
          windowsHide: true,
        });
      else child.kill("SIGTERM");
    }
  }
  setTimeout(() => process.exit(code), 600);
}
for (const child of children) {
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!closing) stop(code || 0);
  });
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
console.log(
  "\nPrompt Caller → http://127.0.0.1:3000\nAPI → http://127.0.0.1:8000/docs\n",
);
