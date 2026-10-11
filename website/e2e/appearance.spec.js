/**
 * Visual consistency, symmetry, and the functionality that depends on them.
 *
 * Deliberately not screenshot comparison. Pixel baselines differ by platform
 * and font rendering, so on a Windows host and a Linux CI they disagree about
 * everything and the suite gets muted -- which is worse than not having it.
 * These measure the geometry instead: what lines up, what is the same size as
 * its siblings, and what stays inside the viewport. Those are the properties a
 * person actually notices, and they hold on any renderer.
 *
 * The app claims to work "including mobile devices", so every layout assertion
 * runs at a phone width too.
 */

const { test, expect } = require('./fixtures')

const VIEWPORTS = [
  { name: 'phone', width: 390, height: 844 },
  { name: 'tablet', width: 820, height: 1180 },
  { name: 'desktop', width: 1440, height: 900 },
]

const STAGES = ['source', 'edit', 'render', 'deliver']

/** Rounded so sub-pixel layout differences do not read as misalignment. */
async function boxes(locator) {
  return locator.evaluateAll(nodes =>
    nodes.map(n => {
      const r = n.getBoundingClientRect()
      return {
        x: Math.round(r.x),
        y: Math.round(r.y),
        width: Math.round(r.width),
        height: Math.round(r.height),
        right: Math.round(r.right),
      }
    })
  )
}

test.describe('layout holds at every width', () => {
  for (const viewport of VIEWPORTS) {
    test(`no horizontal overflow on ${viewport.name}`, async ({ authedPage }) => {
      /**
       * A page wider than its viewport is the most common and least excusable
       * layout failure: on a phone it means the whole interface slides
       * sideways under the thumb. The stage rail scrolls internally by design,
       * which is why this asserts on the document rather than on every child.
       */
      await authedPage.setViewportSize(viewport)
      await authedPage.goto('/')
      await expect(authedPage.locator('#timeline')).toBeVisible()

      const overflow = await authedPage.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth
      )
      expect(overflow, 'the page scrolls sideways').toBeLessThanOrEqual(0)
    })

    test(`the stage rail stays reachable on ${viewport.name}`, async ({
      authedPage,
    }) => {
      await authedPage.setViewportSize(viewport)
      await authedPage.goto('/')

      const rail = authedPage.locator('.stagerail')
      await expect(rail).toBeVisible()

      const [box] = await boxes(rail)
      expect(box.x, 'the rail starts off-screen').toBeGreaterThanOrEqual(0)
      expect(box.right, 'the rail runs past the viewport').toBeLessThanOrEqual(
        viewport.width
      )
    })
  }
})

test.describe('symmetry within the stage rail', () => {
  test('every stage button is the same height', async ({ authedPage }) => {
    // Buttons of differing heights in one row is the thing that makes an
    // interface look assembled rather than designed, and it is invisible in a
    // screenshot review until someone points at it.
    await authedPage.goto('/')
    const heights = (await boxes(authedPage.locator('.stagerail .stage'))).map(
      b => b.height
    )
    expect(heights.length).toBe(STAGES.length)
    expect(new Set(heights).size, `heights differ: ${heights}`).toBe(1)
  })

  test('every stage button sits on the same baseline', async ({ authedPage }) => {
    await authedPage.goto('/')
    const tops = (await boxes(authedPage.locator('.stagerail .stage'))).map(b => b.y)
    expect(new Set(tops).size, `tops differ: ${tops}`).toBe(1)
  })

  test('the stage numbers are round, not ovals', async ({ authedPage }) => {
    // They are circles by intent -- a border-radius of 50% on a non-square box
    // gives a lozenge, which is the usual way this goes wrong.
    await authedPage.goto('/')
    for (const box of await boxes(authedPage.locator('.stagerail .stagenum'))) {
      expect(Math.abs(box.width - box.height), 'stage number is not square').toBeLessThanOrEqual(1)
    }
  })

  test('stages are evenly spaced', async ({ authedPage }) => {
    await authedPage.setViewportSize({ width: 1440, height: 900 })
    await authedPage.goto('/')
    const stages = await boxes(authedPage.locator('.stagerail .stage'))
    const gaps = stages.slice(1).map((s, i) => s.x - stages[i].right)
    // One consistent gap, within a pixel of rounding.
    const spread = Math.max(...gaps) - Math.min(...gaps)
    expect(spread, `uneven gaps: ${gaps}`).toBeLessThanOrEqual(1)
  })

  test('exactly one stage reads as current', async ({ authedPage }) => {
    // Two highlighted stages, or none, and the rail stops telling you where
    // you are -- which is the only job it has.
    await authedPage.goto('/')
    await expect(authedPage.locator('.stagerail .stage.active')).toHaveCount(1)
    for (const stage of STAGES) {
      await authedPage.goto(`/#!/?stage=${stage}`)
      await expect(authedPage.locator('.stagerail .stage.active')).toHaveCount(1)
      await expect(authedPage.locator(`#stage-${stage}`)).toHaveClass(/active/)
    }
  })

  test('the current stage is distinguishable by more than position', async ({
    authedPage,
  }) => {
    /**
     * The active stage must differ visually, not just in the DOM. Asserting
     * "some colour differs" rather than a specific colour keeps this from
     * breaking on a palette change while still failing if the distinction is
     * removed altogether.
     */
    await authedPage.goto('/#!/?stage=render')
    const active = authedPage.locator('#stage-render')
    const inactive = authedPage.locator('#stage-source')

    const colourOf = locator =>
      locator.evaluate(n => {
        const s = getComputedStyle(n)
        return `${s.backgroundColor}|${s.color}`
      })

    expect(await colourOf(active)).not.toBe(await colourOf(inactive))
  })
})

