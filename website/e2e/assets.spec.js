/**
 * The interface's own assets come from the app, not from a CDN.
 *
 * AGENTS.md rules out frontend assets loaded from a CDN, and the icon font was
 * one: its stylesheet named a file on Google's font servers, and that face
 * was the one the browser used, so every page view fetched it from Google.
 * The font is bundled from an npm package now. These hold that in place, and
 * check what someone using the app would notice -- that the icons are icons,
 * rather than the ligature names ("play_arrow") a missing font leaves on the
 * buttons.
 */

const { test, expect, login } = require('./fixtures')

const STAGES = ['source', 'edit', 'render', 'deliver']

// Names the app asks the icon font for that no Material Icons font has. Each
// is a defect, pinned by a test of its own below, and left out of the check
// that every other icon is a glyph.
const NOT_IN_THE_FONT = ['swap_horizontal']

test('no stylesheet or font comes from another origin', async ({ page, baseURL }) => {
  /**
   * Every request from the first one, login screen included, so a link in
   * index.html cannot slip past by loading before the session exists. And
   * declared counts as well as fetched: of two faces with the same family,
   * style and weight the browser downloads only the one it settles on, so a
   * CDN face shadowed by a local one is never requested -- until the local
   * one goes away.
   */
  const origin = new URL(baseURL).origin
  const fetched = []
  page.on('request', request => {
    const kind = request.resourceType()
    if ((kind === 'stylesheet' || kind === 'font') && new URL(request.url()).origin !== origin) {
      fetched.push(`${kind}: ${request.url()}`)
    }
  })

  await login(page)
  for (const stage of STAGES) {
    await page.goto(`/?stage=${stage}`)
    await page.evaluate(() => document.fonts.ready)
  }
  expect(fetched, 'fetched from another origin').toEqual([])

  const declared = await page.evaluate(here => {
    const found = []
    for (const sheet of document.styleSheets) {
      let rules
      try {
        rules = sheet.cssRules
      } catch {
        found.push(`unreadable stylesheet: ${sheet.href}`)
        continue
      }
      for (const rule of rules) {
        if (!(rule instanceof CSSFontFaceRule)) continue
        const src = rule.style.getPropertyValue('src')
        for (const [, url] of src.matchAll(/url\(\s*["']?([^"')]+)/g)) {
          if (new URL(url, document.baseURI).origin !== here) found.push(url)
        }
      }
    }
    return found
  }, origin)
  expect(declared, 'font faces naming another origin').toEqual([])
})

test('every icon on every stage is drawn by the icon font', async ({ authedPage }) => {
  /**
   * A name the font knows is one glyph, about as wide as the text is tall. A
   * missing font leaves the name itself on the button, and a name the font
   * does not know leaves blank space, a letter's width per letter; either
   * way the text is several ems wide. So this is geometry, over the icons
   * actually shown, rather than a list of names kept by hand. The text is
   * measured, not the element, so padding cannot count.
   */
  for (const stage of STAGES) {
    await authedPage.goto(`/?stage=${stage}`)
    // Visible, not merely first: at desktop width the menu icon, first in
    // the page, is hidden.
    await expect(authedPage.locator('i.material-icons:visible').first()).toBeVisible()

    const faces = await authedPage.evaluate(async () => {
      await document.fonts.ready
      return [...document.fonts]
        .filter(face => face.family.replace(/["']/g, '') === 'Material Icons')
        .map(face => face.status)
    })
    expect(faces, `the icon font did not load on ${stage}`).toContain('loaded')

    const words = await authedPage.locator('i.material-icons').evaluateAll(
      (icons, known) =>
        icons
          .filter(icon => icon.getClientRects().length > 0)
          .filter(icon => !known.includes(icon.textContent.trim()))
          .map(icon => {
            const range = document.createRange()
            range.selectNodeContents(icon)
            const width = range.getBoundingClientRect().width
            const ems = width / parseFloat(getComputedStyle(icon).fontSize)
            return { name: icon.textContent.trim(), ems }
          })
          .filter(({ ems }) => ems > 1.5)
          .map(({ name, ems }) => `${name} (${ems.toFixed(1)} em wide)`),
      NOT_IN_THE_FONT
    )
    expect(words, `icons drawn as words on ${stage}`).toEqual([])
  }
})

test('the move tool asks for `swap_horizontal`, which the font does not have', async ({
  authedPage,
}) => {
  /**
   * A defect, pinned rather than hidden. Material Icons calls the icon
   * `swap_horiz`. The font draws that glyph for the first ten letters of
   * TimelineTools.js's name and blank space for the last five, so the button
   * looks right while its text is six ems wide in a one-em box -- with the
   * CDN font as with this one. Fixing the name fails this test; then delete
   * it, and the name from NOT_IN_THE_FONT.
   */
  await authedPage.goto('/?stage=edit')
  await authedPage.evaluate(() => document.fonts.ready)

  const ems = await authedPage.locator('[data-tool="move"]').evaluate(icon => {
    const range = document.createRange()
    range.selectNodeContents(icon)
    return range.getBoundingClientRect().width / parseFloat(getComputedStyle(icon).fontSize)
  })
  expect(ems, 'the move tool icon, in ems').toBeGreaterThan(1.5)
})
