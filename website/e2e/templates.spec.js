/**
 * Template clips: adding them, and changing what they say.
 *
 * # Recipe: a title card
 *
 * Templates are made, not uploaded -- a title, a text box, a colour field.
 * Add one from the bin under the timeline (its + button, or drag it into
 * place) or from the Source stage's Templates list. Its settings appear beside
 * the viewer: text, length, font and size, how the text is aligned, where the
 * template sits in the frame, and colours -- whichever of those the template
 * takes. The server renders every change, and if a setting cannot be rendered
 * it says why, next to the settings.
 *
 * None of this worked before. The timeline refused drops from the bin, the
 * drop handler threw on the shape of a template entry when one got through,
 * and there was nowhere to change a template clip once it existed. Template
 * clips only reached a timeline through demo and seed projects.
 */

const { test, expect } = require('./fixtures')

const DEFAULT_TEXT = 'Your text here'

async function templates(request, token) {
  const res = await request.get('/templates', { headers: { Authorization: token } })
  expect(res.status()).toBe(200)
  return res.json()
}

/** Answer `POST /render` without queueing anything, and keep the bodies. */
async function captureRenders(page) {
  const sent = []
  await page.route(
    url => url.pathname === '/render',
    async route => {
      if (route.request().method() !== 'POST') return route.fallback()
      sent.push(route.request().postDataJSON())
      await route.fulfill({ json: 'abcdefabcdefabcdefabcdef' })
    }
  )
  return sent
}

const binEntry = (page, name) => page.locator(`#bin .binclip[data-bin-name="${name}"]`)

function watchErrors(page) {
  const errors = []
  page.on('pageerror', e => errors.push(String(e.message)))
  return errors
}

