/**
 * Who spoke, and what about: each paragraph of the transcript carries a
 * speaker a person names, saved with the words, and the panel shows what the
 * language engine reads in the words as they stand.
 *
 * The naming needs the api alone; the reading needs a language engine beside
 * the server, and the test that reads skips without one.
 * Desktop and phone.
 */

const { test, expect, expectSaved } = require('./fixtures')

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

const spoken = (start, text, segment) =>
  text.split(' ').map((word, i) => ({ start: start + i, end: start + i + 1, text: word, segment }))

const WORDS = [...spoken(0, 'One two three.', 0), ...spoken(3, 'Four five six.', 1)]
const CAPTIONS = [
  { start: 0, end: 3, text: 'One two three.' },
  { start: 3, end: 6, text: 'Four five six.' },
]

async function withProject(request, token, use) {
  const created = await request.post('/project', {
    ...auth(token),
    data: {
      name: `conversation ${test.info().title.slice(0, 40)} ${test.info().workerIndex}-${Date.now()}`,
      logic: {},
      edl: COLOUR,
    },
  })
  expect(created.status(), await created.text()).toBe(200)
  const project = await created.json()
  const given = await request.put(`/project/${project._id}/captions`, {
    ...auth(token),
    data: { captions: CAPTIONS, words: WORDS },
  })
  expect(given.status(), await given.text()).toBe(200)
  try {
    await use(project)
  } finally {
    await request.delete(`/project/${project._id}`, auth(token))
  }
}

const phone = () => test.info().project.name === 'phone'

/** The Transcript panel, on the Edit stage already open: a tab on the desktop, the switch on a phone. */
async function showTranscript(page) {
  await expect(page.locator('#timeline .clip').first()).toBeVisible()
  if (phone()) await page.locator('#flowswitch-transcript').click()
  else await page.locator('.lm_tab[data-panel="transcript"]').click()
  await expect(page.locator('#transcript-text .word')).toHaveCount(6)
}

/** The Transcript panel, on Edit, with its words. */
async function openTranscript(page, project) {
  await page.goto(`/#!/?project=${project._id}&stage=edit`)
  await showTranscript(page)
}

async function wordsOf(request, token, project) {
  const res = await request.get(`/project/${project._id}/captions/words`, auth(token))
  expect(res.status()).toBe(200)
  return (await res.json()).words
}

test.describe('who spoke', () => {
  test('a paragraph is named, every word of it carries the name, and the save keeps it', async ({
    authedPage,
    request,
    token,
  }) => {
    await withProject(request, token, async project => {
      await openTranscript(authedPage, project)
      const labels = authedPage.locator('#transcript-text .speakerlabel')
      await expect(labels).toHaveCount(2)
      await expect(labels.first()).toHaveText('Unknown')

      authedPage.once('dialog', dialog => dialog.accept('Alice'))
      await labels.first().click()
      await expect(labels.first()).toHaveText('Alice')
      await expect(labels.nth(1)).toHaveText('Unknown')
      await expectSaved(authedPage, { id: 'transcript-save-state' })

      const saved = await wordsOf(request, token, project)
      expect(saved.map(w => w.speaker || null)).toEqual(['Alice', 'Alice', 'Alice', null, null, null])
      // The name comes back with the words.
      await authedPage.reload()
      await showTranscript(authedPage)
      await expect(authedPage.locator('#transcript-text .speakerlabel').first()).toHaveText('Alice')
    })
  })

  test('without a language engine the panel says so, and the labels work all the same', async ({
    authedPage,
    request,
    token,
  }) => {
    const health = await (await request.get('/health', auth(token))).json()
    test.skip(health.language_engine && health.language_engine.configured, 'a language engine is configured')
    await withProject(request, token, async project => {
      await openTranscript(authedPage, project)
      await expect(authedPage.locator('#transcript-reading')).toHaveAttribute('data-state', 'no-engine')
      await expect(authedPage.locator('#transcript-reading')).toContainText('ALFRED_LANGUAGE_ENGINE_URL')
      await expect(authedPage.locator('#transcript-text .speakerlabel')).toHaveCount(2)
    })
  })

  test('@slow with a language engine the reading names the speakers and follows a change', async ({
    authedPage,
    request,
    token,
  }) => {
    const health = await (await request.get('/health', auth(token))).json()
    test.skip(!(health.language_engine && health.language_engine.ok), 'no language engine answers')
    test.setTimeout(120_000)
    await withProject(request, token, async project => {
      await openTranscript(authedPage, project)
      const reading = authedPage.locator('#transcript-reading')
      await expect(reading).toHaveAttribute('data-state', 'read', { timeout: 60_000 })
      await expect(reading).toContainText('Unknown (2)')

      authedPage.once('dialog', dialog => dialog.accept('Bob'))
      await authedPage.locator('#transcript-text .speakerlabel').nth(1).click()
      await expect(reading).toContainText('Bob (1)', { timeout: 60_000 })
      await expect(reading).toContainText('Unknown (1)')

      // The API reads the stored words the same way.
      await expectSaved(authedPage, { id: 'transcript-save-state' })
      const res = await request.get(`/project/${project._id}/conversation`, auth(token))
      expect(res.status(), await res.text()).toBe(200)
      const body = await res.json()
      expect(Object.keys(body.speakers).sort()).toEqual(['Bob', 'Unknown'])
      expect(body.lines.map(l => l.speaker)).toEqual(['Unknown', 'Bob'])
    })
  })
})
