/**
 * The recipes, written to be watched.
 *
 * # Recipes
 *
 * These are tagged `@recipe` and are the source of both halves of the
 * documentation: `docs/cookbook.md` is generated from their titles and
 * comments, and `./al recipes` records them as video through the `docs`
 * Playwright project. A demonstration made this way cannot drift from the
 * behaviour, because it is the behaviour -- and when a recipe breaks there is
 * no video rather than a misleading one.
 *
 * They are deliberately unhurried. Every other spec asserts as fast as it can;
 * these pause between steps so a person watching can follow, which is the one
 * place in this suite where a `waitForTimeout` is the point rather than a
 * smell.
 *
 * Excluded from the `chromium` project, so the gate on every pull request does
 * not pay for the pauses.
 */

const { test: base, expect, login } = require('./fixtures')
// Screenshots for the docs (screens.js).
const { save, clear } = require('./screens')

// What a recipe's project is made from, of what `POST /demo/media` makes.
const DEMO_MEDIA = ['demo-bars.mp4', 'demo-colour.mp4', 'demo-testcard.mp4']

const auth = token => ({ headers: { Authorization: token } })

/**
 * Narrow the page's lists to what the recipe made.
 *
 * The projects, the media library and the renders are the stack's, and on
 * someone's own stack they are that person's: a recording made there would
 * publish them. Each list is fetched from the server as usual and answered
 * with only the recipe's entries -- its projects, the demo media, and the
 * renders of its projects.
 */
async function onlyWhatItMade(page, made) {
  const its = {
    '/project': entry => made.has(entry._id),
    '/media': entry => DEMO_MEDIA.some(name => String(entry.name).endsWith(name)),
    '/videos': entry => DEMO_MEDIA.some(name => String(entry).endsWith(name)),
    '/render': entry => made.has(entry.project_id),
  }
  await page.route(
    url => Object.hasOwn(its, url.pathname),
    async route => {
      if (route.request().method() !== 'GET') return route.fallback()
      const response = await route.fetch()
      const listed = await response.json()
      const keep = its[new URL(route.request().url()).pathname]
      await route.fulfill({
        response,
        json: Array.isArray(listed) ? listed.filter(keep) : listed,
      })
    }
  )
}

/**
 * Open the recipe's page: its lists narrowed, then logged in.
 *
 * Narrowed first, because the page fetches its lists as the session starts.
 * A recording starts with the page, so each one opens on this login; the
 * seconds it took are noted on the test, and `./al recipes` starts the
 * recipe's GIF there.
 */
async function openRecipe(page, made, opened) {
  await onlyWhatItMade(page, made)
  await login(page)
  test.info().annotations.push({
    type: 'recipe-starts',
    description: ((Date.now() - opened) / 1000).toFixed(2),
  })
}

/** Every project, file and render the page shows is the recipe's own. */
async function everyRowIsItsOwn(page, made) {
  const names = [...made.values()].map(entry => entry.name)
  const strangers = []
  for (const text of await page.locator('.projectchoice').allTextContents()) {
    if (!names.some(name => text.includes(name))) strangers.push(`project ${text}`)
  }
  for (const name of await page
    .locator('.mediachoice')
    .evaluateAll(rows => rows.map(row => row.dataset.media))) {
    if (!DEMO_MEDIA.some(file => String(name).endsWith(file))) strangers.push(`file ${name}`)
  }
  for (const text of await page.locator('.renderitem .rendername').allTextContents()) {
    if (!names.some(name => text.includes(name))) strangers.push(`render ${text}`)
  }
  expect(strangers, 'rows the recipe did not make').toEqual([])
}

/**
 * Delete what the recipe made: its projects' renders, once the worker is done
 * with them, then the projects. What it only showed is left alone.
 */
async function removeWhatItMade(request, token, made) {
  const owned = [...made].filter(([, entry]) => entry.owned).map(([id]) => id)
  if (!owned.length) return
  const renders = (await (await request.get('/render', auth(token))).json()).filter(render =>
    owned.includes(render.project_id)
  )
  for (const render of renders) {
    await expect
      .poll(
        async () =>
          (await (await request.get(`/render/${render._id}/status`, auth(token))).json())
            .state,
        { timeout: 90_000, intervals: [1000] }
      )
      .toMatch(/rendered|failed/)
    await request.delete(`/render/${render._id}`, auth(token))
  }
  for (const id of owned) await request.delete(`/project/${id}`, auth(token))
}

