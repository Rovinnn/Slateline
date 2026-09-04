/**
 * Renders sample_budget.html to a real PDF (with a text layer, so the parser
 * has something to read) using the Playwright Chromium already installed for
 * the frontend's browser checks.
 *
 *   python samples/make_sample_budget.py && node samples/render_budget_pdf.mjs
 */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
// Playwright is a frontend devDependency, not a root one; resolve it from
// there so this runs from any cwd without a second node_modules tree.
const { chromium } = createRequire(path.join(here, "..", "frontend", "package.json"))("playwright");
const htmlPath = path.join(here, "sample_budget.html");
const pdfPath = path.join(here, "sample-budget-bluewater.pdf");

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`file://${htmlPath.replace(/\\/g, "/")}`, { waitUntil: "load" });
await page.pdf({ path: pdfPath, format: "Letter", printBackground: true });
await browser.close();
console.log(`wrote ${pdfPath}`);
