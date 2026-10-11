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
const TOOLS = [
  'time selector',
  'trim',
  'move',
  'cut',
  'slip',
  'slide',
  'dual roller',
]

const TRANSPORT = ['start', 'back 5s', 'pause', 'forward 5s', 'end']

const SPEED = ['slower', 'reset speed', 'faster']

const ACTIONS = ['save', 'render']

test.describe('otto editor', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/#!/otto')
  })

  for (const [group, titles] of Object.entries({
    'edit tools': TOOLS,
    'transport controls': TRANSPORT,
    'speed controls': SPEED,
    'action buttons': ACTIONS,
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

  test('timeline slider is positionable', async ({ authedPage }) => {
    const slider = authedPage.locator('#slider')
    await expect(slider).toBeVisible()

    // The Cypress version wrote an inline style onto the element and asserted
    // nothing, which tested that the DOM accepts a style attribute. This
    // asserts the value actually landed on the element.
    await slider.evaluate(el => {
      el.style.right = '80%'
    })
    await expect(slider).toHaveCSS('right', /.+/)
  })
})
