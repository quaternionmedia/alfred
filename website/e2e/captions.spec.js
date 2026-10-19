/**
 * Captions: typed, imported, transcribed, and drawn into renders.
 *
 * A project's captions are text and the stretch of the timeline it is shown
 * for. The Captions panel -- on a wide screen a tab in the workspace, beside
 * Render and Deliver; on a phone the Edit stage's panel, above the viewer --
 * edits them by hand, reads them from a SubRip, WebVTT or JSON file -- the
 * server reads it, the panel shows what it found, and saving keeps it -- or
 * has the timeline's own sound transcribed by the server's audio engine. The
 * caption under the playhead shows over the viewer; renders carry the
 * captions once the project's style says to draw them, which it does not
 * until someone ticks the box.
 *
 * This stack's audio engine is a stub speaking joe's media API (see
 * test_e2e.yml): it "hears" a segment wherever there is sound. The specs that
 * transcribe through it run the real worker and the real mix, and wait for
 * them, so they are tagged @slow.
 */

const { test, expect } = require('./fixtures')

// Written into the library by the stub engine when the stack starts: four
// seconds holding tone from 0.5 to 1.5 and from 2.0 to 3.2.
const FIXTURE = 'videos/e2e-speech.wav'

const SRT = `1
00:00:00,500 --> 00:00:02,000
Said first

2
00:00:02,500 --> 00:00:04,000
<i>Said</i> second
`

const VTT = '﻿WEBVTT\r\n\r\nNOTE from another tool\r\n\r\n00:05.000 --> 00:06.500 align:start\r\nAnd a third\r\n'

const auth = token => ({ headers: { Authorization: token } })

/** A project of the caller's own for one test, removed after it. */
async function withProject(request, token, fields, use) {
  const created = await request.post('/project', {
    ...auth(token),
    data: {
      name: `captions ${test.info().title.slice(0, 40)} ${test.info().workerIndex}-${Date.now()}`,
      logic: {},
      edl: {
        clips: [
          {
            type: 'template',
            name: 'makeColor',
            duration: 6.0,
            start: 0,
            fadeIn: 0,
            fadeOut: 0,
            data: { color: '#203040' },
          },
        ],
      },
      ...fields,
    },
  })
  expect(created.status(), await created.text()).toBe(200)
  const project = await created.json()
  try {
    await use(project)
  } finally {
    await request.delete(`/project/${project._id}`, auth(token))
  }
}

async function captionsOf(request, token, project) {
  const res = await request.get(`/project/${project._id}/captions`, auth(token))
  expect(res.status()).toBe(200)
  return res.json()
}

async function saveCaptions(request, token, project, body) {
  const res = await request.put(`/project/${project._id}/captions`, {
    ...auth(token),
    data: body,
  })
  expect(res.status(), await res.text()).toBe(200)
  return res.json()
}

/** Bring the Captions panel into view, in either layout.
 *
 * On a wide screen it is a workspace tab beside Render and Deliver, mounted
 * only while shown, so its tab is chosen; on a phone it is part of the Edit
 * stage already. The timeline is in both layouts, so waiting for it first
 * means the workspace has been built before its tabs are looked for.
 */
async function showCaptions(page) {
  await expect(page.locator('#timeline .clip').first()).toBeVisible()
  const tab = page.locator('#paneltab-captions')
  if (await tab.count()) await tab.click()
  await expect(page.locator('#panel-captions')).toBeVisible()
}

/** Open the project on the Edit stage, with the Captions panel in view. */
async function openCaptions(page, project) {
  await page.goto(`/#!/?project=${project._id}&stage=edit`)
  await showCaptions(page)
  await expect(page.locator('#caption-add')).toBeEnabled()
}

const rows = page => page.locator('#captions-list .captionrow')

/**
 * Whether the stack's audio engine can be asked, for the specs that need one.
 *
 * Skips where there is none -- a development stack without
 * ALFRED_AUDIO_ENGINE_URL -- and where the vendored vox is one without a
 * media client. Any other way of not answering fails: the engine was
 * promised.
 */
