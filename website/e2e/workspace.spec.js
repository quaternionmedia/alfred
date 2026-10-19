/**
 * The desktop workspace: the editor's panels docked with Golden Layout.
 *
 * # Recipe: arranging the workspace
 *
 * On a screen 1024 pixels wide or more the editor is a workspace of panels:
 * projects and the library on the left, the viewer above the timeline in the
 * middle, the selected clip's settings and the Render, Deliver and Captions
 * tabs on the right. Drag a tab to move a panel, drag the gaps to resize
 * them, close what you do not need. The arrangement is kept in this browser
 * and comes back on the next visit. The Panels menu brings back a closed
 * panel, in its place, and Reset layout restores the arrangement above.
 *
 * Every panel here is the panel the phone flow stacks (stacked.spec.js);
 * these are about the dock around them.
 */

const {
  test,
  expect,
  login,
  holdTheRouter,
  releaseTheRouter,
  LAYOUT_KEY,
  MEDIA_PROJECT,
  PANEL_IDS,
} = require('./fixtures')

const tab = (page, id) => page.locator(`#paneltab-${id}`)
const body = (page, id) => page.locator(`#panelbody-${id}`)
const menuButton = page => page.locator('#panels-button')
const menuItem = (page, id) => page.locator(`#panels-menu [role="menuitem"][data-panel="${id}"]`)

/** The kept arrangement, parsed, or null. */
const saved = page =>
  page.evaluate(key => {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  }, LAYOUT_KEY)

/** Every panel entry a Golden Layout config holds, depth first. */
function components(config) {
  const found = []
  const walk = item => {
    if (!item || typeof item !== 'object') return
    if (item.type === 'component') found.push(item)
    for (const child of item.content || []) walk(child)
  }
  walk(config && config.root)
  return found
}

/** Open the Panels menu and choose `id` (or `reset-layout`). */
async function fromMenu(page, id) {
  await menuButton(page).click()
  const item = id === 'reset' ? page.locator('#reset-layout') : menuItem(page, id)
  await item.click()
  await expect(page.locator('#panels-menu')).toHaveCount(0)
}

/** Box of `locator`, rounded. */
const box = async locator => {
  const b = await locator.boundingBox()
  return b && { x: b.x, y: b.y, width: b.width, height: b.height }
}

test.describe('the default workspace', () => {
  test('every panel is in it, once, under its registry id', async ({ authedPage }) => {
    /**
     * `findFirstComponentItemById` is how a panel is brought forward, or
     * known to be open rather than opened a second time. A default-layout
     * entry without its id is invisible to it -- in codecartographer that
     * made bringing the canvas forward a no-op and reopening it add a
     * second. Read from what Golden Layout itself saves of the layout it
     * loaded, so it is the layout in use, not a file that could disagree.
     */
    await authedPage.goto('/')
    await expect(tab(authedPage, 'timeline')).toBeVisible()
    await expect.poll(() => saved(authedPage)).not.toBeNull()

    const entries = components(await saved(authedPage))
    // Mutation: drop `id` from panelConfig in default_layout.js -- every
    // entry here has an empty id, and this fails.
    expect(entries.map(e => [e.componentType, e.id])).toEqual(
      entries.map(e => [e.componentType, e.componentType])
    )
    expect(entries.map(e => e.componentType).sort()).toEqual([...PANEL_IDS].sort())

    // And on screen: one tab per panel, each named for it.
    await expect(authedPage.locator('#workspace .lm_tab')).toHaveCount(PANEL_IDS.length)
    for (const id of PANEL_IDS) await expect(tab(authedPage, id)).toHaveCount(1)
  })

  test('the material is on the left, the work in the middle, the rest on the right', async ({
    authedPage,
  }) => {
    /**
     * Where each panel opens on a first visit: the default layout's columns
     * and stacks, measured on the page, not read from the configuration.
     */
    await authedPage.goto('/')
    await expect(body(authedPage, 'viewer')).toBeVisible()
    const at = {}
    for (const id of ['projects', 'media', 'viewer', 'timeline', 'template', 'render']) {
      at[id] = await box(body(authedPage, id))
    }

    expect(at.projects.x).toBeLessThan(at.viewer.x)
    expect(at.viewer.x).toBeLessThan(at.template.x)
    // Projects over the library, the viewer over the timeline, the clip's
    // settings over the render tabs.
    expect(at.projects.y).toBeLessThan(at.media.y)
    expect(at.viewer.y).toBeLessThan(at.timeline.y)
    expect(at.template.y).toBeLessThan(at.render.y)
    // The middle is the widest column: it is the work.
    expect(at.viewer.width).toBeGreaterThan(at.projects.width)
    expect(at.viewer.width).toBeGreaterThan(at.template.width)
    // Render in front of Deliver and Captions.
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'false')
  })

  test('the workspace loads without an error in the console', async ({ page }) => {
    /**
     * Counted from the first load with a session: before it, the page asks
     * the server whether auth is disabled (`GET /users/me`, a 401 when it is
     * not), and the browser reports that refusal in the console whatever the
     * layout. Then a deep link to each stage, and a reload -- a full load of
     * the workspace, saved arrangement and all.
     */
    await login(page)
    const errors = []
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    page.on('pageerror', e => errors.push(String(e)))

    for (const stage of ['source', 'edit', 'render', 'deliver']) {
      await page.goto(`/#!/?stage=${stage}`)
      await expect(tab(page, 'timeline')).toBeVisible()
    }
    await page.reload()
    await expect(tab(page, 'timeline')).toBeVisible()
    await page.waitForTimeout(500)
    expect(errors).toEqual([])
  })
})

