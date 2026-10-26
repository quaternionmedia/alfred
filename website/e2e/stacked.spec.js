/**
 * The phone flow: the editor's panels stacked one stage at a time.
 *
 * Below 1024 pixels the editor is not a workspace. The rail chooses a stage,
 * the stage's panels sit under it, and the viewer and the timeline are always
 * below them -- built from the same panel modules the workspace docks
 * (workspace.spec.js). Run by the `phone` project, at 390x844, with the
 * flow, editor, timeline-tools and deliver specs; the picture's room is also
 * checked on a smaller phone, and on one held sideways.
 */

const { test, expect } = require('./fixtures')

const top = async locator => (await locator.boundingBox()).y

/** Each stage, and a panel of its own that says it is open (layout/flow.js). */
const STAGE_PANELS = {
  source: '#panel-source',
  edit: '#panel-captions',
  render: '#panel-render',
  deliver: '#panel-deliver',
}

/**
 * How much of the picture can be seen: the frame's height, and how many of
 * those pixels are inside every box around it that clips -- the viewer's
 * region, the page -- and inside the window, as the page is drawn. A box that
 * is `display: contents` has no edges of its own and clips nothing.
 *
 * Asked of the picture itself, because every other check here passed while
 * the viewer's region was squeezed to a sliver: the frame was the right size,
 * the right shape and in the right place, and almost none of it could be seen.
 */
const pictureShown = page =>
  page.evaluate(() => {
    const frame = document.querySelector('.viewerframe')
    const box = frame.getBoundingClientRect()
    let top = Math.max(box.top, 0)
    let bottom = Math.min(box.bottom, window.innerHeight)
    for (let el = frame.parentElement; el && el !== document.documentElement; el = el.parentElement) {
      const style = getComputedStyle(el)
      if (style.display === 'contents' || !/auto|hidden|scroll|clip/.test(style.overflowY)) continue
      const edges = el.getBoundingClientRect()
      top = Math.max(top, edges.top)
      bottom = Math.min(bottom, edges.bottom)
    }
    return { frame: box.height, shown: Math.max(0, bottom - top) }
  })

/** Where the footer, the last thing in the column, ends: pixels from the window's top. */
const footerEnd = () => document.querySelector('body > footer').getBoundingClientRect().bottom

/**
 * Every stage in turn, chosen on the rail: the whole picture is on the screen
 * as the stage opens, and the rest of the column can be reached below it --
 * scrolled as far as a wheel over the header (which scrolls nothing of its
 * own) takes the page, the footer is in the window. All four stages are
 * asked, so a failure says which of them hide the picture, and by how much.
 *
 * `oneScreen`: and the page does not scroll at all, every region fitting the
 * window with the stage's panels and the timeline at or above their floors.
 */
async function expectEveryStageToShowThePicture(page, { oneScreen = false } = {}) {
  const height = page.viewportSize().height
  await page.goto('/')
  for (const [stage, panel] of Object.entries(STAGE_PANELS)) {
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.locator(`#stage-${stage}`).click()
    await expect(page.locator(`#stage-${stage}`)).toHaveClass(/active/)
    await expect(page.locator(panel)).toBeVisible()

    const { frame, shown } = await pictureShown(page)
    expect(frame, `${stage}: the frame has no height`).toBeGreaterThan(0)
    expect
      .soft(shown, `${stage}: ${Math.round(shown)} of the frame's ${Math.round(frame)} pixels can be seen`)
      .toBeGreaterThanOrEqual(frame * 0.9)

    if (oneScreen) {
      const over = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)
      expect.soft(over, `${stage}: the page scrolls by ${over} pixels, not one screen`).toBeLessThanOrEqual(0)
    }

    const header = await page.locator('body > header').boundingBox()
    await page.mouse.move(header.x + header.width / 2, header.y + header.height / 2)
    await page.mouse.wheel(0, 5000)
    // A wheel scrolls in its own time: wait for the footer, a little.
    await page
      .waitForFunction(h => document.querySelector('body > footer').getBoundingClientRect().bottom <= h + 1, height, {
        timeout: 2000,
      })
      .catch(() => {})
    const end = await page.evaluate(footerEnd)
    expect
      .soft(end, `${stage}: the column runs ${Math.round(end - height)} pixels past the window, out of reach`)
      .toBeLessThanOrEqual(height + 1)
  }
}