async function needEngine(request, token) {
  const health = await (await request.get('/health', auth(token))).json()
  const engine = health.audio_engine || {}
  test.skip(!engine.configured, 'no audio engine is configured on this stack')
  test.skip(
    /vox\.media/.test(engine.detail || ''),
    `the vendored vox has no media client: ${engine.detail}`
  )
  expect(engine.ok, engine.detail).toBe(true)
  return engine
}

test.describe('captions by hand', () => {
  test('captions are typed, kept in order, and saved', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * # Recipe: caption a timeline by hand
     *
     * Add a caption at the playhead, type what is said, set when it starts
     * and ends -- in seconds, or from the playhead -- and save. The list
     * keeps itself in order of when captions start.
     */
    await withProject(request, token, {}, async project => {
      await openCaptions(authedPage, project)
      await expect(authedPage.locator('#captions-empty')).toBeVisible()

      await authedPage.locator('#caption-add').click()
      const later = rows(authedPage).first()
      await later.locator('.caption-text').fill('Said later')
      await later.locator('.caption-start').fill('3')
      await later.locator('.caption-end').fill('4.5')
      await later.locator('.caption-end').blur()

      await authedPage.locator('#caption-add').click()
      await expect(rows(authedPage)).toHaveCount(2)
      // The new one, at the playhead (0), sorts first.
      await rows(authedPage).first().locator('.caption-text').fill('Said first')

      await expect(authedPage.locator('#captions-unsaved')).toBeVisible()
      await authedPage.locator('#captions-save').click()
      await expect(authedPage.locator('#captions-unsaved')).toHaveCount(0)

      const saved = await captionsOf(request, token, project)
      expect(saved.captions).toEqual([
        { start: 0, end: 2, text: 'Said first' },
        { start: 3, end: 4.5, text: 'Said later' },
      ])

      await authedPage.reload()
      await showCaptions(authedPage)
      await expect(rows(authedPage)).toHaveCount(2)
      await expect(rows(authedPage).first().locator('.caption-text')).toHaveValue(
        'Said first'
      )
    })
  })

  test('a caption that cannot be shown says why, and is not saved', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * A caption with no text, or one that ends before it starts, is marked
     * with the reason, and Save waits until it is fixed.
     */
    await withProject(request, token, {}, async project => {
      await openCaptions(authedPage, project)
      await authedPage.locator('#caption-add').click()
      const row = rows(authedPage).first()
      await expect(row.locator('.captionproblem')).toHaveText('Needs some text')
      await expect(authedPage.locator('#captions-save')).toBeDisabled()

      await row.locator('.caption-text').fill('Backwards')
      await row.locator('.caption-end').fill('0')
      await row.locator('.caption-end').blur()
      await expect(row.locator('.captionproblem')).toHaveText('Ends before it starts')
      await expect(authedPage.locator('#captions-save')).toBeDisabled()

      await row.locator('.caption-end').fill('1')
      await row.locator('.caption-end').blur()
      await expect(row.locator('.captionproblem')).toHaveCount(0)
      await expect(authedPage.locator('#captions-save')).toBeEnabled()
    })
  })

  test('a caption is deleted, and the deletion saved', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Deleting takes a caption out of the list; saving takes it off the
     * project.
     */
    await withProject(request, token, {}, async project => {
      await saveCaptions(request, token, project, {
        captions: [
          { start: 0, end: 1, text: 'Keep' },
          { start: 1, end: 2, text: 'Drop' },
        ],
      })
      await openCaptions(authedPage, project)
      await expect(rows(authedPage)).toHaveCount(2)
      await rows(authedPage).nth(1).locator('.caption-delete').click()
      await authedPage.locator('#captions-save').click()
      await expect(authedPage.locator('#captions-unsaved')).toHaveCount(0)
      expect((await captionsOf(request, token, project)).captions).toEqual([
        { start: 0, end: 1, text: 'Keep' },
      ])
    })
  })
})

