import { expect, test } from "@playwright/test";

// Dashboard browser check (§19): after building a quote whose assembly line has
// a parameter changed from its default, the dashboard's per-assembly usage table
// should list the assembly with its usage counts and a non-zero edit rate.
// Runs against the real SPA + API in a browser. Requires `playwright install`.

function unique(prefix: string): string {
  return `${prefix}-${Date.now()}@example.com`;
}

test("dashboard lists per-assembly usage and edit rate", async ({ page }) => {
  const email = unique("e2e-dash");

  // --- Register ---
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Dana Dashboard");
  await page.getByLabel("Business name").fill("Dash Electric");
  await page.getByLabel("Province").selectOption("ON");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("supersecret123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/settings/);

  // --- Business defaults (healthy markup so the quote is not audit-blocked) ---
  await page.getByLabel("Blended labour rate ($/hr)").fill("110");
  await page.getByLabel("Material markup (%)").fill("60");
  await page.getByLabel("Labour markup (%)").fill("60");
  await page.getByRole("button", { name: "Save" }).first().click();
  await expect(page.getByText("Saved.")).toBeVisible();

  // --- Add a customer ---
  await page.getByRole("link", { name: "Customers" }).click();
  await page.getByRole("link", { name: "New customer" }).click();
  await page.getByLabel("Name").fill("Jane Homeowner");
  await page.getByLabel("Address", { exact: true }).fill("1 Main St");
  await page.getByLabel("City").fill("Ottawa");
  await page.getByLabel("Postal code").fill("K1A0A1");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Jane Homeowner")).toBeVisible();

  // --- New quote ---
  await page.getByRole("link", { name: "Quotes" }).click();
  await page.getByRole("link", { name: "New quote" }).click();
  await page.getByLabel("Customer").selectOption({ label: /Jane Homeowner/ });
  await page.getByLabel("Job title").fill("New kitchen circuit");
  await page.getByRole("button", { name: "Create quote" }).click();
  await expect(page).toHaveURL(/\/quotes\/[0-9a-f-]+$/);

  // --- Add an assembly, then change a parameter from its default ---
  await page
    .getByLabel("Add assembly")
    .selectOption({ label: "New 15A residential branch circuit" });
  await page.getByRole("button", { name: "+" }).click();

  // Reveal the per-line parameter editor and override a numeric default.
  await page.getByRole("button", { name: /Options/ }).click();
  await page.getByLabel("run length ft").fill("75");

  // Recompute persists the line (including the edited parameter).
  await page.getByRole("button", { name: "Recompute" }).click();
  await expect(page.getByText(/Total/)).toBeVisible();

  // --- Dashboard: assembly usage table ---
  await page.getByRole("link", { name: "Dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  const card = page.locator(".card", { hasText: "Assembly usage" });
  await expect(card.getByRole("heading", { name: "Assembly usage" })).toBeVisible();

  const row = card.getByRole("row", { hasText: "circuit_new_15a_residential" });
  await expect(row).toBeVisible();
  await expect(row).toContainText("New 15A residential branch circuit");
  // One line for this assembly, in one quote, with its parameter changed -> 100%.
  await expect(row).toContainText("100%");
});
