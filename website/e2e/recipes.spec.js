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

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

// Long enough to read what changed, short enough that a full recording is
// still a couple of minutes.
const BEAT = 900

async function beat(page, ms = BEAT) {
  await page.waitForTimeout(ms)
}

test.describe('@recipe walkthroughs', () => {
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
    authedPage,
    request,
    token,
  }) => {
    /**
     * A first run needs no downloads. The Source stage offers to generate both
     * a project and its media, synthesised locally with ffmpeg's test sources.
     */
    await authedPage.goto('/#!/?stage=source')
    await expect(authedPage.locator('#panel-source')).toBeVisible()
    await beat(authedPage)

    // Generated through the API here so the recording shows the result rather
    // than a spinner: the button does the same thing, and demo.spec.js drives
    // it directly.
    await request.post('/demo/media', { headers: { Authorization: token } })
    await request.post('/demo/project', { headers: { Authorization: token } })

    await authedPage.reload()
    await expect(authedPage.locator('.projectchoice').first()).toBeVisible()
    await beat(authedPage)
  })

  test('recipe: choose a project and edit its timeline', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Choosing a project on the Source stage loads its timeline. The clips are
     * laid out left to right, and each one is as wide as it is long.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const project = projects.find(p => p.name === MEDIA_PROJECT)
    test.skip(!project, 'the media fixture is not present')

    await authedPage.goto('/#!/?stage=source')
    await authedPage
      .getByRole('button', { name: new RegExp(MEDIA_PROJECT, 'i') })
      .first()
      .click()
    await beat(authedPage)

    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    await beat(authedPage)

    // Selecting a clip previews it. A video clip plays; a template renders a
    // frame.
    await authedPage.locator('#timeline .clip').first().click()
    await beat(authedPage, 1800)

    await authedPage.locator('#timeline .clip').nth(1).click()
    await beat(authedPage, 1800)
  })

  test('recipe: pick a tool and move the playhead', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The tools that change clips sit beside the timeline; the ones that move
     * the playhead sit above it, in the transport.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const project = projects.find(p => p.name === MEDIA_PROJECT)
    test.skip(!project, 'the media fixture is not present')

    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      project.edl.clips.length
    )
    await beat(authedPage)

    for (const tool of ['trim', 'move', 'time selector']) {
      await authedPage.locator(`#TTools i[title="${tool}"]`).click()
      await beat(authedPage, 700)
    }

    for (const control of ['end', 'start', 'forward 5s']) {
      await authedPage.locator(`#PlaybackTools i[title="${control}"]`).click()
      await beat(authedPage, 700)
    }
  })

  test('recipe: render the timeline and deliver the result', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The Render stage turns the timeline into a video; the Deliver stage
     * sends it somewhere. Delivery is local by default, so this works on a
     * machine with no cloud account.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const project = projects.find(p => p.name === MEDIA_PROJECT)
    test.skip(!project, 'the media fixture is not present')

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
    await beat(authedPage, 2000)
  })
})