test.describe('captions from a file', () => {
  test('a subtitle file is read by the server, reviewed, and saved', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * # Recipe: import subtitles
     *
     * Import a SubRip (.srt), WebVTT (.vtt) or JSON file. The server reads it
     * -- forgiving the habits of the tools that wrote it -- and the panel
     * shows what it found before anything is kept: use them, add them to
     * the captions already there, or cancel.
     */
    await withProject(request, token, {}, async project => {
      await openCaptions(authedPage, project)
      const sent = []
      authedPage.on('request', r => {
        if (r.url().endsWith('/captions/import')) sent.push(r.postDataJSON())
      })

      await authedPage.locator('#captions-file').setInputFiles({
        name: 'talk.srt',
        mimeType: 'application/x-subrip',
        buffer: Buffer.from(SRT),
      })
      const review = authedPage.locator('#captions-review')
      await expect(review).toContainText('talk.srt: 2 captions')
      expect(sent[0].format).toBe('srt')
      // Nothing is kept until it is accepted.
      expect((await captionsOf(request, token, project)).captions).toEqual([])

      await authedPage.locator('#captions-review-replace').click()
      await expect(review).toHaveCount(0)
      await expect(rows(authedPage)).toHaveCount(2)
      await expect(rows(authedPage).nth(1).locator('.caption-text')).toHaveValue(
        'Said second'
      )
      await expect(authedPage.locator('#captions-unsaved')).toHaveCount(0)

      // A WebVTT file, with a byte-order mark and CRLF, added to them.
      await authedPage.locator('#captions-file').setInputFiles({
        name: 'more.vtt',
        mimeType: 'text/vtt',
        buffer: Buffer.from(VTT),
      })
      await expect(review).toContainText('more.vtt: 1 caption')
      await authedPage.locator('#captions-review-append').click()
      await expect(rows(authedPage)).toHaveCount(3)
      // Added at once, saved by a request of its own: the panel says the save
      // has landed when its unsaved note goes. Read before then, the server
      // still held the two from before.
      await expect(authedPage.locator('#captions-unsaved')).toHaveCount(0)

      const saved = await captionsOf(request, token, project)
      expect(saved.captions.map(c => c.text)).toEqual([
        'Said first',
        'Said second',
        'And a third',
      ])
    })
  })

  test('a file that cannot be read says which line', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The server's reason, naming the line it could not read, is shown where
     * the review would have been, and nothing is kept.
     */
    await withProject(request, token, {}, async project => {
      await openCaptions(authedPage, project)
      await authedPage.locator('#captions-file').setInputFiles({
        name: 'broken.srt',
        mimeType: 'application/x-subrip',
        buffer: Buffer.from('1\n00:00:01,000 --> 00:00:02,000\nFine\n\nnot a cue\n'),
      })
      await expect(authedPage.locator('#captions-error')).toContainText('line 5')
      await expect(authedPage.locator('#captions-review')).toHaveCount(0)
    })
  })
})

