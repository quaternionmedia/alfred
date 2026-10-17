/**
 * Contracts the editor depends on, asserted at the HTTP level.
 *
 * # Recipe: what the API promises the editor
 *
 * The browser specs check that the editor works. These check the promises it
 * is built on, where a change would break the editor without breaking any
 * assertion about the DOM: which templates exist, what a preview returns, what
 * a malformed request gets back, and which fields a write may touch.
 *
 * All of it against the running stack with real data.
 */

const { test, expect } = require('./fixtures')

test.describe('the template preview', () => {
  test('renders a real image for every advertised template', async ({
    request,
    token,
  }) => {
    /**
     * `Preview.js` builds this URL for every template clip on the timeline,
     * and it 404'd for years because the route it named -- `otto/template/...`
     * -- had never existed on this server.
     *
     * Rendered at a time past where a fade would end. The preview builds its
     * clip with no fades unless the query asks for them, so t=0 would do as
     * well today -- but a frame from a fade is a near-identical few kilobytes
     * for every template, and asking for one after it keeps this asserting a
     * real picture whatever the fade defaults become.
     */
    const templates = await (
      await request.get('/templates', { headers: { Authorization: token } })
    ).json()
    expect(templates.length).toBeGreaterThan(0)

    for (const template of templates) {
      const res = await request.get(
        `/preview/template/${template.name}` +
          '?text=Alfred&color=%23101820&width=320&height=180&t=0.9'
      , { headers: { Authorization: token } })

      expect(res.status(), `${template.name} did not preview`).toBe(200)
      expect(res.headers()['content-type']).toContain('image')
      const body = await res.body()
      expect(body.length, `${template.name} produced an empty image`).toBeGreaterThan(
        1000
      )
    }
  })

  test('refuses a name that is not an advertised template', async ({
    request,
    token,
  }) => {
    /**
     * The allowlist is load-bearing, not decorative.
     *
     * otto's module namespace holds far more callables than templates --
     * `ColorClip`, `rgbToDec` and the rest are imports it happens to carry.
     * otto now resolves names through its own `TEMPLATES` registry, but this
     * server's allowlist is what decides what it offers: `final` is in otto's
     * registry and deliberately not offered here, since a clip cannot carry
     * the address, website and phone it shows. Each of these must answer 404.
     */
    for (const name of ['ColorClip', 'rgbToDec', 'concatenate_videoclips', 'final']) {
      const res = await request.get(`/preview/template/${name}?width=320&height=180`, {
        headers: { Authorization: token },
      })
      expect(res.status(), `${name} was accepted as a template`).toBe(404)
    }
  })

  test('previewing requires a session', async ({ request }) => {
    const res = await request.get('/preview/template/makeColor?width=320&height=180')
    expect(res.status()).toBe(401)
  })

  test('the same request twice gives the same size image', async ({
    request,
    token,
  }) => {
    // Determinism, cheaply: a preview that varies run to run makes every
    // downstream comparison unreliable, and a template reading the clock is
    // the usual way that happens.
    const url =
      '/preview/template/makeColor?color=%23f2aa4c&width=320&height=180&t=0.5'
    const first = await request.get(url, { headers: { Authorization: token } })
    const second = await request.get(url, { headers: { Authorization: token } })

    expect((await first.body()).length).toBe((await second.body()).length)
  })
})

test.describe('malformed input is answered, not crashed on', () => {
  const cases = [
    ['/project/undefined', 422],
    ['/project/null', 422],
    ['/render/undefined', 422],
    ['/project/deadbeefdeadbeefdeadbeef', 404],
    ['/render/deadbeefdeadbeefdeadbeef', 404],
  ]

  for (const [path, expected] of cases) {
    test(`GET ${path} answers ${expected}`, async ({ request, token }) => {
      /**
       * The editor really does send `undefined`: its routes read a `project`
       * query parameter that is not always present, and `'/project/' + undefined`
       * is a string the browser will happily request. Both of these answered
       * 500 -- through two different exception hierarchies needing two
       * different fixes, one in beanie and one in bson.
       */
      const res = await request.get(path, { headers: { Authorization: token } })
      expect(res.status()).toBe(expected)
    })
  }
})

test.describe('project writes touch only what they claim', () => {
  test('the settings route saves render settings and destination', async ({
    request,
    token,
  }) => {
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const target = projects.find(p => p.name === 'Timeline demo') || projects[0]
    test.skip(!target, 'no projects to write to')

    const res = await request.put(`/project/${target._id}/settings`, {
      headers: { Authorization: token },
      data: { render_settings: { width: 1280, height: 720 }, destination: 'local' },
    })
    expect(res.status()).toBe(200)

    const saved = await res.json()
    expect(saved.render_settings.width).toBe(1280)
    expect(saved.destination).toBe('local')
  })

  test('saving settings leaves the rest of the project intact', async ({
    request,
    token,
  }) => {
    /**
     * The guard for a defect that cost a document.
     *
     * `PUT /project/{id}` goes through the crud router's update, which
     * replaces the whole record with the request body -- so a partial save
     * wrote null over `name` and `logic`. The write succeeded, because writes
     * are not validated; every subsequent read of that project answered 500,
     * because reads are. One request turned a readable project into an
     * unreadable one and nothing reported an error until the next reader
     * arrived.
     */
    const before = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const target = before.find(p => p.name === 'Timeline demo')
    test.skip(!target, 'the timeline demo is not seeded here')

    await request.put(`/project/${target._id}/settings`, {
      headers: { Authorization: token },
      data: { destination: 'local' },
    })

    const after = await (
      await request.get(`/project/${target._id}`, { headers: { Authorization: token } })
    ).json()

    expect(after.name, 'the project lost its name').toBe(target.name)
    expect(after.logic, 'the project lost its logic').not.toBeNull()
    expect(
      after.edl.clips.length,
      'the project lost its timeline'
    ).toBe(target.edl.clips.length)
  })

  test('the project stays readable afterwards', async ({ request, token }) => {
    // The symptom the corruption actually presented as: not a failed write,
    // but every later read returning 500.
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    for (const project of projects) {
      const res = await request.get(`/project/${project._id}`, {
        headers: { Authorization: token },
      })
      expect(res.status(), `${project.name} is no longer readable`).toBe(200)
    }
  })
})