test.describe('?stage= in the workspace', () => {
  test('each stage brings its panel to the front', async ({ authedPage }) => {
    /**
     * The stage flow's links -- bookmarks, the rail, the old #!/renders --
     * still land: in the workspace a stage is a panel brought forward, with
     * `Stack.setActiveComponentItem`. (`ComponentItem.focus()` marks an item
     * focused and leaves its stack showing whichever tab it showed.)
     */
    for (const [stage, id] of [
      ['deliver', 'deliver'],
      ['render', 'render'],
      ['source', 'projects'],
      ['edit', 'timeline'],
    ]) {
      await authedPage.goto(`/#!/?stage=${stage}`)
      // Mutation: show a panel with item.focus() -- its tab stays behind, and
      // this fails for Deliver.
      await expect(tab(authedPage, id)).toHaveAttribute('aria-selected', 'true')
      await expect(body(authedPage, id)).toBeVisible()
      await expect(authedPage.locator(`#stage-${stage}`)).toHaveClass(/active/)
    }
    await authedPage.goto('/#!/renders')
    await expect(authedPage).toHaveURL(/stage=deliver/)
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')
  })

  test('the rail brings a stage forward again, even the stage already chosen', async ({
    authedPage,
  }) => {
    /**
     * Choosing the stage already in the address changes nothing in it, and
     * still brings its panel to the front: it may have been put behind another
     * since.
     */
    await authedPage.goto('/#!/?stage=render')
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
    // Another panel in front of Render, then Render chosen again on the rail:
    // the address does not change, and Render comes forward all the same.
    await tab(authedPage, 'captions').click()
    await expect(tab(authedPage, 'captions')).toHaveAttribute('aria-selected', 'true')
    await authedPage.locator('#stage-render').click()
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
  })

  test('choosing a tab says which stage you are on', async ({ authedPage }) => {
    /**
     * A tab chosen writes its panel's stage into the address, replacing the
     * entry rather than adding one, so the rail follows and Back does not walk
     * through every tab chosen.
     */
    await authedPage.goto('/')
    await expect(authedPage.locator('#stage-edit')).toHaveClass(/active/)
    await tab(authedPage, 'deliver').click()
    await expect(authedPage).toHaveURL(/stage=deliver/)
    await expect(authedPage.locator('#stage-deliver')).toHaveClass(/active/)
    // The tab chosen stays chosen: the stage does not bring Render back over it.
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')
  })

  test('a tab chosen stays in front while the address catches up', async ({ authedPage }) => {
    /**
     * Choosing a tab writes its stage into the address, which the router reads
     * back a moment later. A redraw in that moment brought the stage from
     * before back over the tab just chosen: Render in front again, the rail on
     * Edit, until something else was chosen. On a loaded machine the rail
     * test above did this in one run of ten to twenty; here the moment is
     * held open and a redraw put in it, so it would happen every time.
     */
    await authedPage.goto('/#!/?stage=render')
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
    await holdTheRouter(authedPage)

    await tab(authedPage, 'captions').click()
    // A redraw before the router has read the address back.
    await menuButton(authedPage).click()
    await expect(authedPage.locator('#panels-menu')).toBeVisible()
    // Mutation: read the stage from `m.route.param()` in followRoute -- the
    // redraw brings Render back over Captions, and this fails.
    await expect(tab(authedPage, 'captions')).toHaveAttribute('aria-selected', 'true')
    await authedPage.keyboard.press('Escape')

    await releaseTheRouter(authedPage)
    await expect(authedPage.locator('#stage-edit')).toHaveClass(/active/)
    await expect(tab(authedPage, 'captions')).toHaveAttribute('aria-selected', 'true')
  })

  test('the address follows the last tab chosen, however quick', async ({ authedPage }) => {
    /**
     * Two tabs chosen before the router has read the first back: the address
     * names the second one's stage, as the rail does. Render chosen after
     * Captions was taken for the stage the route still said -- Render, from
     * before -- and never written, so the address and the rail stayed on
     * Captions' Edit while Render was in front.
     */
    await authedPage.goto('/#!/?stage=render')
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
    await holdTheRouter(authedPage)

    await tab(authedPage, 'captions').click()
    await tab(authedPage, 'render').click()
    await releaseTheRouter(authedPage)
    // Mutation: ask `Flow.stage()` whether the address already names the
    // tab's stage -- it answers from before, Render is not written, and this
    // fails.
    await expect(authedPage).toHaveURL(/stage=render/)
    await expect(authedPage.locator('#stage-render')).toHaveClass(/active/)
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
  })

  test('Back and Forward bring the stage forward', async ({ authedPage }) => {
    /**
     * A stage chosen on the rail is a page visited: Back returns to the stage
     * before, with its panel in front, and Forward to the one after. (A tab
     * chosen replaces the address rather than adding to it.)
     */
    await authedPage.goto('/#!/?stage=render')
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
    await authedPage.locator('#stage-deliver').click()
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')

    await authedPage.goBack()
    await expect(authedPage).toHaveURL(/stage=render/)
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
    await expect(authedPage.locator('#stage-render')).toHaveClass(/active/)

    await authedPage.goForward()
    await expect(authedPage).toHaveURL(/stage=deliver/)
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')
    await expect(authedPage.locator('#stage-deliver')).toHaveClass(/active/)
  })
})

