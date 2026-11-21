/**
 * The Sculpt stage: the recipes on offer with their knobs, the run that cuts a
 * project into drafts, and the drafts it leaves, each a project on Edit.
 *
 * # Recipe: cut a long recording into drafts by recipe
 *
 * Tick a recipe, set its knobs, press Sculpt; the drafts appear under Drafts
 * and under the project on Source. The run is the worker's, so the test that
 * runs one needs the stack's worker; the rest needs the api alone.
 * Desktop and phone.
 */

const { test, expect } = require('./fixtures')

// These check what reaches the server.
test.use({ saves: 'real' })

const auth = token => ({ headers: { Authorization: token } })

/** Six seconds of colour, for words put on through the API. */
const COLOUR = {
  clips: [
    { type: 'template', name: 'makeColor', duration: 3, start: 0, fadeIn: 0, fadeOut: 0, data: { color: '#203040' } },
    { type: 'template', name: 'makeColor', duration: 3, start: 3, fadeIn: 0, fadeOut: 0, data: { color: '#402030' } },
  ],
  duration: 6,
}

/** One word a second from `start`, in `segment`. */
const spoken = (start, text, segment) =>
  text.split(' ').map((word, i) => ({ start: start + i, end: start + i + 1, text: word, segment }))

// Two stretches of speech, a pause of a second and a half between them.
const WORDS = [...spoken(0, 'One two.', 0), ...spoken(3.5, 'Four five.', 1)]
const CAPTIONS = [
  { start: 0, end: 2, text: 'One two.' },
  { start: 3.5, end: 5.5, text: 'Four five.' },
]

async function withProject(request, token, edl, use) {
  const created = await request.post('/project', {
    ...auth(token),
    data: {
      name: `sculpt ${test.info().title.slice(0, 40)} ${test.info().workerIndex}-${Date.now()}`,
      logic: {},
      edl,
    },
  })
  expect(created.status(), await created.text()).toBe(200)
  const project = await created.json()
  try {
    await use(project)
  } finally {
    // The drafts first: a source gone leaves them ownerless in the list.
    const drafts = await request.get(`/project/${project._id}/drafts`, auth(token))
    if (drafts.ok()) {
      const ids = (await drafts.json()).drafts.map(d => d.id)
      if (ids.length) {
        await request.delete(`/project/${project._id}/drafts`, { ...auth(token), data: { drafts: ids } })
      }
    }
    await request.delete(`/project/${project._id}`, auth(token))
  }
}

async function giveWords(request, token, project) {
  const res = await request.put(`/project/${project._id}/captions`, {
    ...auth(token),
    data: { captions: CAPTIONS, words: WORDS },
  })
  expect(res.status(), await res.text()).toBe(200)
}

const phone = () => test.info().project.name === 'phone'

/** The Sculpt stage open on `project`, its Recipes panel showing. */
async function openSculpt(page, project) {
  await page.goto(`/#!/?project=${project._id}&stage=sculpt`)
  await expect(page.locator('#stage-sculpt')).toHaveClass(/active/)
  // On a phone the switch keeps the panel last chosen.
  if (phone()) await page.locator('#flowswitch-recipes').click()
  await expect(page.locator('#panel-recipes')).toBeVisible()
}

/** The Drafts panel: a tab on the desktop, the switch's second choice on a phone. */
async function showDrafts(page) {
  if (phone()) await page.locator('#flowswitch-drafts').click()
  else await page.locator('.lm_tab[data-panel="drafts"]').click()
  await expect(page.locator('#panel-drafts')).toBeVisible()
}