test.describe('adding a template', () => {
  test('the bin adds a template as a clip with text and five seconds', async ({
    authedPage,
  }) => {
    /**
     * Press + on a template in the bin. It lands on the end of the timeline
     * as five seconds of "Your text here", its settings open beside the
     * viewer, and that is exactly what a render receives.
     */
    const errors = watchErrors(authedPage)
    const sent = await captureRenders(authedPage)
    await authedPage.goto('/#!/?stage=edit')
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(0)

    await binEntry(authedPage, 'title').locator('.binadd').click()

    const clip = authedPage.locator('#timeline .clip.template[name="title"]')
    await expect(clip).toHaveCount(1)
    // Its text, not "Hello, world" twice: the contenteditable it used to be
    // rendered two hard-coded placeholder divs before the real one.
    await expect(clip).toHaveText(DEFAULT_TEXT)

    // Its settings are offered beside the viewer.
    const params = authedPage.locator('#template-params')
    await expect(params).toBeVisible()
    await expect(params.locator('#param-text')).toHaveValue(DEFAULT_TEXT)
    await expect(params.locator('#param-duration')).toHaveValue('5')

    // And that is what a render receives.
    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips).toEqual([
      {
        type: 'template',
        name: 'title',
        duration: 5,
        data: { text: DEFAULT_TEXT },
        start: 0,
        fadeIn: 0,
        fadeOut: 0,
      },
    ])
    expect(errors).toEqual([])
  })

  test('a template that takes no text is not given any', async ({ authedPage }) => {
    /**
     * makeColor's parameters are a colour and a position. Offering it a
     * text field would invite an edit that changes nothing.
     */
    await authedPage.goto('/#!/?stage=edit')
    await binEntry(authedPage, 'makeColor').locator('.binadd').click()

    const params = authedPage.locator('#template-params')
    await expect(params).toBeVisible()
    await expect(params.locator('#param-text')).toHaveCount(0)
    await expect(params.locator('#param-color')).toBeVisible()
    await expect(params.locator('#param-themecolor')).toHaveCount(0)
  })

  test('the Source stage lists every template, and adds one', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Templates are material too, so the Source stage lists them beside the
     * media, and says where an added one landed.
     */
    const offered = await templates(request, token)
    await authedPage.goto('/#!/?stage=source')

    const choices = authedPage.locator('.templatechoice')
    await expect(choices).toHaveCount(offered.length)
    await authedPage.locator('.templatechoice[data-template="textBox"]').click()

    await expect(authedPage.locator('#timeline .clip.template[name="textBox"]')).toHaveCount(1)
    await expect(authedPage.locator('#template-added')).toContainText('textBox')
  })

  test('a template dragged from the bin lands on the timeline', async ({
    authedPage,
  }) => {
    /**
     * The bin and the timeline are two Sortable lists, and the timeline's
     * group accepted only itself -- so a drag from the bin was refused before
     * the drop handler ever ran. And the handler, had it run, read fields
     * from the dragged element that template entries do not have.
     */
    const errors = watchErrors(authedPage)
    // Tall enough that the bin and the timeline are both fully on screen: a
    // drag is a pointer gesture, and it cannot start on something scrolled
    // under the footer.
    await authedPage.setViewportSize({ width: 1280, height: 1000 })
    await authedPage.goto('/#!/?stage=edit')
    await binEntry(authedPage, 'makeColor').locator('.binadd').click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)

    const from = await binEntry(authedPage, 'textBox').locator('.binlabel').boundingBox()
    const to = await authedPage.locator('#timeline .clip').first().boundingBox()
    await authedPage.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
    await authedPage.mouse.down()
    await authedPage.mouse.move(from.x + from.width / 2 + 8, from.y + from.height / 2, {
      steps: 4,
    })
    await authedPage.mouse.move(to.x + to.width - 4, to.y + to.height / 2, { steps: 20 })
    await authedPage.waitForTimeout(250)
    await authedPage.mouse.up()

    await expect(authedPage.locator('#timeline .clip')).toHaveCount(2)
    await expect(authedPage.locator('#timeline .clip.template[name="textBox"]')).toHaveCount(1)
    await expect(authedPage.locator('#timeline .clip.template[name="textBox"]')).toHaveText(
      DEFAULT_TEXT
    )

    // The bin is as it was -- the entry back in it, once, and nothing of the
    // bin's left in the timeline -- and the entry that was dragged still
    // works: a drag used to leave behind a copy with no event handlers.
    await expect(binEntry(authedPage, 'textBox')).toHaveCount(1)
    await expect(authedPage.locator('#timeline .binclip')).toHaveCount(0)
    await binEntry(authedPage, 'textBox').locator('.binadd').click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(3)
    expect(errors).toEqual([])
  })
})

