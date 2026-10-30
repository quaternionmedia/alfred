/**
 * Each step of making a video, from the editor opening to the render
 * delivered, saved as `docs/assets/screens/guide/<step>.png` for
 * docs/guide.md. One walk (guide.js) on an empty project; the sound is the
 * stub engine's tones unless `E2E_SPEECH` names a file of speech. @screens,
 * docs project.
 */

const { test, login } = require('./fixtures')
const { DESKTOP, clear, narrow, save, screenFile } = require('./screens-kit')
const guide = require('./guide')

let project

test.use({ video: 'off' })

test.describe('@screens', () => {
  test.describe.configure({ timeout: 360_000 })
  test.use({ viewport: DESKTOP })

  test.afterAll(async ({ playwright, token }, info) => {
    const api = await playwright.request.newContext({ baseURL: info.project.use.baseURL })
    try {
      if (project) await guide.removeProject(api, token, project)
    } finally {
      await api.dispose()
    }
  })

  test('screen: each step of making a video', async ({ page, request, token }) => {
    /** Nine steps in the guide; the first, starting the family, is a command. */
    // Skipped, the pictures stay: they were not retaken, not broken.
    const why = await guide.cannotWalk(request, token)
    test.skip(Boolean(why), why)
    for (const step of guide.STEPS) clear(screenFile('guide', step))
    project = await guide.emptyProject(request, token)

    await narrow(page, [project], guide.LIBRARY)
    await login(page)
    await guide.walk(
      page,
      { project, request, token },
      { shown: step => save(page, screenFile('guide', step)) }
    )
  })
})