test.describe('how captions are drawn', () => {
  test('the style is saved with the captions, and off until someone says', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Size, position, colours, the box behind the text and the font are
     * saved with the captions. "Draw into renders" starts unticked: a
     * project's captions are drawn only once someone says so.
     */
    await withProject(request, token, {}, async project => {
      await saveCaptions(request, token, project, {
        captions: [{ start: 0, end: 2, text: 'Styled' }],
      })
      await openCaptions(authedPage, project)
      await expect(authedPage.locator('#caption-enabled')).not.toBeChecked()

      await authedPage.locator('#caption-enabled').check()
      await authedPage.locator('#caption-size').fill('40')
      await authedPage.locator('#caption-position').selectOption('top')
      await authedPage.locator('#caption-box').uncheck()
      await authedPage.locator('#captions-save').click()
      await expect(authedPage.locator('#captions-unsaved')).toHaveCount(0)

      const { style } = await captionsOf(request, token, project)
      expect(style).toMatchObject({
        enabled: true,
        fontsize: 40,
        position: 'top',
        bg: '',
      })
    })
  })

  test('the caption under the playhead shows over the viewer', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Whether or not the Captions panel is in view, the caption under the
     * playhead is drawn over the viewer in its style; past it, nothing is.
     */
    await withProject(request, token, {}, async project => {
      await saveCaptions(request, token, project, {
        captions: [{ start: 0, end: 2, text: 'Over the picture' }],
        style: { enabled: true },
      })
      // The Captions tab is left behind Render, so the panel is not drawn at
      // all: the viewer shows captions regardless.
      await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
      const overlay = authedPage.locator('#caption-overlay')
      await expect(overlay).toHaveText('Over the picture')
      await expect(overlay).toHaveAttribute('data-drawn', 'true')
      await expect(authedPage.locator('#panel-captions')).toHaveCount(0)

      // Past it, nothing.
      await authedPage.keyboard.press('End')
      await expect(overlay).toHaveCount(0)
    })
  })

  test('renders carry the captions once they are drawn, and not before', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * # Recipe: burn captions into a render
     *
     * Tick "Draw into renders" and save. Every render of the timeline then
     * carries the captions and their style, and the server draws them over
     * the picture at the render's own size.
     */
    await withProject(request, token, {}, async project => {
      await saveCaptions(request, token, project, {
        captions: [{ start: 0.5, end: 2, text: 'Burned in' }],
      })
      const sent = []
      await authedPage.route(
        url => url.pathname === '/render',
        async route => {
          if (route.request().method() !== 'POST') return route.fallback()
          sent.push(route.request().postDataJSON())
          await route.fulfill({ status: 200, json: 'abcdefabcdefabcdefabcdef' })
        }
      )

      await authedPage.goto(`/#!/?project=${project._id}&stage=render`)
      await expect(authedPage.locator('#timeline .clip').first()).toBeVisible()
      await authedPage.locator('#queue-render').click()
      await expect.poll(() => sent.length).toBe(1)
      expect(sent[0].captions).toBeUndefined()

      await openCaptions(authedPage, project)
      await authedPage.locator('#caption-enabled').check()
      await authedPage.locator('#captions-save').click()
      await expect(authedPage.locator('#captions-unsaved')).toHaveCount(0)

      await authedPage.locator('#stage-render').click()
      await authedPage.locator('#queue-render').click()
      await expect.poll(() => sent.length).toBe(2)
      expect(sent[1].captions).toEqual([{ start: 0.5, end: 2, text: 'Burned in' }])
      expect(sent[1].caption_style.enabled).toBe(true)
    })
  })
})

// `GET /health` as the contract shapes it (alfred/core/routes/health.py), a
// renderer running, for a spec to give its own `audio_engine`.
const HEALTHY = { api: 'ok', db: 'ok', renderer: { ok: true, workers: 1 }, queue: { pending: 0 } }

