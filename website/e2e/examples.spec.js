/**
 * Each docs example (docs/examples/edl/*.json) previews on the demo media alone.
 * Fails by example name; never prints the frame's signed URL.
 */

const { test, expect } = require('./fixtures')
const { AT_LEAST, examples, moment } = require('./docs-examples')

// What `POST /preview/` answers: a frame path, signed.
const FRAME = /^\/preview\/frames\/[0-9a-f]{32}\.jpg\?/

// Brightest channel an all-black JPEG reaches, with margin.
const NOTHING_DRAWN = 40

const redact = text => String(text).replace(/sig=[^&\s"'\\]*/g, 'sig=…')

/** Fetch the frame by its signed URL, no session. */
async function fetchFrame(request, url, name) {
  let response
  try {
    response = await request.get(url)
  } catch (error) {
    // Playwright's message includes the URL.
    throw new Error(`${name}: its frame could not be fetched: ${redact(error.message)}`)
  }
  expect(response.status(), `${name}: fetching its frame answered ${response.status()}`).toBe(200)
  expect(response.headers()['content-type'], `${name}: its frame is not a JPEG`).toBe('image/jpeg')
  return response.body()
}

/** Decode in the browser: size and brightest channel value. */
const look = (page, jpeg) =>
  page.evaluate(async data => {
    const image = new Image()
    image.src = `data:image/jpeg;base64,${data}`
    try {
      await image.decode()
    } catch (error) {
      return { decoded: false }
    }
    const canvas = document.createElement('canvas')
    canvas.width = image.naturalWidth
    canvas.height = image.naturalHeight
    const context = canvas.getContext('2d')
    context.drawImage(image, 0, 0)
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data
    let brightest = 0
    for (let i = 0; i < pixels.length; i += 4) {
      brightest = Math.max(brightest, pixels[i], pixels[i + 1], pixels[i + 2])
    }
    return { decoded: true, width: image.naturalWidth, height: image.naturalHeight, brightest }
  }, jpeg.toString('base64'))

test.describe('the docs examples', () => {
  test('are there to test', () => {
    // None found would pass silently below.
    expect(examples().length).toBeGreaterThanOrEqual(AT_LEAST)
  })

  for (const example of examples()) {
    test(`${example.file} previews on the demo media`, async ({ page, request, token }) => {
      const headers = { Authorization: token }
      const demo = await request.post('/demo/media', { headers })
      expect(demo.status(), 'POST /demo/media made the demo media').toBe(200)

      const t = moment(example)
      const preview = await request.post(`/preview/?t=${t}`, { headers, data: example.body })
      const status = preview.status()
      // On success the body is the signed URL: read it only on failure.
      const why = status === 200 ? '' : redact(await preview.text())
      expect(status, `${example.name}: POST /preview/?t=${t} was refused: ${why}`).toBe(200)

      const url = await preview.json()
      expect(
        typeof url === 'string' && FRAME.test(url),
        `${example.name}: POST /preview/ answered something other than a frame's signed URL`
      ).toBe(true)

      const seen = await look(page, await fetchFrame(request, url, example.name))
      expect(seen.decoded, `${example.name}: its frame is not a picture`).toBe(true)
      expect(
        [seen.width, seen.height],
        `${example.name}: its frame is not the size asked for`
      ).toEqual([example.body.width || 1920, example.body.height || 1080])
      expect(
        seen.brightest,
        `${example.name}: its frame at ${t} s has nothing drawn on it`
      ).toBeGreaterThan(NOTHING_DRAWN)
    })
  }
})
