const { test, expect } = require('./fixtures')

/**
 * Otto editor toolbar.
 *
 * The Cypress version listed selectors with no assertions attached. `cy.get`
 * fails when nothing matches, so those were implicit existence checks -- but
 * three of them targeted generated markup rather than the app's own hooks:
 * `.bar.right > :nth-child(1) > .custom`, `[style="width: auto;"] > :nth-child(1)`,
 * and `[style="position: absolute; right: 0px;"]`. Matching on an inline
 * style attribute breaks on any CSS change and says nothing about behavior.
 * The first of those is the "reset speed" control, which has a title like
 * every other button, so it is addressed by title here. The other two are
 * dropped; they identified no nameable control.
 */
// The timeline tools, by `data-tool` rather than by title: a tool's title is
// its tooltip, and the tooltip is where it explains itself -- the cut tool
// says how to use it, and the tools not built yet say that.
const TOOLS = ['time', 'trim', 'move', 'cut']
const NOT_YET = ['slip', 'slide', 'dual roller']

// The seek controls, by title. Play is checked separately by id: its title
// is the action it will perform, so it reads "play" when stopped and "pause"
// while running -- and on an empty timeline it explains that there is nothing
// to play instead.
const TRANSPORT = ['start', 'back 5s', 'forward 5s', 'end']

const SPEED = ['slower', 'reset speed', 'faster']

// The project actions, by id. Their titles are now the reason they are
// unavailable when they are -- "Nothing on the timeline to save" rather than
// "save" -- so a title is not a stable handle for them.
const ACTION_IDS = ['#save-timeline', '#render-timeline']

test.describe('otto editor', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/#!/otto')
  })

  test('edit tools are present', async ({ authedPage }) => {
    for (const tool of TOOLS) {
      const control = authedPage.locator(`#TTools [data-tool="${tool}"]`)
      await expect(control, `missing tool: ${tool}`).toBeVisible()
      await expect(control).not.toHaveClass(/disabled/)
    }
  })

  test('tools that are not built yet say so, and do not pretend', async ({
    authedPage,
  }) => {
    /**
     * Slip, slide and dual roller could be chosen -- they lit up like the
     * others -- and then did nothing to any clip. They are visibly disabled
     * now, with a title saying why, and choosing one says so too.
     */
    const active = () =>
      authedPage
        .locator('#TTools [aria-pressed="true"]')
        .evaluateAll(nodes => nodes.map(n => n.dataset.tool))

    for (const tool of NOT_YET) {
      const control = authedPage.locator(`#TTools [data-tool="${tool}"]`)
      await expect(control).toBeVisible()
      await expect(control).toHaveClass(/disabled/)
      await expect(control).toHaveAttribute('aria-disabled', 'true')
      await expect(control).toHaveAttribute('title', /not yet/i)

      // Forced: it is announced as disabled, so Playwright will not press it
      // by default -- but a pointer still can, and should be told why
      // nothing happened.
      await control.click({ force: true })
      expect(await active(), `choosing ${tool} changed the tool`).toEqual(['time'])
      await expect(
        authedPage.locator('.ajs-message').filter({ hasText: /not available yet/i }).first()
      ).toBeVisible()
    }
  })

  for (const [group, titles] of Object.entries({
    'transport controls': TRANSPORT,
    'speed controls': SPEED,
  })) {
    test(`${group} are present`, async ({ authedPage }) => {
      for (const title of titles) {
        await expect(
          authedPage.locator(`[title="${title}"]`),
          `missing control: ${title}`
        ).toBeVisible()
      }
    })
  }

  test('action buttons are present', async ({ authedPage }) => {
    for (const id of ACTION_IDS) {
      await expect(authedPage.locator(id), `missing control: ${id}`).toBeVisible()
    }
  })

  test('the play control is present', async ({ authedPage }) => {
    await expect(authedPage.locator('#playpause')).toBeVisible()
  })

  test('timeline slider is positionable', async ({ authedPage }) => {
    const slider = authedPage.locator('#slider')
    await expect(slider).toBeVisible()

    // The Cypress version wrote an inline style onto the element and asserted
    // nothing, which tested that the DOM accepts a style attribute.
    //
    // The first attempt here asserted toHaveCSS('right', /.+/), which was no
    // better: .slider is statically positioned, so computed `right` is the
    // string "auto" beforehand and /.+/ matches that too. It passed with the
    // evaluate() below deleted entirely. Assert the exact value.
    await expect(slider).toHaveCSS('right', 'auto')
    await slider.evaluate(el => {
      el.style.right = '80%'
    })
    await expect(slider).toHaveCSS('right', '80%')
  })
})