test.describe("changing a template clip's settings", () => {
  test('text, length and colour change the clip, its frame, and its render', async ({
    authedPage,
  }) => {
    /**
     * Each field changes the clip itself: the label on the timeline, its
     * width, the frame the server renders for the viewer, and the clip a
     * render receives. A colour can be typed or picked; the swatch follows.
     */
    const sent = await captureRenders(authedPage)
    const frames = []
    authedPage.on('request', req => {
      const url = new URL(req.url())
      if (url.pathname === '/preview/template/title') frames.push(url.searchParams)
    })

    await authedPage.goto('/#!/?stage=edit')
    await binEntry(authedPage, 'title').locator('.binadd').click()
    const clip = authedPage.locator('#timeline .clip.template[name="title"]')
    const widthBefore = (await clip.boundingBox()).width

    await authedPage.locator('#param-text').fill('Hello there')
    await expect(clip).toHaveText('Hello there')
    await expect
      .poll(() => frames.some(p => p.get('text') === 'Hello there'), {
        message: 'the frame was never rendered with the new text',
      })
      .toBe(true)

    await authedPage.locator('#param-duration').fill('2.5')
    await expect.poll(async () => (await clip.boundingBox()).width).toBeLessThan(widthBefore)

    await authedPage.locator('#param-color').fill('#ff0000')
    await expect
      .poll(() => frames.some(p => p.get('color') === '#ff0000'))
      .toBe(true)
    // The swatch follows the text.
    await expect(authedPage.locator('#template-params .paramcolour input.swatch').first()).toHaveValue(
      '#ff0000'
    )

    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips[0]).toMatchObject({
      name: 'title',
      duration: 2.5,
      data: { text: 'Hello there', color: '#ff0000' },
    })
    expect(sent[0].edl.duration).toBe(2.5)
  })

  test('typing a duration is not interrupted halfway', async ({ authedPage }) => {
    /**
     * The field is controlled; without a draft, "1." would be rewritten to
     * the clip's duration before the next digit arrived.
     */
    await authedPage.goto('/#!/?stage=edit')
    await binEntry(authedPage, 'title').locator('.binadd').click()
    const field = authedPage.locator('#param-duration')
    await field.fill('')
    await field.pressSequentially('1.75')
    await expect(field).toHaveValue('1.75')
  })

  test('a setting that cannot render says why, beside the settings', async ({
    authedPage,
  }) => {
    /**
     * Validation is the server's: the frame is rendered from the clip's data,
     * and a template that cannot render what it was given answers 422 with
     * the reason. That reason was read from a blob response with
     * `responseText`, which throws, so it never reached the screen. Served
     * here so the reason is known.
     */
    const reason = 'title could not be rendered from the data supplied.'
    await authedPage.route(
      url => url.pathname === '/preview/template/title' && url.searchParams.get('color') === 'nope',
      route => route.fulfill({ status: 422, json: { detail: reason } })
    )

    await authedPage.goto('/#!/?stage=edit')
    await binEntry(authedPage, 'title').locator('.binadd').click()
    await expect(authedPage.locator('#preview img.preview, img.preview')).toBeVisible({
      timeout: 20_000,
    })
    await expect(authedPage.locator('#param-problem')).toHaveCount(0)

    await authedPage.locator('#param-color').fill('nope')
    await expect(authedPage.locator('#param-problem')).toHaveText(reason)
    await expect(authedPage.locator('.preview.unrenderable')).toContainText(reason)

    // Back to the template's own colour, and the frame renders again.
    await authedPage.locator('#template-params .paramreset').click()
    await expect(authedPage.locator('#param-problem')).toHaveCount(0)
    await expect(authedPage.locator('img.preview')).toBeVisible({ timeout: 20_000 })
  })
})