test.describe('consistency across controls', () => {
  test('panel buttons are all one height, wherever they appear', async ({
    authedPage,
  }) => {
    /**
     * Measured against the CSS contract, not against each other.
     *
     * Comparing buttons to their siblings looked more direct and was not
     * usable: the Deliver panel lists a button per undelivered render, and the
     * render-pipeline and flow specs create and deliver renders while this
     * runs. So the set being measured changed underneath it -- sometimes to
     * nothing, leaving one button and no comparison to make. The test passed
     * alone and failed in the full suite, every time, which is the shape of a
     * shared-state dependency rather than a layout bug.
     *
     * Every single-line action button should be 2rem tall, allowing a pixel
     * for flex rounding. That holds whether the panel lists six renders or
     * none, and still catches the drift this was written for: Render and
     * Deliver buttons differed by two pixels before stages.scss gave them a
     * height.
     */
    const EXPECTED = 32 // 2rem at the default root size
    const measured = []

    for (const stage of ['render', 'deliver']) {
      await authedPage.goto(`/#!/?stage=${stage}`)
      await expect(authedPage.locator(`#panel-${stage} h3`).first()).toBeVisible()

      // The project chooser is excluded: it stacks a name over a clip count
      // and is taller on purpose.
      const found = await boxes(
        authedPage.locator(`#panel-${stage} button:not(.projectchoice)`)
      )
      measured.push(...found.map(b => b.height))
    }

    expect(measured.length, 'found no action buttons at all').toBeGreaterThan(0)
    for (const height of measured) {
      expect(
        Math.abs(height - EXPECTED),
        `a panel button is ${height}px, not ${EXPECTED}px (all: ${measured})`
      ).toBeLessThanOrEqual(1)
    }
  })

  test('panel headings share one type treatment', async ({ authedPage }) => {
    const seen = new Set()
    for (const stage of ['source', 'render', 'deliver']) {
      await authedPage.goto(`/#!/?stage=${stage}`)
      await expect(authedPage.locator(`#panel-${stage} h3`).first()).toBeVisible()
      const styles = await authedPage
        .locator('.stagepanel h3')
        .evaluateAll(nodes =>
          nodes.map(n => {
            const s = getComputedStyle(n)
            return `${s.fontSize}|${s.textTransform}|${s.letterSpacing}`
          })
        )
      styles.forEach(s => seen.add(s))
    }
    expect(seen.size, `headings styled ${seen.size} different ways`).toBe(1)
  })

  test('every panel aligns to the same left edge', async ({ authedPage }) => {
    // Panels that start at different x-positions read as separate pages
    // stitched together, which is exactly what the stage rail exists to deny.
    const lefts = []
    for (const stage of ['source', 'render', 'deliver']) {
      await authedPage.goto(`/#!/?stage=${stage}`)
      const [box] = await boxes(authedPage.locator('.stagepanel'))
      lefts.push(box.x)
    }
    expect(new Set(lefts).size, `panels start at ${lefts}`).toBe(1)
  })

  test('the rail and the panel below it share an edge', async ({ authedPage }) => {
    await authedPage.goto('/#!/?stage=source')
    const [rail] = await boxes(authedPage.locator('.stagerail'))
    const [panel] = await boxes(authedPage.locator('.stagepanel'))
    expect(panel.x, 'panel does not line up with the rail').toBe(rail.x)
    expect(panel.width).toBe(rail.width)
  })

  test('a disabled action still looks like an action', async ({ authedPage }) => {
    /**
     * The render button is disabled with an empty timeline. It has to remain
     * visible and legible -- an action that vanishes when unavailable reads as
     * a broken page rather than a missing prerequisite, and the panel already
     * says which step is missing.
     */
    await authedPage.goto('/#!/?stage=render')
    const button = authedPage.locator('#queue-render')
    await expect(button).toBeDisabled()
    await expect(button).toBeVisible()

    const [box] = await boxes(button)
    expect(box.width).toBeGreaterThan(40)
    expect(box.height).toBeGreaterThan(20)

    const opacity = await button.evaluate(n => Number(getComputedStyle(n).opacity))
    expect(opacity, 'disabled control is effectively invisible').toBeGreaterThan(0.25)
  })
})