test.describe('the arrangement is kept', () => {
  test('a closed panel and a chosen tab survive a reload', async ({ authedPage }) => {
    /**
     * Closing a panel and choosing a tab are kept in this browser
     * (localStorage, `alfred.layout.v1`), and are what the next visit opens
     * with.
     */
    await authedPage.goto('/')
    await tab(authedPage, 'captions').locator('.lm_close_tab').click()
    await expect(tab(authedPage, 'captions')).toHaveCount(0)
    await tab(authedPage, 'deliver').click()
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')
    await expect
      .poll(async () => components(await saved(authedPage)).map(e => e.componentType))
      .not.toContain('captions')

    // Without a stage in the address, so nothing but the kept arrangement
    // decides which tab is in front.
    await authedPage.goto('/#!/')
    await authedPage.reload()
    await expect(tab(authedPage, 'timeline')).toBeVisible()
    await expect(tab(authedPage, 'captions')).toHaveCount(0)
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')
  })

  test('a panel dragged by its tab to another stack stays there', async ({ authedPage }) => {
    /**
     * Golden Layout's own move: the Captions tab dragged onto the Projects
     * stack's tab strip joins it, comes to the front there, draws, and is
     * there after a reload.
     */
    await authedPage.goto('/')
    const from = await box(tab(authedPage, 'captions'))
    const strip = await box(authedPage.locator('#workspace .lm_header', { has: tab(authedPage, 'projects') }))
    const start = { x: from.x + from.width / 2 - 8, y: from.y + from.height / 2 }
    await authedPage.mouse.move(start.x, start.y)
    await authedPage.mouse.down()
    await authedPage.mouse.move(start.x + 12, start.y + 6, { steps: 4 })
    await authedPage.mouse.move(strip.x + strip.width - 40, strip.y + strip.height / 2, { steps: 24 })
    await authedPage.mouse.up()

    const shared = authedPage.locator('#workspace .lm_tabs', { has: tab(authedPage, 'captions') })
    await expect(shared.locator('#paneltab-projects')).toHaveCount(1)
    await expect(tab(authedPage, 'captions')).toHaveAttribute('aria-selected', 'true')
    await expect(authedPage.locator('#panel-captions')).toBeVisible()
    await expect(authedPage.locator('#workspace .lm_tab[data-panel="captions"]')).toHaveCount(1)

    await expect
      .poll(async () => {
        const stacks = []
        const walk = item => {
          if (!item) return
          if (item.type === 'stack') stacks.push(item.content.map(c => c.componentType))
          for (const child of item.content || []) walk(child)
        }
        walk((await saved(authedPage)).root)
        return stacks.some(ids => ids.includes('captions') && ids.includes('projects'))
      })
      .toBe(true)
    await authedPage.goto('/#!/')
    await authedPage.reload()
    await expect(authedPage.locator('#workspace .lm_tabs', { has: tab(authedPage, 'captions') }).locator('#paneltab-projects')).toHaveCount(1)
  })

  test('a resized panel keeps its size across a reload', async ({ authedPage }) => {
    /**
     * Dragging the gap between two panels resizes them, and the sizes are kept
     * with the arrangement.
     */
    await authedPage.goto('/')
    const before = await box(body(authedPage, 'viewer'))

    // The gap under the viewer, dragged down.
    const splitter = authedPage
      .locator('#workspace .lm_splitter.lm_vertical')
      .filter({ has: authedPage.locator('.lm_drag_handle') })
    const gaps = await splitter.evaluateAll(nodes =>
      nodes.map(n => {
        const r = n.getBoundingClientRect()
        return { x: r.x, y: r.y, width: r.width, height: r.height }
      })
    )
    const viewerBottom = before.y + before.height
    const gap = gaps.find(
      g => g.x <= before.x + 5 && g.x + g.width >= before.x + before.width - 5 && Math.abs(g.y - viewerBottom) < 20
    )
    expect(gap, 'no gap found under the viewer').toBeTruthy()
    await authedPage.mouse.move(gap.x + gap.width / 2, gap.y + gap.height / 2)
    await authedPage.mouse.down()
    await authedPage.mouse.move(gap.x + gap.width / 2, gap.y + gap.height / 2 + 60, { steps: 8 })
    await authedPage.mouse.up()
    await expect.poll(async () => (await box(body(authedPage, 'viewer'))).height).toBeGreaterThan(before.height + 30)
    const resized = await box(body(authedPage, 'viewer'))

    await authedPage.waitForTimeout(500)
    await authedPage.reload()
    await expect(body(authedPage, 'viewer')).toBeVisible()
    await expect
      .poll(async () => Math.round((await box(body(authedPage, 'viewer'))).height))
      .toBeGreaterThan(Math.round(resized.height) - 3)
  })

  for (const [name, corrupt] of [
    ['text that is not JSON', '{not json'],
    ['JSON that is not a layout', '[1, 2, 3]'],
    [
      'a panel this version does not have',
      JSON.stringify({
        root: {
          type: 'row',
          content: [
            { type: 'component', componentType: 'timeline', id: 'timeline', title: 'Timeline' },
            { type: 'component', componentType: 'a-panel-nobody-registered', id: 'a-panel-nobody-registered' },
          ],
        },
      }),
    ],
    [
      'a panel without its id',
      JSON.stringify({
        root: {
          type: 'stack',
          content: [
            { type: 'component', componentType: 'timeline', id: 'timeline' },
            { type: 'component', componentType: 'deliver' },
          ],
        },
      }),
    ],
    [
      'a panel twice',
      JSON.stringify({
        root: {
          type: 'stack',
          content: [
            { type: 'component', componentType: 'timeline', id: 'timeline' },
            { type: 'component', componentType: 'deliver', id: 'deliver' },
            { type: 'component', componentType: 'deliver', id: 'deliver' },
          ],
        },
      }),
    ],
    [
      'no timeline',
      JSON.stringify({
        root: { type: 'stack', content: [{ type: 'component', componentType: 'deliver', id: 'deliver' }] },
      }),
    ],
  ]) {
    test(`a saved arrangement holding ${name} gives way to the default`, async ({ page }) => {
      /**
       * Golden Layout throws on a panel nobody registered, and a panel without
       * its id, or shown twice, breaks finding a panel by id. Each is caught
       * before Golden Layout sees it: the default loads instead, and the
       * viewer is told why.
       */
      const errors = []
      page.on('pageerror', e => errors.push(String(e)))
      await page.addInitScript(
        ({ key, value }) => {
          // Once per test, not on every navigation: the check below reads the
          // key back after the page has had its chance to replace it.
          if (sessionStorage.getItem('seeded')) return
          sessionStorage.setItem('seeded', '1')
          localStorage.setItem(key, value)
        },
        { key: LAYOUT_KEY, value: corrupt }
      )
      await login(page)

      // Mutation: load the saved text without the check -- Golden Layout
      // throws on it or loads it as it is, and this fails.
      for (const id of PANEL_IDS) await expect(tab(page, id)).toHaveCount(1)
      await expect(page.locator('.ajs-message').filter({ hasText: /could not be used/ })).toBeVisible()
      expect(errors).toEqual([])
      expect(await page.evaluate(key => localStorage.getItem(key), LAYOUT_KEY)).not.toBe(corrupt)
    })
  }

  test('a saved arrangement naming only its own panels is loaded as saved', async ({ page }) => {
    /**
     * The check refuses only what cannot be used: a valid arrangement, however
     * unlike the default, is the one that opens.
     */
    const arrangement = {
      root: {
        type: 'row',
        content: [
          { type: 'component', componentType: 'timeline', id: 'timeline', title: 'Timeline' },
          {
            type: 'stack',
            content: [
              { type: 'component', componentType: 'viewer', id: 'viewer', title: 'Viewer' },
              { type: 'component', componentType: 'deliver', id: 'deliver', title: 'Deliver' },
            ],
          },
        ],
      },
    }
    await page.addInitScript(
      ({ key, value }) => {
        if (sessionStorage.getItem('seeded')) return
        sessionStorage.setItem('seeded', '1')
        localStorage.setItem(key, value)
      },
      { key: LAYOUT_KEY, value: JSON.stringify(arrangement) }
    )
    await login(page)

    await expect(tab(page, 'deliver')).toHaveCount(1)
    await expect(tab(page, 'viewer')).toHaveCount(1)
    // The default's other panels are absent: this is the saved arrangement.
    await expect(tab(page, 'projects')).toHaveCount(0)
    await expect(tab(page, 'template')).toHaveCount(0)
  })
})

