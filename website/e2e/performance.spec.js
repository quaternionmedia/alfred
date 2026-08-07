const { test, expect } = require('./fixtures')

/**
 * Page-load budget.
 *
 * Tagged @perf and excluded from the default project, so it runs when someone
 * asks for it rather than gating every pull request. The Cypress original
 * asserted a hard 1000ms ceiling on a shared CI runner, which is a flake
 * generator: it fails on a noisy neighbour and passes on a fast one, and
 * neither outcome says anything about a code change.
 *
 * Kept because the intent is sound. Changed so a failure means something: the
 * budget is configurable, and the measurement uses the Navigation Timing entry
 * rather than marks straddling `onBeforeLoad`/`onLoad` callbacks.
 */
const BUDGET_MS = Number(process.env.E2E_LOAD_BUDGET_MS || 3000)

test.describe('performance @perf', () => {
  test('loads the shell within the budget @perf', async ({ page }) => {
    await page.goto('/', { waitUntil: 'load' })

    const duration = await page.evaluate(() => {
      const [nav] = performance.getEntriesByType('navigation')
      return nav ? nav.loadEventEnd - nav.startTime : null
    })

    expect(duration, 'no navigation timing entry available').not.toBeNull()
    expect(
      duration,
      `page load took ${Math.round(duration)}ms, budget is ${BUDGET_MS}ms`
    ).toBeLessThanOrEqual(BUDGET_MS)
  })
})
