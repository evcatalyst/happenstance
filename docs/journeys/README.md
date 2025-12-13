# Journey Report

Screenshots are produced by the Playwright E2E suite and saved as artifacts alongside this report.

1. **Home (restaurants default)** – `01-home.png`  
   ![Home](01-home.png)
2. **Events view** – `02-events.png`  
   ![Events](02-events.png)
3. **Events filtered (e.g., “music”)** – `03-filtered-events.png`  
   ![Filtered events](03-filtered-events.png)
4. **Paired recommendations** – `04-paired.png`  
   ![Paired](04-paired.png)
5. **Restaurants filtered** – `05-restaurants-filter.png`  
   ![Restaurants filter](05-restaurants-filter.png)
6. **Restaurants table layout** – `06-layout-table.png`  
   ![Table layout](06-layout-table.png)

Steps covered:
1. Load the site, wait for `data-hs-ready=1`.
2. Switch to Events and filter.
3. View Paired recommendations.
4. Return to Restaurants, filter, and toggle Table layout.

Artifacts are uploaded in CI; regenerate by running `npm run test:e2e`.
