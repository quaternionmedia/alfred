/**
 * Media the browser fetches by itself.
 *
 * # Recipe: media links that work without a session
 *
 * A `<video src>`, an `<img src>` or an `<a download>` is a request the
 * browser makes on its own, and it carries no session. So the API hands out
 * signed URLs for the files those elements need -- each good for one path, for
 * a limited time -- and the file routes accept one in place of a session
 * (contract M1):
 *
 * - `GET /media` lists the library with what the editor needs to place each
 *   file -- its kind, how long it runs, its size in pixels -- and a signed
 *   `url` to load it from (contract M2).
 * - `POST /preview/` answers with a signed URL for the frame it made.
 * - a render's `download_url`, in its status and in the render list.
 *
 * The frames used to be served from `/data`, a static mount open to anyone;
 * it is gone.
 */

const { test, expect } = require('./fixtures')

/** The library as `GET /media` describes it, after global setup's demo media. */
async function media(request, token) {
  const res = await request.get('/media', { headers: { Authorization: token } })
  expect(res.status()).toBe(200)
  return res.json()
}

test.describe('the media library', () => {
  test('GET /media describes exactly the files GET /videos lists', async ({
    request,
    token,
  }) => {
    const listed = await (
      await request.get('/videos', { headers: { Authorization: token } })
    ).json()
    const described = await media(request, token)
    expect(described.map(item => item.name)).toEqual(listed)
    for (const item of described) {
      expect(Object.keys(item).sort()).toEqual(
        ['duration', 'fps', 'height', 'kind', 'name', 'size', 'url', 'width'].sort()
      )
    }
  })

  test('a clip says how long it runs and how big its picture is', async ({
    request,
    token,
  }) => {
    // The editor placed every library clip as five seconds long, because
    // nothing said otherwise. The demo bars are three seconds of 320x180 at 24.
    const bars = (await media(request, token)).find(
      item => item.name === 'videos/demo-bars.mp4'
    )
    expect(bars, 'global setup generates demo media').toBeTruthy()
    expect(bars.kind).toBe('video')
    expect(bars.duration).toBeCloseTo(3, 1)
    expect([bars.width, bars.height, bars.fps]).toEqual([320, 180, 24])
    expect(bars.size).toBeGreaterThan(0)
  })

  test('its url plays in a video element, in a page with no session', async ({
    page,
    request,
    token,
  }) => {
    const bars = (await media(request, token)).find(
      item => item.name === 'videos/demo-bars.mp4'
    )
    await page.goto('/')
    const played = await page.evaluate(
      url =>
        new Promise(resolve => {
          const video = document.createElement('video')
          video.muted = true
          video.addEventListener('loadeddata', () =>
            resolve({ ok: true, width: video.videoWidth })
          )
          video.addEventListener('error', () =>
            resolve({ ok: false, code: video.error && video.error.code })
          )
          video.src = url
          document.body.appendChild(video)
        }),
      bars.url
    )
    expect(played).toEqual({ ok: true, width: 320 })
  })

  test('a url opens its own file and no other', async ({ request, token }) => {
    const items = await media(request, token)
    const [first, second] = items
    test.skip(!second, 'needs two files in the library')
    const moved = `${second.url.split('?')[0]}?${first.url.split('?')[1]}`
    expect((await request.get(moved)).status()).toBe(401)
    expect((await request.get(second.url.split('?')[0])).status()).toBe(401)
  })
})

const FRAME_REQUEST = {
  edl: {
    clips: [
      {
        type: 'template',
        name: 'makeColor',
        duration: 1.0,
        start: 0.0,
        data: { color: '#f2aa4c' },
      },
    ],
    duration: 1.0,
  },
  width: 64,
  height: 48,
}

const SIGNED_FRAME = /^\/preview\/frames\/[0-9a-f]{32}\.jpg\?exp=\d+&sig=[A-Za-z0-9_-]{43}$/

async function previewFrame(request, token) {
  const res = await request.post('/preview/?t=0.5', {
    headers: { Authorization: token },
    data: FRAME_REQUEST,
  })
  expect(res.status(), await res.text()).toBe(200)
  return res.json()
}

test.describe('a preview frame', () => {
  test('the EDL preview answers with a signed URL for its frame', async ({
    request,
    token,
  }) => {
    const url = await previewFrame(request, token)
    expect(url).toMatch(SIGNED_FRAME)
  })

  test('the URL fetches the frame with no session', async ({ request, token }) => {
    const url = await previewFrame(request, token)
    const res = await request.get(url)
    expect(res.status()).toBe(200)
    expect(res.headers()['content-type']).toBe('image/jpeg')
    const bytes = await res.body()
    // A JPEG starts with FF D8.
    expect(bytes[0]).toBe(0xff)
    expect(bytes[1]).toBe(0xd8)
  })

  test('an image element shows it, in a page with no session at all', async ({
    page,
    request,
    token,
  }) => {
    // Nobody is logged in to this page: the URL is the only permission.
    const url = await previewFrame(request, token)
    await page.goto('/')
    const size = await page.evaluate(
      src =>
        new Promise(resolve => {
          const img = new Image()
          img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight })
          img.onerror = () => resolve(null)
          img.src = src
        }),
      url
    )
    expect(size).toEqual({ width: 64, height: 48 })
  })

  test('the frame without its signature is refused', async ({ request, token }) => {
    const url = await previewFrame(request, token)
    const res = await request.get(url.split('?')[0])
    expect(res.status()).toBe(401)
  })

  test('a signature moved to another frame is refused', async ({ request, token }) => {
    const first = await previewFrame(request, token)
    const second = await previewFrame(request, token)
    const moved = `${second.split('?')[0]}?${first.split('?')[1]}`
    expect((await request.get(moved)).status()).toBe(401)
  })
})

test.describe('nothing is served from /data', () => {
  test('the public mount the frames came from is gone', async ({ request, token }) => {
    // A frame made now is not reachable there, by its name or any other.
    const url = await previewFrame(request, token)
    const name = url.split('?')[0].split('/').pop()
    expect((await request.get(`/data/${name}`)).status()).toBe(404)
    expect((await request.get('/data/')).status()).toBe(404)
  })
})
