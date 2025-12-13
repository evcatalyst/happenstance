const { test, expect } = require("@playwright/test");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const ARTIFACT_DIR = path.join(__dirname, "..", "..", "artifacts", "journeys");
const PORT = process.env.PORT || "8000";
const PYTHON = process.env.PYTHON || "python3";
let server;

test.describe.configure({ mode: "serial" });

async function waitForServer(port, attempts = 10) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const response = await fetch(`http://localhost:${port}`);
      if (response.ok) {
        return;
      }
    } catch (err) {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error(`Server did not start on port ${port}`);
}

test.beforeAll(async () => {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  const reportSrc = path.join(__dirname, "..", "..", "docs", "journeys", "README.md");
  if (fs.existsSync(reportSrc)) {
    fs.copyFileSync(reportSrc, path.join(ARTIFACT_DIR, "README.md"));
  }
  const docsDir = path.join(__dirname, "..", "..", "docs");
  try {
    server = spawn(PYTHON, ["-m", "http.server", PORT, "--directory", docsDir], {
      stdio: "inherit",
    });
    await waitForServer(PORT);
  } catch (err) {
    if (server && !server.killed) {
      server.kill();
    }
    throw err;
  }
});

test.afterAll(() => {
  if (server && !server.killed) {
    server.kill();
  }
});

test("journeys with screenshots", async ({ page }) => {
  await page.goto(`http://localhost:${PORT}`);
  await page.waitForSelector('[data-hs-ready="1"]');

  const restaurantsCards = page.locator("#restaurants-view .card");
  await expect(restaurantsCards).not.toHaveCount(0);
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "01-home.png") });

  await page.getByRole("button", { name: "Events" }).click();
  await expect(page.locator("#events-view")).toBeVisible();
  const eventsCards = page.locator("#events-view .card");
  await expect(eventsCards).not.toHaveCount(0);
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "02-events.png") });

  const beforeCount = await eventsCards.count();
  await page.fill("#filter-input", "music");
  await page.waitForFunction(
    (expected) => document.querySelectorAll("#events-view .card").length <= expected,
    beforeCount
  );
  const afterCount = await eventsCards.count();
  expect(afterCount).toBeLessThanOrEqual(beforeCount);
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "03-filtered-events.png") });
  await expect(page).toHaveURL(/filter=music/);

  await page.getByRole("button", { name: "Paired" }).click();
  await expect(page.locator("#paired-view")).toBeVisible();
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "04-paired.png") });

  await page.getByRole("button", { name: "Restaurants" }).click();
  await page.fill("#filter-input", "Sushi");
  await page.waitForFunction(
    () => document.querySelectorAll("#restaurants-view .card, #restaurants-view tbody tr").length > 0
  );
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "05-restaurants-filter.png") });
  await page.selectOption("#layout-select", "table");
  await expect(page.locator("table")).toBeVisible();
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "06-layout-table.png") });
});
