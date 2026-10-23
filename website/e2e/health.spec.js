/**
 * Whether the stack can do its work.
 *
 * # Recipe: is a renderer running?
 *
 * A render waits in `queued` until a worker takes it. On a stack with no
 * worker -- the thin stack runs none -- it waited for ever, and nothing could
 * say why. `GET /health` says how many render workers answer and how many
 * jobs are waiting (contract M3), and how many previews the api is drawing
 * and how many wait for a turn; `GET /healthz` answers container health
 * checks with no session and nothing behind it.
 *
 * This stack runs a worker against a database that starts empty, which is
 * also the case where a worker used to be deaf to pings until it restarted.
 */

const { test, expect } = require('./fixtures')

test.describe('health', () => {
  test('GET /healthz answers with no session', async ({ request }) => {
    const res = await request.get('/healthz')
    expect(res.status()).toBe(200)
    expect(await res.json()).toEqual({ ok: true })
  })

  test('GET /health needs a session', async ({ request }) => {
    expect((await request.get('/health')).status()).toBe(401)
  })

  test('GET /health has the contract fields', async ({ request, token }) => {
    const res = await request.get('/health', { headers: { Authorization: token } })
    expect(res.status()).toBe(200)
    const health = await res.json()
    expect(Object.keys(health).sort()).toEqual([
      'api',
      'audio_engine',
      'db',
      'previews',
      'queue',
      'renderer',
    ])
    expect(health.api).toBe('ok')
    expect(health.db).toBe('ok')
    expect(Object.keys(health.renderer).sort()).toEqual(['ok', 'workers'])
    expect(Object.keys(health.queue)).toEqual(['pending'])
    // How many previews are being drawn, how many wait for a slot, and how
    // many may be drawn at once (ALFRED_PREVIEW_CONCURRENCY).
    expect(Object.keys(health.previews).sort()).toEqual(['limit', 'running', 'waiting'])
    expect(health.previews.limit).toBeGreaterThanOrEqual(1)
    expect(Object.keys(health.audio_engine).sort()).toEqual(['configured', 'detail', 'ok'])
  })

  test('the running worker answers, so the renderer is ok', async ({
    request,
    token,
  }) => {
    // A worker starts listening for pings when it starts; poll briefly in
    // case this runs before it has.
    await expect
      .poll(
        async () => {
          const res = await request.get('/health', {
            headers: { Authorization: token },
          })
          return (await res.json()).renderer
        },
        { timeout: 30_000, intervals: [1_000, 2_000, 5_000] }
      )
      .toEqual({ ok: true, workers: expect.any(Number) })
    const { renderer, queue } = await (
      await request.get('/health', { headers: { Authorization: token } })
    ).json()
    expect(renderer.workers).toBeGreaterThanOrEqual(1)
    expect(typeof queue.pending).toBe('number')
  })
})
