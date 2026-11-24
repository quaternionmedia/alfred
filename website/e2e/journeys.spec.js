/**
 * The editor says what to do next.
 *
 * # Recipe: finding the way through
 *
 * A line under the stage rail says where you are and what comes next, with a
 * button to that stage and a **How?** link to the journey it belongs to
 * (docs/journeys.md). With no project open, Source is marked as the place to
 * start, and **New project** there starts an empty one. The viewer's frame
 * menus are named for what they set, and the Render stage says where the size
 * it offers came from.
 */

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

const line = page => page.locator('#next-step')

async function mediaProject(request, token) {
  const projects = await (await request.get('/project', { headers: { Authorization: token } })).json()
  const project = projects.find(p => p.name === MEDIA_PROJECT)
  expect(project, `${MEDIA_PROJECT} is missing; global-setup.js creates it`).toBeTruthy()
  return project
}

test.describe('the line under the rail', () => {
  test('a first visit is told where to start', async ({ authedPage }) => {
    await authedPage.goto('/')
    await expect(line(authedPage)).toContainText('Start here: choose a project')
    await expect(authedPage.locator('#stage-source')).toHaveClass(/starthere/)
    await authedPage.locator('#next-step-go').click()
    await expect(authedPage.locator('#stage-source')).toHaveClass(/active/)
    await expect(line(authedPage)).toContainText('Start here: choose a project, or generate a demo one')
  })

  test('each stage says what comes next, and goes there', async ({ authedPage, request, token }) => {
    /**
     * Edit with clips on the timeline points on to Render; Render says what
     * to press. Once a project is open, Source is no longer marked.
     */
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
    await expect(line(authedPage)).toContainText('Arrange, trim and title the clips. It saves itself.')
    await expect(authedPage.locator('#stage-source')).not.toHaveClass(/starthere/)
    await expect(authedPage.locator('#next-step-go')).toHaveText(/Next: Render/)

    await authedPage.locator('#next-step-go').click()
    await expect(authedPage.locator('#stage-render')).toHaveClass(/active/)
    await expect(line(authedPage)).toContainText('Choose a size, then Queue render.')
    await expect(authedPage.locator('#next-step-go')).toHaveCount(0)
  })

  test('How? opens the journey for the step', async ({ authedPage, request, token }) => {
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    const how = authedPage.locator('#next-step-how')
    await expect(how).toHaveAttribute('href', '/docs/journeys/#arrange-and-title')
    await expect(how).toHaveAttribute('target', '_blank')
  })
})

test.describe('a project of your own', () => {
  test('New project starts an empty one and opens it on Source', async ({ authedPage, request, token }) => {
    const name = `new project ${test.info().workerIndex}-${test.info().repeatEachIndex}`
    await authedPage.goto('/#!/?stage=source')
    await authedPage.locator('#project-new').click()
    await authedPage.locator('#project-new-name').fill(name)
    await authedPage.locator('#project-new-create').click()
    await expect(authedPage).toHaveURL(/project=/)
    const id = new URLSearchParams(new URL(authedPage.url()).hash.split('?')[1]).get('project')
    try {
      await expect(line(authedPage)).toContainText(`${name} is open. Add material or a template.`)
      await expect(authedPage.locator('.projectchoice', { hasText: name })).toBeVisible()
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(0)
      const saved = await (await request.get(`/project/${id}`, { headers: { Authorization: token } })).json()
      expect(saved.name).toBe(name)
      expect(saved.edl.clips).toEqual([])
    } finally {
      await request.delete(`/project/${id}`, { headers: { Authorization: token } })
    }
  })
})

test.describe('settings that say what they set', () => {
  test("the frame menus are named, and Render says where its size came from", async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * 16:9 and 1080p beside the viewer set the frame's shape and size: the
     * picture's, and the size a project's first render starts at. After a
     * render, Render offers the size the project last rendered at.
     */
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=render`)
    await expect(authedPage.locator('.viewersettingslabel')).toHaveText('Frame')
    await expect(authedPage.locator('#aspect')).toHaveAttribute('aria-label', 'Frame shape')
    await expect(authedPage.locator('#resolution')).toHaveAttribute('aria-label', 'Frame size')
    await expect(authedPage.locator('#render-size-from')).toHaveText(
      /^(The size this project last rendered at\.|The viewer's frame: \d+:\d+ at \d+p\.)$/
    )
  })

  test('the footer links read on the dark bar', async ({ authedPage }) => {
    await authedPage.goto('/')
    const colour = await authedPage
      .locator('footer a.docLink')
      .first()
      .evaluate(a => getComputedStyle(a).color)
    // Not the browser's link blue.
    expect(colour).not.toBe('rgb(0, 0, 238)')
    expect(colour).toBe('rgb(158, 197, 255)')
  })
})