test.describe('the Panels menu', () => {
  test('a closed panel comes back once, in its place', async ({ authedPage }) => {
    /**
     * The Panels menu says which panels are closed. Choosing one brings it
     * back beside the panels it shares a stack with by default; choosing it
     * again, or its stage, brings it forward -- found by its id -- and never
     * adds a second.
     */
    await authedPage.goto('/#!/?stage=deliver')
    await expect(authedPage.locator('#panel-deliver')).toBeVisible()
    await tab(authedPage, 'deliver').locator('.lm_close_tab').click()
    await expect(tab(authedPage, 'deliver')).toHaveCount(0)
    // Closed is gone, not hidden: its Mithril root is unmounted with it
    // (Golden Layout's beforeComponentRelease), so nothing of it is drawn or
    // still asking the server for the render list.
    await expect(authedPage.locator('#panel-deliver')).toHaveCount(0)
    await expect(authedPage.locator('.panelhost--deliver')).toHaveCount(0)

    await menuButton(authedPage).click()
    await expect(menuItem(authedPage, 'deliver')).toContainText('closed')
    await menuItem(authedPage, 'deliver').click()
    await expect(tab(authedPage, 'deliver')).toHaveCount(1)
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')
    // Back beside Render, where it was: one tab strip holds both.
    const strip = authedPage.locator('#workspace .lm_tabs', { has: tab(authedPage, 'deliver') })
    await expect(strip.locator('#paneltab-render')).toHaveCount(1)

    // Chosen again, and again by its stage: brought forward, never doubled.
    // Mutation: add a panel without first looking for it by id -- a second
    // Deliver appears, and this fails.
    await tab(authedPage, 'render').click()
    await fromMenu(authedPage, 'deliver')
    await authedPage.goto('/#!/?stage=deliver')
    await expect(authedPage.locator('#workspace .lm_tab[data-panel="deliver"]')).toHaveCount(1)
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')
    await expect(authedPage.locator('#panel-deliver')).toHaveCount(1)
  })

  test('a stage whose panel was closed opens it again', async ({ authedPage }) => {
    /**
     * A rail click or a stage link whose panel is closed reopens it in its
     * place: the project list over the library, though closing it had folded
     * their column away.
     */
    await authedPage.goto('/')
    await tab(authedPage, 'projects').locator('.lm_close_tab').click()
    await expect(tab(authedPage, 'projects')).toHaveCount(0)
    await authedPage.locator('#stage-source').click()
    await expect(tab(authedPage, 'projects')).toHaveCount(1)
    await expect(authedPage.locator('#panel-source')).toBeVisible()
    // Above the library, as it was.
    const projects = await box(body(authedPage, 'projects'))
    const media = await box(body(authedPage, 'media'))
    expect(projects.y).toBeLessThan(media.y)
    expect(Math.abs(projects.x - media.x)).toBeLessThan(2)
  })

  test('Reset layout restores the default, and keeps the work', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Golden Layout builds every panel again when it loads a layout. The
     * panels are drawn in boxes the layout moves, so the timeline is not
     * fetched again: a clip added and not saved is still there afterwards,
     * and no draft is offered back.
     */
    await request.post('/demo/media', { headers: { Authorization: token } })
    await authedPage.goto('/#!/?stage=source')
    await authedPage.locator('.mediachoice').first().click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)

    await tab(authedPage, 'captions').locator('.lm_close_tab').click()
    await tab(authedPage, 'template').locator('.lm_close_tab').click()
    await expect(tab(authedPage, 'template')).toHaveCount(0)

    await fromMenu(authedPage, 'reset')
    for (const id of PANEL_IDS) await expect(tab(authedPage, id)).toHaveCount(1)
    await expect(tab(authedPage, 'render')).toHaveAttribute('aria-selected', 'true')
    // Mutation: erase every panel when the layout is reloaded -- the timeline
    // starts over, empty, and this fails.
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(1)
    await expect(authedPage.locator('#draft-offer')).toHaveCount(0)
    // The focus goes back to the menu's button.
    await expect(menuButton(authedPage)).toBeFocused()
  })

  test('the menu and the tabs work from the keyboard', async ({ authedPage }) => {
    /**
     * The Panels menu is a menu button: Enter or the arrow keys open it on an
     * item, the arrow keys move along it, Escape closes it and returns the
     * focus. Golden Layout's tabs are given roles: a tablist per stack, tabs
     * named for their panels, one tab stop per strip, the arrow keys along it,
     * Enter to show a panel and Delete to close it.
     */
    await authedPage.goto('/')
    await menuButton(authedPage).focus()
    await authedPage.keyboard.press('Enter')
    await expect(authedPage.locator('#panels-menu')).toBeVisible()
    await expect(menuButton(authedPage)).toHaveAttribute('aria-expanded', 'true')
    await expect(menuItem(authedPage, 'projects')).toBeFocused()
    await authedPage.keyboard.press('ArrowDown')
    await expect(menuItem(authedPage, 'media')).toBeFocused()
    await authedPage.keyboard.press('Escape')
    await expect(authedPage.locator('#panels-menu')).toHaveCount(0)
    await expect(menuButton(authedPage)).toBeFocused()

    // A tab is a tab: named, selected or not, and the arrow keys move along
    // its strip, Enter chooses, Delete closes.
    const render = tab(authedPage, 'render')
    await expect(render).toHaveAttribute('role', 'tab')
    await expect(render).toHaveAttribute('aria-controls', 'panelbody-render')
    await expect(authedPage.locator('#panelbody-render')).toHaveAttribute('role', 'tabpanel')
    await expect(authedPage.getByRole('tab', { name: 'Deliver', exact: true })).toHaveCount(1)
    await render.focus()
    await authedPage.keyboard.press('ArrowRight')
    await expect(tab(authedPage, 'deliver')).toBeFocused()
    await authedPage.keyboard.press('Enter')
    await expect(tab(authedPage, 'deliver')).toHaveAttribute('aria-selected', 'true')
    await expect(render).toHaveAttribute('aria-selected', 'false')
    await authedPage.keyboard.press('Delete')
    await expect(tab(authedPage, 'deliver')).toHaveCount(0)
  })
})

