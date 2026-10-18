/**
 * The phone flow: the editor's panels stacked one stage at a time.
 *
 * Below 1024 pixels the editor is not a workspace. The rail chooses a stage,
 * the stage's panels sit under it, and the viewer and the timeline are always
 * below them -- built from the same panel modules the workspace docks
 * (workspace.spec.js). Run by the `phone` project, at 390x844, with the
 * flow, editor, timeline-tools and deliver specs.
 */

const { test, expect } = require('./fixtures')

const top = async locator => (await locator.boundingBox()).y

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