test.describe('the rail works as navigation', () => {
  test('clicking each stage shows its panel', async ({ authedPage }) => {
    await authedPage.goto('/')
    for (const stage of ['source', 'render', 'deliver']) {
      await authedPage.locator(`#stage-${stage}`).click()
      await expect(authedPage.locator(`#panel-${stage}`)).toBeVisible()
    }
    await authedPage.locator('#stage-edit').click()
    // Edit has no panel: it is the timeline, which is always mounted.
    await expect(authedPage.locator('.stagepanel')).toHaveCount(0)
    await expect(authedPage.locator('#timeline')).toBeVisible()
  })

  test('the stages are reachable by keyboard', async ({ authedPage }) => {
    // They are <button>s rather than divs precisely so this works; asserting
    // it stops a later restyle from quietly turning them into unfocusable
    // elements.
    await authedPage.goto('/')
    await authedPage.locator('#stage-source').focus()
    const focused = await authedPage.evaluate(() => document.activeElement.id)
    expect(focused).toBe('stage-source')

    await authedPage.keyboard.press('Enter')
    await expect(authedPage.locator('#panel-source')).toBeVisible()
  })

  test('the rail is announced as a tablist', async ({ authedPage }) => {
    await authedPage.goto('/#!/?stage=render')
    await expect(authedPage.locator('.stagerail')).toHaveAttribute('role', 'tablist')
    await expect(authedPage.locator('#stage-render')).toHaveAttribute(
      'aria-selected',
      'true'
    )
    await expect(authedPage.locator('#stage-source')).toHaveAttribute(
      'aria-selected',
      'false'
    )
  })

  test('the timeline is never displaced by a panel', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * The point of stages-of-one-view. Whichever stage is open, the timeline
     * stays on screen and keeps its clips -- if opening the render settings
     * scrolled the work out of view, these would be four routes wearing a
     * shared header.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const demo = projects.find(p => p.name === 'Timeline demo')
    test.skip(!demo, 'demo project not seeded')

    for (const stage of STAGES) {
      await authedPage.goto(`/#!/?project=${demo._id}&stage=${stage}`)
      await expect(authedPage.locator('#timeline .clip')).toHaveCount(
        demo.edl.clips.length
      )
    }
  })
})

test.describe('the timeline reads as a timeline', () => {
  test('clips sit on one row, in order', async ({ authedPage, request, token }) => {
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const demo = projects.find(p => p.name === 'Timeline demo')
    test.skip(!demo, 'demo project not seeded')

    await authedPage.goto(`/#!/?project=${demo._id}&stage=edit`)
    // Wait before measuring. `evaluateAll` does not retry the way
    // `toHaveCount` does, so reading straight after goto measured an empty
    // timeline and reported undefined widths rather than a layout problem.
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      demo.edl.clips.length
    )
    const clips = await boxes(authedPage.locator('#timeline .clip'))

    // Same row: a timeline whose clips wrap is no longer a timeline.
    expect(new Set(clips.map(c => c.y)).size, 'clips are on different rows').toBe(1)

    // Left to right, in the order the EDL lists them.
    const xs = clips.map(c => c.x)
    expect(xs).toEqual([...xs].sort((a, b) => a - b))
  })

  test('a clip is wider when it is longer', async ({ authedPage, request, token }) => {
    /**
     * Width encodes duration -- that is what makes a timeline readable at a
     * glance. The demo project's clips have different durations, so their
     * widths must differ accordingly.
     */
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const demo = projects.find(p => p.name === 'Timeline demo')
    test.skip(!demo, 'demo project not seeded')

    const durations = demo.edl.clips.map(c => c.duration)
    test.skip(new Set(durations).size < 2, 'demo clips all share a duration')

    await authedPage.goto(`/#!/?project=${demo._id}&stage=edit`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(
      demo.edl.clips.length
    )
    const widths = (await boxes(authedPage.locator('#timeline .clip'))).map(
      b => b.width
    )

    const longest = durations.indexOf(Math.max(...durations))
    const shortest = durations.indexOf(Math.min(...durations))
    expect(
      widths[longest],
      `the ${durations[longest]}s clip is not wider than the ${durations[shortest]}s one`
    ).toBeGreaterThan(widths[shortest])
  })

  test('the media bin and the timeline agree on clip appearance', async ({
    authedPage,
    request,
    token,
  }) => {
    // Both render the same component. A bin entry that looks nothing like the
    // clip it becomes when dragged makes the connection guesswork.
    const projects = await (
      await request.get('/project', { headers: { Authorization: token } })
    ).json()
    const demo = projects.find(p => p.name === 'Timeline demo')
    test.skip(!demo, 'demo project not seeded')

    await authedPage.goto(`/#!/?project=${demo._id}&stage=edit`)
    await expect(authedPage.locator('#bin .clip').first()).toBeVisible()
    await expect(authedPage.locator('#timeline .clip').first()).toBeVisible()

    const styleOf = selector =>
      authedPage
        .locator(selector)
        .first()
        .evaluate(n => {
          const s = getComputedStyle(n)
          return `${s.borderRadius}|${s.fontFamily}`
        })

    // Two different elements, which the first version of this did not do: it
    // compared `#bin .clip` with `#bin .clip` and could only ever pass.
    expect(await styleOf('#timeline .clip')).toBe(await styleOf('#bin .clip'))
  })
})
