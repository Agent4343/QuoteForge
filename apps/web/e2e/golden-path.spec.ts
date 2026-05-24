import { expect, test } from "@playwright/test";

// Golden path (§21): a contractor signs up, sets defaults, adds a customer,
// builds a quote, sees the engine-computed total and audit, and opens the PDF.
// Runs against the real SPA + API in a browser. Requires `playwright install`.

function unique(prefix: string): string {
  return `${prefix}-${Date.now()}@example.com`;
}

test("sign up, configure, quote, and preview PDF", async ({ page }) => {
  const email = unique("e2e");

  // --- Register ---
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Sam Sparks");
  await page.getByLabel("Business name").fill("Sparks Electric");
  await page.getByLabel("Province").selectOption("ON");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("supersecret123");
  await page.getByRole("button", { name: "Create account" }).click();

  // Lands on settings after registration.
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

  // Quote builder loads.
  await expect(page).toHaveURL(/\/quotes\/[0-9a-f-]+$/);

  // --- Add an assembly and recompute ---
  await page
    .getByLabel("Add assembly")
    .selectOption({ label: "New 15A residential branch circuit" });
  await page.getByRole("button", { name: "+" }).click();
  await page.getByRole("button", { name: "Recompute" }).click();

  // The engine-computed total (CAD) appears in the estimate pane.
  await expect(page.getByText(/Total/)).toBeVisible();
  await expect(page.getByText(/\$\d/).first()).toBeVisible();

  // --- PDF preview ---
  await page.getByRole("link", { name: "Download PDF" }).click();
  await expect(page).toHaveURL(/\/pdf-preview/);
  await expect(page.locator("iframe")).toBeVisible();
});