const test = base.extend({
  /** When the page opened: its recording starts then. */
  opened: async ({ page }, use) => {
    await use(Date.now())
  },

  /** What the recipe made or may show, by id: `{ name, owned }`. */
  made: async ({ request, token }, use) => {
    const made = new Map()
    await use(made)
    await removeWhatItMade(request, token, made)
  },

  /** The recipe's project: two demo clips between a title and a text box. */
  project: async ({ request, token, made }, use) => {
    expect((await request.post('/demo/media', auth(token))).status()).toBe(200)
    const videos = (await (await request.get('/videos', auth(token))).json()).map(String)
    const clip = name => {
      const found = videos.find(video => video.endsWith(name))
      expect(found, `${name} is in the library`).toBeTruthy()
      return found
    }
    const edl = {
      clips: [
        {
          type: 'template',
          name: 'title',
          duration: 3,
          start: 0,
          data: { text: 'Alfred', color: '#f2aa4c' },
        },
        { type: 'video', name: clip('demo-bars.mp4'), duration: 3, start: 3, inpoint: 0, outpoint: 3 },
        { type: 'video', name: clip('demo-testcard.mp4'), duration: 3, start: 6, inpoint: 0, outpoint: 3 },
        {
          type: 'template',
          name: 'textBox',
          duration: 3,
          start: 9,
          data: { text: 'Drama is life with the dull bits cut out.', color: '#f2aa4c' },
        },
      ],
      duration: 12,
    }
    const created = await request.post('/project', {
      ...auth(token),
      data: { name: 'Demo reel', logic: {}, fields: [], edl },
    })
    expect(created.status(), await created.text()).toBe(200)
    const project = await created.json()
    made.set(project._id, { name: project.name, owned: true })
    await use({ ...project, edl })
  },

  /**
   * The recipe's page, opened once its project is made, and checked
   * afterwards: every row it shows is the recipe's own.
   */
  authedPage: async ({ page, opened, made, project }, use) => {
    expect(made.has(project._id)).toBe(true)
    await openRecipe(page, made, opened)
    await use(page)
    await everyRowIsItsOwn(page, made)
    // The Deliver panel polls the renders, so a list can still be in flight
    // as the page closes; its answer has nowhere to go and is not a failure.
    await page.unrouteAll({ behavior: 'ignoreErrors' })
  },
})

// Long enough to read what changed, short enough that a full recording is
// still a couple of minutes.
const BEAT = 900

async function beat(page, ms = BEAT) {
  await page.waitForTimeout(ms)
}

// The subtitle file the captions recipe imports.
const RECIPE_SRT = `1
00:00:00,500 --> 00:00:02,600
Read from a subtitle file

2
00:00:03,400 --> 00:00:05,600
and drawn over the picture
`