test.describe('the viewer keeps its shape', () => {
  // The frame's box, and its room's.
  const frame = async page => ({
    frame: await box(page.locator('#head')),
    room: await box(page.locator('.viewerframe')),
  })

  const ratio = b => b.width / b.height

  test('resizing the panel resizes the picture, never reshapes it', async ({ authedPage }) => {
    /**
     * The frame is the largest rectangle of the output's aspect that fits its
     * panel: a larger window makes it larger and the same shape, and an
     * upright output makes it upright.
     */
    await authedPage.goto('/')
    await expect(authedPage.locator('#head')).toBeVisible()
    await expect(authedPage.locator('#aspect')).toHaveValue('16:9')

    const first = await frame(authedPage)
    // Mutation: size the frame from the window as before -- it is no longer
    // the output's shape in a panel, and this fails.
    expect(ratio(first.frame)).toBeCloseTo(16 / 9, 1)
    expect(first.frame.width).toBeLessThanOrEqual(first.room.width + 1)
    expect(first.frame.height).toBeLessThanOrEqual(first.room.height + 1)

    // A wider window: every panel grows, the frame with them, the same shape.
    await authedPage.setViewportSize({ width: 1600, height: 900 })
    await expect.poll(async () => (await box(authedPage.locator('#head'))).width).toBeGreaterThan(first.frame.width + 20)
    const wider = await frame(authedPage)
    expect(ratio(wider.frame)).toBeCloseTo(16 / 9, 1)
    expect(wider.frame.height).toBeLessThanOrEqual(wider.room.height + 1)

    // An upright output in the same room: taller than wide.
    await authedPage.locator('#aspect').selectOption('9:16')
    await expect.poll(async () => ratio(await box(authedPage.locator('#head')))).toBeCloseTo(9 / 16, 1)
  })
})

