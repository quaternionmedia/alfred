/**
 * Saving the docs' screenshots to docs/assets/screens/<name>.png.
 * Used by screens.spec.js and recipes.spec.js; test_docs_images.py reads `save(page, '<name>')`.
 */

const fs = require('fs')
const path = require('path')
const { expect } = require('@playwright/test')

const SCREENS = path.join(__dirname, '..', '..', 'docs', 'assets', 'screens')

/** Save the page as `docs/assets/screens/<name>.png`, once it has settled. */
async function save(page, name) {
  await page.waitForLoadState('networkidle')
  // Every picture on the page drawn, the preview's included.
  await expect
    .poll(() =>
      page.evaluate(() =>
        [...document.images].every(image => image.complete && image.naturalWidth > 0)
      )
    )
    .toBe(true)
  // The pointer off the page, so nothing is drawn hovered.
  await page.mouse.move(-1, -1)
  await page.waitForTimeout(400)
  await page.screenshot({
    path: path.join(SCREENS, `${name}.png`),
    animations: 'disabled',
    caret: 'hide',
    // The notices the test's own login raised, which a person at this
    // screen would not see.
    style: '.alertify-notifier { display: none !important; }',
  })
}

/** A screen's file goes first, so a screen that fails leaves none behind. */
function clear(name) {
  fs.rmSync(path.join(SCREENS, `${name}.png`), { force: true })
}

module.exports = { SCREENS, save, clear }