test.describe('transcribing the timeline', () => {
  test('transcribing says why it cannot', async ({ authedPage, request, token }) => {
    /**
     * Transcribing needs an audio engine that answers and a renderer to mix
     * the timeline's sound. Until the server has said whether there is one,
     * the button waits and says it is checking; without one, it says which
     * is missing.
     */
    await withProject(request, token, {}, async project => {
      // The server's answer, held to two cases it can give -- and given here,
      // when the test says, rather than fetched from the server and edited.
      // Fetched, a busy server's answer could take longer than the test
      // waits, while the button stood enabled: what is under test is what
      // the panel does before an answer and with each one, not how fast the
      // server is.
      let engine = { configured: false, ok: false, detail: 'none' }
      let answer
      const answered = new Promise(resolve => (answer = resolve))
      await authedPage.route('**/health', async route => {
        await answered
        await route.fulfill({ json: { ...HEALTHY, audio_engine: engine } })
      })
      // From a fresh load, so the session's first check of all is this one.
      await authedPage.goto(`/#!/?project=${project._id}&stage=edit`)
      await authedPage.reload()
      await showCaptions(authedPage)
      await expect(authedPage.locator('#caption-add')).toBeEnabled()
      const button = authedPage.locator('#captions-transcribe')
      const reason = authedPage.locator('#captions-transcribe-reason')
      // Mutation: give no reason until `/health` has come back -- the button
      // is enabled while it waits, and this fails.
      await expect(reason).toHaveText('Checking the audio engine…')
      await expect(button).toBeDisabled()

      answer()
      await expect(reason).toContainText('No audio engine is configured')
      await expect(button).toBeDisabled()

      engine = { configured: true, ok: false, detail: 'the audio engine at http://e: refused' }
      await authedPage.reload()
      await showCaptions(authedPage)
      await expect(reason).toContainText('cannot be reached: the audio engine at http://e: refused')
      await expect(button).toBeDisabled()
    })
  })

  test('a transcription already under way is followed, and the refusal still read', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Another tab, or an API client, started one first. The server refuses a
     * second with 409 and `code: "transcription_running"` beside its
     * sentence (docs/api/errors.md). The panel shows the sentence, and,
     * because of the code, follows the transcription under way until its
     * captions arrive -- the ones a second would have made.
     */
    await withProject(request, token, {}, async project => {
      const path = `/project/${project._id}/captions`
      const style = (await captionsOf(request, token, project)).style
      const heard = [{ start: 0.5, end: 2, text: 'Heard by the other one' }]
      // What the server holds: nothing, until the refusal; then the other
      // transcription, which is done the second time it is looked at.
      let looks = 0
      let refused = false
      await authedPage.route('**/health', route =>
        route.fulfill({
          json: { ...HEALTHY, audio_engine: { configured: true, ok: true, detail: null } },
        })
      )
      await authedPage.route(
        url => url.pathname === `${path}/transcribe`,
        route => {
          refused = true
          return route.fulfill({
            status: 409,
            json: {
              detail: "This project's timeline is already being transcribed; wait for that to finish.",
              code: 'transcription_running',
            },
          })
        }
      )
      await authedPage.route(
        url => url.pathname === path,
        route => {
          if (route.request().method() !== 'GET') return route.fallback()
          if (!refused) return route.fulfill({ json: { captions: [], style, job: null } })
          looks += 1
          const done = looks > 1
          return route.fulfill({
            json: {
              captions: done ? heard : [],
              style,
              job: {
                state: done ? 'done' : 'transcribing',
                error: null,
                engine: 'http://engine.test',
                segments: done ? 1 : null,
                updated_at: new Date().toISOString(),
              },
            },
          })
        }
      )

      await openCaptions(authedPage, project)
      await expect(authedPage.locator('#captions-transcribe')).toBeEnabled()
      await authedPage.locator('#captions-transcribe').click()
      // The sentence, as the server wrote it; never the code.
      await expect(authedPage.locator('#captions-error')).toHaveText(
        "Could not transcribe: This project's timeline is already being transcribed; wait for that to finish."
      )
      // Mutation: drop the switch on the code -- nothing follows, and the job
      // line never appears.
      const job = authedPage.locator('#captions-job')
      await expect(job).toHaveAttribute('data-state', 'done')
      await expect(rows(authedPage)).toHaveCount(1)
      await expect(rows(authedPage).locator('.caption-text')).toHaveValue('Heard by the other one')
    })
  })
})