test.describe('@recipe walkthroughs', () => {
  // Room for the render recipe's render to finish before it is deleted.
  test.describe.configure({ timeout: 150_000 })

  test('recipe: open the editor and look around', async ({ authedPage }) => {
    /**
     * The editor is the first thing the app shows. Three regions, in the order
     * you work: the **viewer** with the output settings beside it, the
     * **transport** that moves the playhead, and the **editor** where the
     * timeline sits with its tools and the media bin beneath.
     */
    await authedPage.goto('/')
    await expect(authedPage.locator('#timeline')).toBeVisible()
    await beat(authedPage)

    await expect(authedPage.locator('section.viewer')).toBeVisible()
    await expect(authedPage.locator('section.transport')).toBeVisible()
    await expect(authedPage.locator('section.editor')).toBeVisible()
    await beat(authedPage)

    // The stage rail names the whole flow without leaving the page.
    for (const stage of ['source', 'edit', 'render', 'deliver']) {
      await authedPage.locator(`#stage-${stage}`).hover()
      await beat(authedPage, 400)
    }
  })

  test('recipe: generate a demo from an empty install', async ({
    page,
    opened,
    made,
    request,
    token,
  }) => {
    /**
     * A first run needs no downloads. The Source stage offers to generate both
     * a project and its media, synthesised locally with ffmpeg's test sources.
     */
    // No project of its own: the Source stage opens with none listed.
    await openRecipe(page, made, opened)
    await page.goto('/#!/?stage=source')
    await expect(page.locator('#panel-source')).toBeVisible()
    await expect(page.locator('.projectchoice')).toHaveCount(0)
    await beat(page)

    // Generated through the API here so the recording shows the result rather
    // than a spinner: the button does the same thing, and demo.spec.js drives
    // it directly.
    await request.post('/demo/media', auth(token))
    const demo = await (await request.post('/demo/project', auth(token))).json()
    // One demo per account. Made now, it is the recipe's to delete; made
    // before, it is shown only while it is the demo as generated, not one
    // renamed into somebody's own project.
    test.skip(
      !demo.created && demo.name !== 'Demo',
      "this account's demo project has been renamed, and would be recorded"
    )
    made.set(demo.id, { name: demo.name, owned: demo.created })

    await page.reload()
    await expect(page.locator('.projectchoice')).toHaveCount(1)
    await beat(page)
    await everyRowIsItsOwn(page, made)
  })

  test('recipe: choose a project and edit its timeline', async ({
    authedPage,
    project,
  }) => {
    /**
     * Choosing a project on the Source stage loads its timeline. The clips are
     * laid out left to right, and each one is as wide as it is long.
     */
    await authedPage.goto('/#!/?stage=source')
    await authedPage
      .locator('.projectpicker')
      .getByRole('button', { name: new RegExp(project.name, 'i') })
      .first()
      .click()
    await beat(authedPage)

    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    await beat(authedPage)

    // Selecting a clip previews it. A template renders a frame; a video clip
    // plays.
    await authedPage.locator('#timeline .clip').first().click()
    await beat(authedPage, 1800)

    await authedPage.locator('#timeline .clip').nth(1).click()
    await beat(authedPage, 1800)
  })

  test('recipe: pick a tool and move the playhead', async ({
    authedPage,
    project,
  }) => {
    /**
     * The tools that change clips sit beside the timeline; the ones that move
     * the playhead sit above it, in the transport.
     */
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    await beat(authedPage)

    for (const tool of ['trim', 'move', 'time']) {
      await authedPage.locator(`#TTools [data-tool="${tool}"]`).click()
      await beat(authedPage, 700)
    }

    for (const control of ['end', 'start', 'forward 5s']) {
      await authedPage.locator(`#PlaybackTools i[title="${control}"]`).click()
      await beat(authedPage, 700)
    }
  })

  test('recipe: render the timeline and deliver the result', async ({
    authedPage,
    project,
  }) => {
    /**
     * The Render stage turns the timeline into a video; the Deliver stage
     * sends it somewhere. Delivery is local by default, so this works on a
     * machine with no cloud account.
     */
    await authedPage.goto(`/#!/?project=${project._id}&stage=render`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    await beat(authedPage)

    await authedPage.locator('#render-width').fill('320')
    await authedPage.locator('#render-height').fill('180')
    await beat(authedPage, 600)

    await authedPage.locator('#queue-render').click()

    // Queuing moves to Deliver, which is where the result appears.
    await expect(authedPage.locator('#panel-deliver')).toBeVisible({
      timeout: 30_000,
    })
    await expect(authedPage.locator('#panel-deliver .renderitem')).toHaveCount(1)
    await beat(authedPage, 2000)
  })

  test('recipe: import captions and show them over the picture', async ({
    authedPage,
    project,
  }) => {
    /**
     * The Captions panel reads a subtitle file and shows what it found before
     * anything is kept. Use them, tick **Draw into renders** and save, and
     * the caption under the playhead is drawn over the picture.
     */
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    await authedPage.locator('#paneltab-captions').click()
    await expect(authedPage.locator('#panel-captions')).toBeVisible()
    await beat(authedPage)

    await authedPage.locator('#captions-file').setInputFiles({
      name: 'film.srt',
      mimeType: 'application/x-subrip',
      buffer: Buffer.from(RECIPE_SRT),
    })
    await expect(authedPage.locator('#captions-review')).toContainText(
      'film.srt: 2 captions'
    )
    await beat(authedPage, 1400)
    await authedPage.locator('#captions-review-replace').click()
    await expect(authedPage.locator('#captions-list .captionrow')).toHaveCount(2)
    await beat(authedPage)

    await authedPage.locator('#caption-enabled').check()
    await authedPage.locator('#captions-save').click()
    await expect(authedPage.locator('#captions-unsaved')).toHaveCount(0)
    await beat(authedPage)

    // On the title, the first caption over the picture; on the colour bars,
    // the second.
    const overlay = authedPage.locator('#caption-overlay')
    await authedPage.locator('#timeline .clip').first().click()
    await expect(overlay).toHaveText('Read from a subtitle file')
    await expect(overlay).toHaveAttribute('data-drawn', 'true')
    await beat(authedPage, 1600)
    await authedPage.locator('#timeline .clip').nth(1).click()
    await expect(overlay).toHaveText('and drawn over the picture')
    await beat(authedPage, 1800)
  })
})

// Narration for the text-editing recipe, `[start, end, text]`: put on through
// the API (the demo media is silent). The second line crosses the 6 s clip cut.
const NARRATION = [
  [0.4, 2.8, 'A video editor that works in the browser.'],
  [4.5, 8.1, 'Every frame you see here is drawn by the server.'],
  [8.8, 11.6, 'The dull bits come out by deleting their words.'],
]

/** The narration's words, `{start, end, text, segment}`. */
const narratedWords = () =>
  NARRATION.flatMap(([start, end, line], segment) => {
    const said = line.split(' ')
    const step = (end - start) / said.length
    return said.map((text, k) => ({
      start: Math.round((start + k * step) * 1000) / 1000,
      end: Math.round((start + (k + 1) * step) * 1000) / 1000,
      text,
      segment,
    }))
  })

test.describe('@recipe editing by text', () => {
  test.describe.configure({ timeout: 150_000 })
  // The docs' screenshot size.
  test.use({ viewport: { width: 1280, height: 800 } })

  test('recipe: cut the video by deleting words from its transcript', async ({
    authedPage,
    project,
    request,
    token,
  }) => {
    /**
     * Drag across "you see here", press Delete: the bars lose their end, the
     * test card its start, and the captions after move up. Save keeps it.
     */
    clear('transcript')
    clear('transcript-cut')
    const res = await request.put(`/project/${project._id}/captions`, {
      ...auth(token),
      data: {
        captions: NARRATION.map(([start, end, text]) => ({ start, end, text })),
        words: narratedWords(),
      },
    })
    expect(res.status(), await res.text()).toBe(200)

    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
    await authedPage.locator('#paneltab-transcript').click()
    const words = authedPage.locator('#transcript-text .word')
    await expect(words).toHaveCount(narratedWords().length)
    await beat(authedPage)

    const [you, here] = [words.nth(10), words.nth(12)]
    await expect(you).toHaveText('you')
    await expect(here).toHaveText('here')
    const from = await you.boundingBox()
    const to = await here.boundingBox()
    await authedPage.mouse.move(from.x + 2, from.y + from.height / 2)
    await authedPage.mouse.down()
    await authedPage.mouse.move(to.x + to.width - 2, to.y + to.height / 2, { steps: 12 })
    await authedPage.mouse.up()
    await expect(authedPage.locator('#transcript-text .word.going')).toHaveText([
      'you',
      'see',
      'here',
    ])
    await beat(authedPage, 1400)
    await save(authedPage, 'transcript')

    await authedPage.keyboard.press('Delete')
    await expect(authedPage.locator('#transcript-text .transcriptpara').nth(1)).toHaveText(
      'Every frame is drawn by the server.'
    )
    await expect(authedPage.locator('#transcript-last')).toContainText('Cut 3 words')
    await beat(authedPage, 1400)
    await save(authedPage, 'transcript-cut')

    await authedPage.locator('#transcript-save').click()
    await expect(authedPage.locator('#transcript-unsaved')).toHaveCount(0)
    await beat(authedPage)
  })
})