test.describe('the frame takes overlays', () => {
  test('the frame is positioned, and the picture fills it', async ({ authedPage }) => {
    /**
     * What is drawn over the picture -- the caption under the playhead -- is
     * placed against the frame (`viewerOverlays`, panels/Viewer.js), so the
     * frame is positioned and the preview fills it, with nothing else in
     * between.
     */
    await authedPage.goto('/')
    const head = authedPage.locator('#head')
    await expect(head).toBeVisible()
    expect(await head.evaluate(n => getComputedStyle(n).position)).toBe('relative')

    const frame = await box(head)
    const picture = await box(head.locator('#preview'))
    // Inside the frame's 3px border, and the whole of it.
    expect(picture.x).toBeGreaterThanOrEqual(frame.x)
    expect(picture.y).toBeGreaterThanOrEqual(frame.y)
    expect(picture.width).toBeGreaterThanOrEqual(frame.width - 8)
    expect(picture.height).toBeGreaterThanOrEqual(frame.height - 8)
  })
})

test.describe('the workspace and the phone flow', () => {
  test('narrowing the window swaps one for the other, and the work stays', async ({
    authedPage,
    request,
    token,
  }) => {
    /**
     * Below 1024 pixels the workspace gives way to the phone flow, and comes
     * back above it, with the same panels: an unsaved clip is still on the
     * timeline either way, and nothing is offered back as a draft.
     */
    const projects = await (await request.get('/project', { headers: { Authorization: token } })).json()
    const project = projects.find(p => p.name === MEDIA_PROJECT)
    expect(project, `${MEDIA_PROJECT} is missing; global-setup.js creates it`).toBeTruthy()

    await authedPage.goto(`/#!/?project=${project._id}&stage=source`)
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length)
    await authedPage.locator('.mediachoice').first().click()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length + 1)

    await authedPage.setViewportSize({ width: 390, height: 844 })
    await expect(authedPage.locator('#workspace')).toHaveCount(0)
    await expect(authedPage.locator('.stagerail')).toBeVisible()
    // Mutation: build the panels again on the way -- the timeline is fetched
    // again, the unsaved clip becomes a draft offered back, and this fails.
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length + 1)
    await expect(authedPage.locator('#draft-offer')).toHaveCount(0)

    await authedPage.setViewportSize({ width: 1280, height: 720 })
    await expect(tab(authedPage, 'timeline')).toBeVisible()
    await expect(authedPage.locator('#timeline .clip')).toHaveCount(project.edl.clips.length + 1)
  })
})
