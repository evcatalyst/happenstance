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
  // Journey 1: Initial Load and Restaurant View
  await page.goto(`http://localhost:${PORT}`);
  await page.waitForSelector('[data-hs-ready="1"]');

  const restaurantsCards = page.locator("#restaurants-view .card");
  await expect(restaurantsCards).not.toHaveCount(0);
  
  // Verify badges are present
  await expect(page.locator(".badge-cuisine").first()).toBeVisible();
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "01-home.png"), fullPage: false });

  // Journey 2: Events Tab
  await page.getByRole("button", { name: "Events" }).click();
  await expect(page.locator("#events-view")).toBeVisible();
  const eventsCards = page.locator("#events-view .card");
  await expect(eventsCards).not.toHaveCount(0);
  
  // Verify event category badges
  await expect(page.locator(".badge-category").first()).toBeVisible();
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "02-events.png"), fullPage: false });

  // Journey 3: Filter Events by Keyword
  const beforeCount = await eventsCards.count();
  await page.fill("#filter-input", "music");
  await page.waitForFunction(
    (expected) => document.querySelectorAll("#events-view .card").length <= expected,
    beforeCount
  );
  const afterCount = await eventsCards.count();
  expect(afterCount).toBeLessThanOrEqual(beforeCount);
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "03-filtered-events.png"), fullPage: false });
  
  // Verify URL parameters
  await expect(page).toHaveURL(/filter=music/);

  // Journey 4: Paired View
  await page.fill("#filter-input", ""); // Clear filter
  await page.getByRole("button", { name: "Paired" }).click();
  await expect(page.locator("#paired-view")).toBeVisible();
  
  // Verify pairings are displayed
  const pairingCards = page.locator("#paired-view .card-paired");
  const pairingCount = await pairingCards.count();
  if (pairingCount > 0) {
    // Verify pairing structure
    await expect(page.locator(".pairing-event").first()).toBeVisible();
    await expect(page.locator(".pairing-restaurant").first()).toBeVisible();
  }
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "04-paired.png"), fullPage: false });

  // Journey 5: Restaurant Filter
  await page.getByRole("button", { name: "Restaurants" }).click();
  await page.fill("#filter-input", "Sushi");
  await page.waitForFunction(
    () => document.querySelectorAll("#restaurants-view .card, #restaurants-view tbody tr").length > 0
  );
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "05-restaurants-filter.png"), fullPage: false });
  
  // Verify filter is applied
  await expect(page).toHaveURL(/filter=Sushi/);

  // Journey 6: Table Layout
  await page.selectOption("#layout-select", "table");
  await expect(page.locator("table")).toBeVisible();
  await expect(page.locator("thead")).toBeVisible();
  await expect(page.locator("tbody tr")).not.toHaveCount(0);
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "06-layout-table.png"), fullPage: false });
  
  // Verify URL parameters persist
  await expect(page).toHaveURL(/layout=table/);
});

test("responsive behavior and navigation", async ({ page }) => {
  await page.goto(`http://localhost:${PORT}`);
  await page.waitForSelector('[data-hs-ready="1"]');
  
  // Test navigation between views
  await page.getByRole("button", { name: "Events" }).click();
  await expect(page.locator("#events-view")).toBeVisible();
  await expect(page.locator("#restaurants-view")).not.toBeVisible();
  
  await page.getByRole("button", { name: "Paired" }).click();
  await expect(page.locator("#paired-view")).toBeVisible();
  await expect(page.locator("#events-view")).not.toBeVisible();
  
  await page.getByRole("button", { name: "Restaurants" }).click();
  await expect(page.locator("#restaurants-view")).toBeVisible();
  await expect(page.locator("#paired-view")).not.toBeVisible();
  
  // Verify active button styling
  const activeButton = page.locator('button[data-view="restaurants"].active');
  await expect(activeButton).toBeVisible();
});

test("filter functionality across views", async ({ page }) => {
  await page.goto(`http://localhost:${PORT}`);
  await page.waitForSelector('[data-hs-ready="1"]');
  
  // Test restaurant filtering
  await page.fill("#filter-input", "BBQ");
  await page.waitForTimeout(300); // Wait for filter to apply
  const restaurantCards = page.locator("#restaurants-view .card");
  const visibleCount = await restaurantCards.count();
  
  // Clear filter
  await page.fill("#filter-input", "");
  await page.waitForTimeout(300);
  const allCount = await restaurantCards.count();
  expect(allCount).toBeGreaterThanOrEqual(visibleCount);
  
  // Screenshot of cleared filter
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "07-filter-cleared.png"), fullPage: false });
});

test("deep linking and URL persistence", async ({ page }) => {
  // Test loading with URL parameters
  await page.goto(`http://localhost:${PORT}?view=events&filter=art&layout=cards`);
  await page.waitForSelector('[data-hs-ready="1"]');
  
  // Verify state from URL
  await expect(page.locator("#events-view")).toBeVisible();
  await expect(page.locator("#filter-input")).toHaveValue("art");
  await expect(page.locator("#layout-select")).toHaveValue("cards");
  
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "08-deep-link.png"), fullPage: false });
});

test("empty state handling", async ({ page }) => {
  await page.goto(`http://localhost:${PORT}`);
  await page.waitForSelector('[data-hs-ready="1"]');
  
  // Navigate to paired view and apply filter that yields no results
  await page.getByRole("button", { name: "Paired" }).click();
  await page.fill("#filter-input", "nonexistentitem12345");
  await page.waitForTimeout(300);
  
  // Verify empty state is shown
  const emptyState = page.locator("#paired-view .empty");
  await expect(emptyState).toBeVisible();
  await expect(emptyState).toContainText("No pairings match");
  
  await page.screenshot({ path: path.join(ARTIFACT_DIR, "09-empty-state.png"), fullPage: false });
});
