const { test, expect } = require('./fixtures')

/**
 * The tour's box stands wholly inside the window.
 *
 * The box is a popover over the editor (src/Tour.js), placed by its own
 * script, so nothing in the workspace keeps it on screen: it is placed once
 * its stage is drawn, or it is placed as an empty box and grows past the
 * window's foot. And the editor's own rules do not reach it: a rule for the
 * editor's header made the box's head wider than the box, which then scrolled
 * sideways and clipped its close button.
 */

const box = page => page.locator('#tour')

async function openTheTour(page) {
  await page.goto('/')
  await page.locator('#tour-open').click()
  await expect(box(page).locator('.tourtitle')).toBeVisible()
}

/** The box's edges and the window's, as the page measures them. */
const edges = page =>
  box(page).evaluate(el => {
    const r = el.getBoundingClientRect()
    return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: innerWidth, height: innerHeight }
  })

test.describe('the tour box', () => {
  test('opens with all of it inside the window', async ({ authedPage }) => {
    await openTheTour(authedPage)
    const at = await edges(authedPage)
    expect(at.top).toBeGreaterThanOrEqual(0)
    expect(at.left).toBeGreaterThanOrEqual(0)
    expect(at.bottom).toBeLessThanOrEqual(at.height)
    expect(at.right).toBeLessThanOrEqual(at.width)
  })

  test('holds nothing wider than itself', async ({ authedPage }) => {
    await openTheTour(authedPage)
    const widths = await box(authedPage).evaluate(el => ({
      box: el.clientWidth,
      scroll: el.scrollWidth,
      head: el.querySelector('.tourhead').getBoundingClientRect().width,
      outer: el.getBoundingClientRect().width,
    }))
    expect(widths.scroll).toBeLessThanOrEqual(widths.box)
    expect(widths.head).toBeLessThanOrEqual(widths.outer)
    await expect(box(authedPage).locator('.tourclose')).toBeInViewport({ ratio: 1 })
  })
})