test.describe('the phone flow', () => {
  test('is a stack, not a dock', async ({ authedPage }) => {
    /**
     * Below 1024 pixels there is no dock and no Panels menu: the rail, and the
     * regions under it.
     */
    await authedPage.goto('/')
    await expect(authedPage.locator('.stagerail')).toBeVisible()
    await expect(authedPage.locator('#timeline')).toBeVisible()
    await expect(authedPage.locator('#workspace')).toHaveCount(0)
    await expect(authedPage.locator('.lm_goldenlayout')).toHaveCount(0)
    await expect(authedPage.locator('#panels-button')).toHaveCount(0)
  })

  test('a notice lets a tap through to what is under it', async ({ authedPage }) => {
    // Notices cover the timeline for ten seconds; taps must reach it.
    const notice = authedPage.locator('.alertify-notifier .ajs-message.ajs-visible').first()
    await expect(notice, "the login's own notice is up").toBeVisible()
    const box = await notice.boundingBox()
    const stopped = await authedPage.evaluate(
      ([x, y]) => Boolean(document.elementFromPoint(x, y)?.closest('.ajs-message')),
      [box.x + box.width / 2, box.y + box.height / 2]
    )
    expect(stopped, 'a press on a notice stops at the notice').toBe(false)
  })

  test("a stage's panels sit between the rail and the viewer", async ({ authedPage }) => {
    /**
     * Choosing Source puts the project list and the library under the rail,
     * and the viewer and the timeline under them.
     */
    await authedPage.goto('/#!/?stage=source')
    await expect(authedPage.locator('#panel-source')).toBeVisible()
    await expect(authedPage.locator('#panel-media')).toBeVisible()

    const rail = await top(authedPage.locator('.stagerail'))
    const projects = await top(authedPage.locator('#panel-source'))
    const media = await top(authedPage.locator('#panel-media'))
    const viewer = await top(authedPage.locator('section.viewer'))
    const editor = await top(authedPage.locator('section.editor'))
    expect(rail).toBeLessThan(projects)
    expect(projects).toBeLessThan(media)
    expect(media).toBeLessThan(viewer)
    expect(viewer).toBeLessThan(editor)
  })

  test('a long project list scrolls inside its panel, and the timeline stays on screen', async ({
    authedPage,
  }) => {
    /**
     * The stage's panels keep their height up to a share of the screen and
     * scroll inside themselves past it. Unbounded, a long list took the whole
     * column and squeezed the viewer and the timeline out of it.
     */
    const many = Array.from({ length: 40 }, (_, i) => ({
      _id: `${(0xabc000 + i).toString(16).padStart(24, '0')}`,
      name: `Listed project ${i + 1}`,
      edl: { clips: [], duration: 0 },
    }))
    await authedPage.route(
      url => url.pathname === '/project',
      route => (route.request().method() === 'GET' ? route.fulfill({ json: many }) : route.fallback())
    )
    await authedPage.goto('/#!/?stage=source')
    await authedPage.reload()
    await expect(authedPage.locator('.projectrow')).toHaveCount(many.length)

    const panel = authedPage.locator('#panel-source')
    const scrolls = await panel.evaluate(n => n.scrollHeight > n.clientHeight + 1)
    expect(scrolls, 'the project list does not scroll inside its panel').toBe(true)

    // Mutation: let the stage's panels grow with their content -- the list
    // takes the column, the regions below it are pushed off the page, and
    // this fails.
    const viewport = authedPage.viewportSize()
    const stage = await authedPage.locator('.flowstage').boundingBox()
    expect(stage.height).toBeLessThanOrEqual(viewport.height * 0.45 + 1)
    for (const region of ['section.viewer', 'section.transport', 'section.editor']) {
      const at = await authedPage.locator(region).boundingBox()
      expect(at.y, `${region} is pushed off the page`).toBeLessThan(viewport.height - 40)
    }
  })

  test('the viewer and the transport fit the screen', async ({ authedPage }) => {
    /**
     * The frame is the output's shape and no wider than the screen, and the
     * playback and speed buttons wrap rather than run past its edges. Both
     * did: every `section` is a column, which sized the frame's room by the
     * frame, and the two button groups could not wrap.
     */
    await authedPage.goto('/#!/?stage=edit')
    await expect(authedPage.locator('#head')).toBeVisible()
    const width = authedPage.viewportSize().width

    const frame = await authedPage.locator('#head').boundingBox()
    expect(frame.x).toBeGreaterThanOrEqual(0)
    expect(frame.x + frame.width).toBeLessThanOrEqual(width)
    expect(frame.width / frame.height).toBeCloseTo(16 / 9, 1)

    for (const selector of ['#PlaybackTools', '#speed', '#playpause']) {
      const b = await authedPage.locator(selector).boundingBox()
      expect(b.x, `${selector} starts off the screen`).toBeGreaterThanOrEqual(0)
      expect(b.x + b.width, `${selector} runs past the screen`).toBeLessThanOrEqual(width)
    }
  })

  test("the selected template clip's settings are beside the output settings", async ({
    authedPage,
  }) => {
    /**
     * Not a panel of their own on a phone: beside the aspect and the
     * resolution, where they always were, and nothing at all while no template
     * clip is selected.
     */
    await authedPage.goto('/#!/?stage=edit')
    await authedPage.locator('#bin .binclip[data-bin-name="title"] .binadd').click()
    const params = authedPage.locator('.viewersettings #template-params')
    await expect(params).toBeVisible()
    await expect(params.locator('#param-text')).toHaveValue(/./)
    // Not a panel of its own here, and nothing where nothing is selected.
    await expect(authedPage.locator('#template-hint')).toHaveCount(0)
  })
})