test.describe('the Sculpt stage', () => {
  test('sits between Source and Edit, and lists the built-in recipes with their knobs', async ({
    authedPage,
  }) => {
    await authedPage.goto('/#!/?stage=sculpt')
    await expect(authedPage.locator('#stage-sculpt')).toHaveClass(/active/)
    const labels = await authedPage.locator('.stagerail .stage .stagelabel').allInnerTexts()
    expect(labels.indexOf('Sculpt')).toBe(labels.indexOf('Source') + 1)
    expect(labels.indexOf('Edit')).toBe(labels.indexOf('Sculpt') + 1)

    await expect(authedPage.locator('#panel-recipes .recipe').first()).toBeVisible()
    // Highlights first, ticked, with the advice's first values as its knobs.
    await expect(authedPage.locator('#panel-recipes .recipe').first()).toHaveAttribute(
      'data-recipe',
      'highlights'
    )
    await expect(authedPage.locator('#recipe-highlights')).toBeChecked()
    await expect(authedPage.locator('#recipe-highlights-count')).toHaveValue('25')
    // Without a project there is nothing to sculpt.
    await expect(authedPage.locator('#sculpt-run')).toBeDisabled()
  })

  test('a project without a transcript is told to transcribe first', async ({
    authedPage,
    request,
    token,
  }) => {
    await withProject(request, token, COLOUR, async project => {
      await openSculpt(authedPage, project)
      await expect(authedPage.locator('#sculpt-blocker')).toContainText('Transcribe the timeline first')
      await expect(authedPage.locator('#sculpt-run')).toBeDisabled()
      await expect(authedPage.locator('#next-step')).toContainText('Transcribe the timeline first')
      await showDrafts(authedPage)
      await expect(authedPage.locator('#panel-drafts')).toContainText('No drafts yet')
    })
  })

  test('a transcribed project is offered Sculpt from Source', async ({ authedPage, request, token }) => {
    await withProject(request, token, COLOUR, async project => {
      await giveWords(request, token, project)
      await authedPage.goto(`/#!/?project=${project._id}&stage=source`)
      await expect(authedPage.locator('#next-step-go')).toHaveText(/Next: Sculpt/)
      await authedPage.locator('#next-step-go').click()
      await expect(authedPage.locator('#stage-sculpt')).toHaveClass(/active/)
      await expect(authedPage.locator('#sculpt-run')).toBeEnabled()
    })
  })

  test('@slow a run of the chapters recipe leaves a draft per chapter, listed, opened and dropped', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Two stretches of speech with a pause between them: the chapters recipe,
     * its pause set to one second, leaves two drafts, each a project carrying
     * its source, grouped under the project on Source; the second is dropped
     * from the Drafts panel with its cue.
     */
    test.setTimeout(120_000)
    await withProject(request, token, COLOUR, async project => {
      await giveWords(request, token, project)
      await openSculpt(authedPage, project)
      // Highlights off, chapters on, with its pause under the gap.
      await authedPage.locator('#recipe-highlights').uncheck()
      await authedPage.locator('#recipe-chapters').check()
      await authedPage.locator('#recipe-chapters-pause').fill('1')
      await authedPage.locator('#sculpt-run').click()
      await expect(authedPage.locator('#sculpt-job')).toHaveAttribute('data-state', 'done', {
        timeout: 90_000,
      })
      await expect(authedPage.locator('#sculpt-job')).toContainText('2 drafts made')

      await showDrafts(authedPage)
      const drafts = authedPage.locator('#panel-drafts .draft')
      await expect(drafts).toHaveCount(2)
      await expect(drafts.first()).toContainText('Chapters 1')
      await expect(drafts.first()).toContainText('2 s')

      // Each is a project of the owner's carrying its source, with its words.
      const listed = await request.get(`/project/${project._id}/drafts`, auth(token))
      const made = (await listed.json()).drafts
      expect(made.map(d => d.source.spans)).toEqual([[[0, 2]], [[3.5, 5.5]]])
      const words = await request.get(`/project/${made[1].id}/captions/words`, auth(token))
      expect((await words.json()).words.map(w => [w.text, w.start])).toEqual([
        ['Four', 0],
        ['five.', 1],
      ])
      // A cue per draft on the source.
      const cues = await request.get(`/project/${project._id}/cues`, auth(token))
      expect((await cues.json()).cues.filter(c => c.kind === 'draft')).toHaveLength(2)

      // Opening one goes to Edit, with its clips on the timeline.
      await drafts.first().locator('.draftopen').click()
      await expect(authedPage).toHaveURL(new RegExp(`project=${made[0].id}`))
      await expect(authedPage.locator('#stage-edit')).toHaveClass(/active/)
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)

      // Back on the source, the second is dropped with its cue.
      await openSculpt(authedPage, project)
      await showDrafts(authedPage)
      await authedPage.locator('#panel-drafts .draft').nth(1).locator('.draftmark').check()
      await authedPage.locator('#drafts-drop').click()
      await expect(authedPage.locator('#panel-drafts .draft')).toHaveCount(1)
      const after = await request.get(`/project/${project._id}/cues`, auth(token))
      expect((await after.json()).cues.filter(c => c.kind === 'draft')).toHaveLength(1)

      // On Source, the draft sits under the project it came from.
      await authedPage.goto(`/#!/?project=${project._id}&stage=source`)
      const group = authedPage.locator(`.draftgroup[data-source="${project._id}"]`)
      await expect(group).toContainText('1 draft')
    })
  })
})
