import { defineConfig, devices, webkit } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname } from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const localLibs = `${root}.runtime/webkit-libs/usr/lib/x86_64-linux-gnu`;
if (existsSync(localLibs)) {
  process.env.LD_LIBRARY_PATH = `${localLibs}:${process.env.LD_LIBRARY_PATH || ""}`;
  // Playwright checks /sbin/ldconfig's SYSTEM cache for x264, which cannot see
  // our unprivileged libraries. Verify the real loader before bypassing only
  // that environment check; all browser/business assertions still run.
  execFileSync("python3", [
    "-c",
    "import ctypes; [ctypes.CDLL(x) for x in ['libevent-2.1.so.7','libflite.so.1','libavif.so.16','libmanette-0.2.so.0','libx264.so.165']]",
  ]);
  process.env.PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "1";
}
// Browser test traffic is loopback only; never route it through desktop proxies.
const testEnv = {
  ...process.env,
  http_proxy: "",
  https_proxy: "",
  all_proxy: "",
  HTTP_PROXY: "",
  HTTPS_PROXY: "",
  ALL_PROXY: "",
  no_proxy: "127.0.0.1,localhost",
  NO_PROXY: "127.0.0.1,localhost",
};
const localWebkit = existsSync(localLibs)
  ? {
      executablePath: `${root}scripts/webkit-local.sh`,
      env: {
        ...testEnv,
        YANTU_WEBKIT_BUNDLE: dirname(webkit.executablePath()),
      } as Record<string, string>,
    }
  : {};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:18000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1050 },
      },
    },
    {
      name: "mobile-webkit",
      use: { ...devices["iPhone 13"], launchOptions: localWebkit },
    },
  ],
  webServer: {
    command: `"${root}.venv/bin/python" "${root}scripts/e2e_server.py"`,
    url: "http://127.0.0.1:18000/api/health",
    reuseExistingServer: false,
    timeout: 20000,
  },
});