/** Every region that scrolls sideways because something in it is too wide. */
const sideways = page =>
  page.evaluate(() =>
    [...document.querySelectorAll('body *')]
      .filter(el => {
        const style = getComputedStyle(el)
        return /auto|scroll/.test(style.overflowX) && el.scrollWidth > el.clientWidth + 1
      })
      .map(el => `${el.id ? '#' + el.id : el.className}: ${el.scrollWidth} in ${el.clientWidth}`)
  )

test.describe('the phone flow fits the width of the phone', () => {
  test('all four stages sit across the rail', async ({ authedPage }) => {
    /**
     * At the rail's desktop spacing the four stages came to 459 pixels, so on
     * a 375-pixel phone Deliver was cut off at its number and the rail
     * scrolled sideways: the last stage of the flow, out of sight.
     *
     * Mutation: drop the rail's narrow-screen spacing (stages.scss) and this
     * fails.
     */
    await authedPage.goto('/')
    const rail = authedPage.locator('.stagerail')
    const width = authedPage.viewportSize().width
    expect(await rail.evaluate(r => r.scrollWidth - r.clientWidth)).toBeLessThanOrEqual(1)
    for (const stage of ['source', 'edit', 'render', 'deliver']) {
      const b = await authedPage.locator(`#stage-${stage}`).boundingBox()
      expect(b.x + b.width, `${stage} runs past the screen`).toBeLessThanOrEqual(width)
    }
  })

  test('no stage scrolls sideways', async ({ authedPage, request, token }) => {
    /**
     * The scrubber was the whole row plus its margins, and the transport
     * scrolled sideways by 32 pixels to show them; a generated clip's long
     * file name ran the Material panel past the screen. A phone held upright
     * scrolls one way.
     */
    // A file name as long as the ones the editor generates, so there is one
    // to break whatever the library holds.
    await authedPage.route(
      url => url.pathname === '/media',
      async route => {
        // A stage chosen reloads the library, and the page can move on before
        // an answer is read; reading it then threw "Response has been
        // disposed" into the test, in two runs of four against a dev stack. There
        // is nothing left to change by then, so the request goes on as sent.
        const response = await route.fetch().catch(() => null)
        const items = response && (await response.json().catch(() => null))
        if (!items) return route.continue().catch(() => {})
        const long = { name: 'videos/Demo_320x180_9.0s_20260809-112440_6a786378bc3b0bdd8e881398.mp4', kind: 'video', duration: 9, size: 1 }
        await route.fulfill({ response, json: [...items, long] })
      }
    )
    await authedPage.goto('/')
    for (const stage of ['source', 'edit', 'render', 'deliver']) {
      await authedPage.locator(`#stage-${stage}`).click()
      await expect(authedPage.locator(STAGE_PANELS[stage])).toBeVisible()
      expect(await sideways(authedPage), `${stage} scrolls sideways`).toEqual([])
    }
  })

  test.describe('on a narrower phone', () => {
    test.use({ viewport: { width: 360, height: 740 } })

    test('the rail and every stage still fit', async ({ authedPage }) => {
      await authedPage.goto('/')
      const rail = authedPage.locator('.stagerail')
      expect(await rail.evaluate(r => r.scrollWidth - r.clientWidth)).toBeLessThanOrEqual(1)
      for (const stage of ['source', 'edit', 'render', 'deliver']) {
        await authedPage.locator(`#stage-${stage}`).click()
        await expect(authedPage.locator(STAGE_PANELS[stage])).toBeVisible()
        expect(await sideways(authedPage), `${stage} scrolls sideways`).toEqual([])
      }
    })
  })
})