test.describe('@slow transcribing through the worker', () => {
  test('the timeline is heard by the audio engine and captioned', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * # Recipe: caption a timeline from what it says
     *
     * "Transcribe timeline" sends the project's saved timeline to the
     * server's audio engine: the render worker mixes its sound, the engine
     * hears it, and what it said becomes captions, timed by the timeline.
     * Here the sound is two bursts of tone placed a second into the
     * timeline, and the stub engine hears a line of speech in each.
     */
    test.setTimeout(180_000)
    await needEngine(request, token)
    const edl = {
      clips: [
        { type: 'template', name: 'makeColor', duration: 6.0, start: 0, fadeIn: 0, fadeOut: 0, data: { color: '#203040' } },
        { type: 'audio', name: FIXTURE, duration: 4.0, start: 1.0, fadeIn: 0, fadeOut: 0 },
      ],
    }
    await withProject(request, token, { edl }, async project => {
      await openCaptions(authedPage, project)
      await authedPage.locator('#captions-transcribe').click()
      const job = authedPage.locator('#captions-job')
      await expect(job).toHaveAttribute('data-state', /queued|transcribing|done/)
      await expect(job).toHaveAttribute('data-state', 'done', { timeout: 150_000 })
      await expect(job).toContainText('2 segments')

      await expect(rows(authedPage)).toHaveCount(2)
      const saved = await captionsOf(request, token, project)
      expect(saved.captions.map(c => c.text)).toEqual([
        'the first thing said',
        'and then a second line',
      ])
      // The fixture's bursts, a second later on the timeline.
      const times = saved.captions.map(c => [Math.round(c.start * 10) / 10, Math.round(c.end * 10) / 10])
      expect(times).toEqual([
        [1.5, 2.5],
        [3.0, 4.2],
      ])
      expect(saved.job).toMatchObject({ state: 'done', segments: 2 })
      expect(saved.style.enabled).toBe(false)

      // What the engine was sent: the mix, as speech engines want it.
      const engineUrl = process.env.E2E_AUDIO_ENGINE_URL
      if (engineUrl) {
        const uploads = await (await request.get(`${engineUrl}/stub/uploads`)).json()
        expect(uploads.at(-1)).toMatchObject({
          content_type: 'audio/wav',
          sample_rate: 16000,
          channels: 1,
        })
      }
    })
  })

  test('a timeline with no sound fails, and says so', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * A timeline whose clips have no sound track -- the demo media is silent
     * -- fails with that reason, and the captions it had are left alone.
     */
    test.setTimeout(120_000)
    await needEngine(request, token)
    // Demo media is silent: a video clip with no sound track.
    const videos = await (await request.get('/videos', auth(token))).json()
    const silent = videos.find(v => v.includes('demo-bars'))
    const edl = { clips: [{ type: 'video', name: silent, duration: 2, start: 0 }] }
    await withProject(request, token, { edl }, async project => {
      await openCaptions(authedPage, project)
      await authedPage.locator('#captions-transcribe').click()
      const job = authedPage.locator('#captions-job')
      await expect(job).toHaveAttribute('data-state', 'failed', { timeout: 100_000 })
      await expect(job).toContainText('has a sound track')
    })
  })
})

test.describe('the audio engine, through the API', () => {
  test('GET /health says whether there is one', async ({ request, token }) => {
    /**
     * `audio_engine` says whether one is `configured` and `ok`, and in
     * `detail`, why not.
     */
    const health = await (await request.get('/health', auth(token))).json()
    expect(Object.keys(health.audio_engine).sort()).toEqual(['configured', 'detail', 'ok'])
    expect(typeof health.audio_engine.configured).toBe('boolean')
    expect(typeof health.audio_engine.ok).toBe('boolean')
  })

  test('a project answers its captions, style and job', async ({ request, token }) => {
    /**
     * `PUT /project/{id}/captions` answers what it stored, in order; the
     * style states `enabled`, and `GET /project/{id}` carries both.
     */
    await withProject(request, token, {}, async project => {
      const body = await saveCaptions(request, token, project, {
        captions: [{ start: 2, end: 3, text: 'b' }, { start: 0, end: 1, text: 'a' }],
      })
      expect(body.captions.map(c => c.text)).toEqual(['a', 'b'])
      expect(body.style.enabled).toBe(false)
      expect(body.job).toBeNull()
      const whole = await (await request.get(`/project/${project._id}`, auth(token))).json()
      expect(whole.captions).toHaveLength(2)
      expect(whole.caption_style.enabled).toBe(false)
    })
  })

})

test.describe('@slow the audio engine hears library media', () => {
  test('a library file is analysed by the engine', async ({ request, token }) => {
    /**
     * `GET /media/{name}/audio` answers what the engine measured: here, the
     * fixture's two bursts of tone, as onsets and the silences around them.
     */
    test.setTimeout(60_000)
    await needEngine(request, token)
    const res = await request.get(`/media/${FIXTURE}/audio?features=onsets,silences`, auth(token))
    expect(res.status(), await res.text()).toBe(200)
    const analysis = await res.json()
    expect(analysis.onsets).toEqual([0.5, 2.0])
    expect(analysis.silences[0]).toEqual({ start: 0, end: 0.5 })
  })
})
