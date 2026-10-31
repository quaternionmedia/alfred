/**
 * The timeline saves itself.
 *
 * # Recipe: saving
 *
 * The timeline has no Save button. A moment after it stops changing (a clip
 * added, moved, trimmed or cut, a title retyped, words cut from the
 * transcript) it is saved to the project, with the captions and words a cut
 * moved. The indicator beside the timeline says **Saving…**, then **Saved**.
 * When a save fails it says **Not saved**, with the reason on hover and a
 * **Retry**; the edits are kept in the tab meanwhile, and it tries again by
 * itself. Opening another project saves the one being left, and transcribing
 * saves first, so the audio engine hears what is on screen. Captions typed or
 * styled by hand keep their own Save.
 */

const { test, expect, expectSaved, addTemplate, MEDIA_PROJECT } = require('./fixtures')

const state = page => page.locator('#save-state')
const clips = page => page.locator('#timeline .clip')

/** A project of the test's own, empty; deleted after. */
async function ownProject(request, token, name) {
  const created = await request.post('/project', {
    headers: { Authorization: token },
    data: { name: `${name} ${test.info().workerIndex}-${test.info().repeatEachIndex}`, logic: {}, edl: { clips: [] } },
  })
  expect(created.status(), await created.text()).toBeLessThan(400)
  return created.json()
}

/** How many clips the server holds for `project`. */
const savedClips = async (request, token, project) => {
  const saved = await (await request.get(`/project/${project._id}`, { headers: { Authorization: token } })).json()
  return ((saved.edl || {}).clips || []).length
}

test.describe('the timeline saves itself', () => {
  test.use({ saves: 'real' })

  test('an edit is saved a moment later', async ({ authedPage, request, token }) => {
    const project = await ownProject(request, token, 'autosave')
    try {
      await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
      await expect(state(authedPage)).toHaveAttribute('data-state', 'saved')
      await addTemplate(authedPage, 'title')
      await expect(clips(authedPage)).toHaveCount(1)
      await expectSaved(authedPage)
      await expect(state(authedPage)).toHaveText(/Saved/)
      await expect.poll(() => savedClips(request, token, project)).toBe(1)
    } finally {
      await request.delete(`/project/${project._id}`, { headers: { Authorization: token } })
    }
  })

  test('opening another project saves the one being left', async ({ authedPage, request, token }) => {
    // The project changes at once, inside the moment the save waits for.
    const left = await ownProject(request, token, 'left')
    const next = await ownProject(request, token, 'next')
    try {
      await authedPage.goto(`/#!/?project=${left._id}&stage=source`)
      await addTemplate(authedPage, 'title')
      await expect(clips(authedPage)).toHaveCount(1)
      await authedPage.locator('.projectchoice', { hasText: next.name }).click()
      await expect(authedPage).toHaveURL(new RegExp(`project=${next._id}`))
      await expect.poll(() => savedClips(request, token, left)).toBe(1)
      expect(await savedClips(request, token, next)).toBe(0)
    } finally {
      for (const p of [left, next]) {
        await request.delete(`/project/${p._id}`, { headers: { Authorization: token } })
      }
    }
  })
})

test.describe('a save that fails', () => {
  test.use({ saves: 'refused' })

  test('says so, keeps the edit, and saves once it can', async ({ authedPage, request, token }) => {
    const projects = await (await request.get('/project', { headers: { Authorization: token } })).json()
    const project = projects.find(p => p.name === MEDIA_PROJECT)
    await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
    await expect(clips(authedPage)).toHaveCount(project.edl.clips.length)

    await addTemplate(authedPage, 'title')
    await expect(state(authedPage)).toHaveAttribute('data-state', 'failed', { timeout: 15000 })
    await expect(state(authedPage)).toHaveText(/Not saved/)
    await expect(state(authedPage)).toHaveAttribute('title', /refused by the test/)

    // The server answers again (a later route wins); Retry saves.
    await authedPage.route(
      url => url.pathname === `/project/${project._id}/timeline`,
      route => route.fulfill({ json: {} })
    )
    await authedPage.locator('#save-state-retry').click()
    await expectSaved(authedPage)
  })
})