test.describe("a template's type and placement", () => {
  /**
   * # Recipe: setting a title's font, size and position
   *
   * A text template is offered a font -- from the fonts this server can draw
   * -- a size, and where it sits in the frame; a text box also how its text
   * is aligned in the box. Each is the template's own until chosen, and
   * "Template default" puts it back.
   */
  const FONTS = ['DejaVu-Sans', 'Nimbus-Sans']

  /** Serve the font list, and keep every frame the viewer asks for. */
  async function serveFonts(page) {
    await page.route(
      url => url.pathname === '/fonts',
      route => route.fulfill({ json: FONTS })
    )
    const frames = []
    page.on('request', req => {
      const url = new URL(req.url())
      if (url.pathname.startsWith('/preview/template/')) frames.push(url.searchParams)
    })
    return frames
  }

  test('font, size, alignment and position change the frame and the render', async ({
    authedPage,
  }) => {
    const frames = await serveFonts(authedPage)
    const sent = await captureRenders(authedPage)
    await authedPage.goto('/#!/?stage=edit')
    await binEntry(authedPage, 'textBox').locator('.binadd').click()

    const font = authedPage.locator('#param-font')
    await expect(font.locator('option')).toHaveText([
      'Template default',
      'DejaVu Sans',
      'Nimbus Sans',
    ])
    await font.selectOption('DejaVu-Sans')
    await authedPage.locator('#param-fontsize').fill('48')
    await authedPage.locator('#param-align').selectOption('West')
    await authedPage.locator('#param-position').selectOption('top')

    // The viewer's frame is rendered with each of them.
    await expect
      .poll(() =>
        frames.some(
          p =>
            p.get('font') === 'DejaVu-Sans' &&
            p.get('fontsize') === '48' &&
            p.get('align') === 'West' &&
            p.get('position') === 'top'
        )
      )
      .toBe(true)

    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips[0].data).toEqual({
      text: DEFAULT_TEXT,
      font: 'DejaVu-Sans',
      fontsize: 48,
      align: 'West',
      position: 'top',
    })
  })

  test('each template is offered only what it takes', async ({ authedPage }) => {
    /**
     * A title takes a font and a position but aligns nothing; a colour field
     * takes a position, and nothing about text.
     */
    await serveFonts(authedPage)
    await authedPage.goto('/#!/?stage=edit')

    await binEntry(authedPage, 'title').locator('.binadd').click()
    const params = authedPage.locator('#template-params')
    await expect(params.locator('#param-font')).toBeVisible()
    await expect(params.locator('#param-fontsize')).toBeVisible()
    await expect(params.locator('#param-position')).toBeVisible()
    await expect(params.locator('#param-align')).toHaveCount(0)

    await binEntry(authedPage, 'makeColor').locator('.binadd').click()
    await expect(params.locator('h4')).toContainText('makeColor')
    await expect(params.locator('#param-position')).toBeVisible()
    for (const field of ['#param-font', '#param-fontsize', '#param-align', '#param-text']) {
      await expect(params.locator(field)).toHaveCount(0)
    }
  })

  test('a font that cannot be drawn says why, and the default puts it right', async ({
    authedPage,
  }) => {
    /**
     * Validation is the server's, as for every setting: the frame is
     * rendered with the font, and a refusal's reason is shown beside the
     * fields. Served here so the reason is known.
     */
    await serveFonts(authedPage)
    const reason = 'title could not be rendered from the data supplied.'
    await authedPage.route(
      url =>
        url.pathname === '/preview/template/title' && url.searchParams.get('font') === 'Nimbus-Sans',
      route => route.fulfill({ status: 422, json: { detail: reason } })
    )
    await authedPage.goto('/#!/?stage=edit')
    await binEntry(authedPage, 'title').locator('.binadd').click()

    await authedPage.locator('#param-font').selectOption('Nimbus-Sans')
    await expect(authedPage.locator('#param-problem')).toHaveText(reason)

    await authedPage.locator('#param-font').selectOption('')
    await expect(authedPage.locator('#param-problem')).toHaveCount(0)
    await expect(authedPage.locator('img.preview')).toBeVisible({ timeout: 20_000 })
  })

  test("a placement written by a project's logic is kept, not replaced", async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * A project can place a template by coordinates, which the form offers
     * no field for. It is shown as set, and goes on to the render untouched
     * when other settings change.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const project = projects.find(p => p.name === 'Timeline demo')
    expect(project, 'Timeline demo is missing; global-setup.js creates it').toBeTruthy()
    const placed = {
      type: 'template',
      name: 'textBox',
      duration: 3,
      data: { text: 'Placed', position: ['center', 0.8] },
    }
    await authedPage.route(
      url => url.pathname === `/project/${project._id}`,
      route =>
        route.request().method() === 'GET'
          ? route.fulfill({ json: { ...project, edl: { clips: [placed], duration: 3 } } })
          : route.fallback()
    )
    // The Render stage remembers the size on the project; the shared fixture
    // is answered here rather than written.
    await authedPage.route(
      url => url.pathname === `/project/${project._id}/settings`,
      route => route.fulfill({ json: project })
    )
    await serveFonts(authedPage)
    const sent = await captureRenders(authedPage)

    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)
    const position = authedPage.locator('#param-position')
    await expect(position.locator('option:checked')).toHaveText('As set: center,0.8')

    await authedPage.locator('#param-text').fill('Still placed')
    await authedPage.locator('#stage-render').click()
    await authedPage.locator('#queue-render').click()
    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].edl.clips[0].data).toEqual({ text: 'Still placed', position: ['center', 0.8] })
  })
})