test.describe('the Source stage', () => {
  test('gives its panels the room the timeline can spare', async ({ authedPage }) => {
    /**
     * Choosing is the work on Source, so the viewer and the timeline give way
     * first, to their floors. Shared in proportion as on the other stages,
     * the timeline took 207 pixels at 375x812 and the project list 78: its
     * heading, its filter, and not one whole project.
     *
     * Mutation: drop the Source stage's `flex-shrink` (flow.scss) and the
     * timeline keeps more than its floor, and this fails.
     */
    const listed = Array.from({ length: 12 }, (_, i) => ({
      _id: `${(0xbcd000 + i).toString(16).padStart(24, '0')}`,
      name: `Listed project ${i + 1}`,
      edl: { clips: [], duration: 0 },
    }))
    await authedPage.route(
      url => url.pathname === '/project',
      route => (route.request().method() === 'GET' ? route.fulfill({ json: listed }) : route.fallback())
    )
    await authedPage.goto('/#!/?stage=source')
    await authedPage.reload()
    await expect(authedPage.locator('.projectrow')).toHaveCount(listed.length)

    const stage = await authedPage.locator('.flowstage').boundingBox()
    const timeline = await authedPage.locator('section.editor').boundingBox()
    expect(stage.height, 'the stage panels are smaller than the timeline').toBeGreaterThan(timeline.height)

    const panel = await authedPage.locator('#panel-source').boundingBox()
    const whole = await authedPage.locator('.projectrow').evaluateAll(
      (rows, p) => rows.filter(r => {
        const b = r.getBoundingClientRect()
        return b.top >= p.y - 1 && b.bottom <= p.y + p.height + 1
      }).length,
      panel
    )
    expect(whole, 'not one whole project can be seen').toBeGreaterThanOrEqual(2)
  })
})

test.describe('the Render stage', () => {
  test('shows its whole form, Queue render included', async ({ authedPage }) => {
    /**
     * Width and height took a row each at the inputs' own width, and shared
     * in proportion the stage had 114 pixels at 375x812: Width, the top of
     * Height, and Queue render below them, out of sight.
     *
     * Mutation: drop the Render stage's rules (flow.scss) and the form
     * scrolls inside its panel; drop the fields' row (stages.scss) and width
     * and height stack again. Either fails this.
     */
    await authedPage.goto('/#!/?stage=render')
    const panel = authedPage.locator('#panel-render')
    await expect(panel).toBeVisible()
    expect(
      await panel.evaluate(p => p.scrollHeight - p.clientHeight),
      'the form scrolls inside its panel'
    ).toBeLessThanOrEqual(1)

    const width = await authedPage.locator('#render-width').boundingBox()
    const height = await authedPage.locator('#render-height').boundingBox()
    expect(Math.abs(width.y - height.y), 'width and height share a row').toBeLessThanOrEqual(1)

    const button = await authedPage.locator('#queue-render').boundingBox()
    const stage = await authedPage.locator('.flowstage').boundingBox()
    expect(button.y + button.height, 'Queue render is below the stage').toBeLessThanOrEqual(
      stage.y + stage.height
    )
  })
})

test.describe('the picture keeps its room', () => {
  test("every stage shows the whole picture on one screen at a phone's size", async ({
    authedPage,
  }) => {
    /**
     * In every stage the whole picture is on the screen, and the stage's own
     * panels and the timeline give way to it, scrolling inside themselves --
     * at 390x844 all on one screen, the page itself not scrolling. The
     * viewer's region was a scroller the column could squeeze like any other,
     * and it was squeezed, under the stage's panels at their full share: to a
     * few dozen pixels of a 203-pixel picture at 390x844, and to none of it
     * at 375x667.
     */
    await expectEveryStageToShowThePicture(authedPage, { oneScreen: true })
  })

  test.describe('on a smaller phone', () => {
    test.use({ viewport: { width: 375, height: 667 } })

    test('every stage shows the whole picture, and the page scrolls to the rest', async ({
      authedPage,
    }) => {
      /**
       * At 375x667 the stage's panels and the timeline would share about 100
       * pixels, which holds a heading of the one and a row of tools of the
       * other. They keep a floor instead, and the page scrolls past it -- by
       * the window, from anywhere that does not scroll itself.
       */
      await expectEveryStageToShowThePicture(authedPage)
    })
  })

  test.describe('held sideways', () => {
    test.use({ viewport: { width: 844, height: 390 } })

    test('every stage shows the whole picture, and the page scrolls to the rest', async ({
      authedPage,
    }) => {
      /**
       * The frame's room is two-fifths of the screen held sideways, and the
       * header, the rail, the room, the transport and the footer are taller
       * than the screen on their own, so this page has to scroll. The column
       * used to run on past the window's edge instead, out of reach.
       */
      await expectEveryStageToShowThePicture(authedPage)
    })
  })
})
