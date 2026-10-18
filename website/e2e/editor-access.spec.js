/**
 * The editor from the keyboard, and read as text.
 *
 * # Recipe: choosing a timeline tool without a mouse
 *
 * The tools beside the timeline are buttons. Tab to one and press Enter or
 * Space to choose it; the chosen tool is announced as pressed. They were
 * icons that announced themselves as buttons and could not be reached: no tab
 * stop, and neither key did anything. Space is still play and pause whenever
 * the keyboard has not moved to a button -- choosing a tool with the mouse
 * does not take it away.
 */

const { test, expect, MEDIA_PROJECT } = require('./fixtures')

async function mediaProject(request, token) {
  const projects = await (
    await request.get('/project', { headers: { Authorization: token } })
  ).json()
  const project = projects.find(p => p.name === MEDIA_PROJECT)
  expect(project, `${MEDIA_PROJECT} is missing; global-setup.js creates it`).toBeTruthy()
  return project
}

const tool = (page, id) => page.locator(`#TTools [data-tool="${id}"]`)

test.describe('the timeline tools from the keyboard', () => {
  test('every tool is a button with a name', async ({ authedPage }) => {
    /**
     * Named for the tool, not for its icon: the icon's ligature text --
     * "content_cut" -- is hidden from assistive technology.
     */
    await authedPage.goto('/#!/?stage=edit')
    for (const [id, name] of [
      ['time', 'Time'],
      ['trim', 'Trim'],
      ['move', 'Move'],
      ['cut', 'Cut'],
    ]) {
      await expect(tool(authedPage, id)).toHaveJSProperty('tagName', 'BUTTON')
      await expect(
        authedPage.locator('#TTools').getByRole('button', { name, exact: true })
      ).toHaveAttribute('data-tool', id)
    }
  })

  test('Tab reaches a tool, and Enter or Space chooses it', async ({ authedPage }) => {
    await authedPage.goto('/#!/?stage=edit')
    await expect(tool(authedPage, 'time')).toHaveAttribute('aria-pressed', 'true')

    // From the first tool, the next Tab stop is the second.
    await tool(authedPage, 'time').focus()
    await authedPage.keyboard.press('Tab')
    await expect(tool(authedPage, 'trim')).toBeFocused()
    await authedPage.keyboard.press('Space')
    await expect(tool(authedPage, 'trim')).toHaveAttribute('aria-pressed', 'true')
    await expect(tool(authedPage, 'time')).toHaveAttribute('aria-pressed', 'false')

    await authedPage.keyboard.press('Tab')
    await expect(tool(authedPage, 'move')).toBeFocused()
    await authedPage.keyboard.press('Enter')
    await expect(tool(authedPage, 'move')).toHaveAttribute('aria-pressed', 'true')
    await expect(tool(authedPage, 'trim')).toHaveAttribute('aria-pressed', 'false')
  })

  test('Space pressing a tool does not also start playback', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The page's own Space handler cancelled the press and played the
     * timeline instead, so a keyboard could not have chosen a tool even had
     * it reached one.
     */
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)

    await tool(authedPage, 'time').focus()
    await authedPage.keyboard.press('Tab')
    await authedPage.keyboard.press('Space')
    await expect(tool(authedPage, 'trim')).toHaveAttribute('aria-pressed', 'true')
    await expect(authedPage.locator('#playpause')).toHaveText('play_arrow')
  })

  test('after choosing a tool with the mouse, Space still plays', async ({
    authedPage,
    request,
    token,
  }) => {
    const project = await mediaProject(request, token)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)

    await tool(authedPage, 'trim').click()
    await expect(tool(authedPage, 'trim')).toHaveAttribute('aria-pressed', 'true')
    await authedPage.keyboard.press('Space')
    await expect(authedPage.locator('#playpause')).toHaveText('pause')
    await authedPage.keyboard.press('Space')
    await expect(authedPage.locator('#playpause')).toHaveText('play_arrow')
    // And the tool is as it was chosen.
    await expect(tool(authedPage, 'trim')).toHaveAttribute('aria-pressed', 'true')
  })
})

test.describe('the footer', () => {
  test('its links are separated, to the eye and in the text', async ({ authedPage }) => {
    /**
     * Two bare anchors side by side read "User documentationAPI reference".
     */
    await authedPage.goto('/')
    const links = authedPage.locator('footer nav.doclinks')
    await expect(links).toHaveText('User documentation · API reference')
    await expect(authedPage.locator('footer')).not.toContainText('documentationAPI')

    // And apart on screen, not merely in the markup.
    const [first, second] = await authedPage
      .locator('footer a.docLink')
      .evaluateAll(nodes => nodes.map(n => n.getBoundingClientRect()))
    expect(second.left - first.right).toBeGreaterThan(4)
  })
})
