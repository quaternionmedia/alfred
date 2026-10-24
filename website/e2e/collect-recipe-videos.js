#!/usr/bin/env node
/**
 * Gather the passing recipes' recordings in docs/recipes, ready to become
 * GIFs.
 *
 * `./al recipes` records the @recipe walkthroughs as video. Each passing
 * recipe's recording is copied here as `docs/recipes/<recipe>.webm`, which
 * git ignores, and listed in `website/recipe-videos.json` with the second its
 * recipe starts at: the recording opens on the login in front of it, which
 * the recipe notes (recipes.spec.js). `scripts/recipe_gifs.py` then turns
 * each into `docs/recipes/<recipe>.gif`. git ignores both: they are
 * published beside the docs, not committed.
 *
 * Only recipes that passed are listed, and every GIF and recording is cleared
 * first: a recipe that breaks leaves no artefact claiming it works.
 */

const fs = require('fs')
const path = require('path')

const WEBSITE = path.join(__dirname, '..')
const OUT = path.join(WEBSITE, '..', 'docs', 'recipes')
const MANIFEST = path.join(WEBSITE, 'recipe-videos.json')

/**
 * Recipe title -> file name.
 *
 * Taken from Playwright's JSON report rather than from its output directory
 * names, which are hashed and truncated -- "choose a project and edit its
 * timeline" arrives on disk as `oject-and-edit-its-timeline`. The report
 * carries the real title and the real attachment path, so the file name can
 * match the recipe the cookbook names.
 */
function slugFor(title) {
  return title
    .replace(/^recipe:\s*/i, '')
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase()
}

/** The second a recording's recipe starts at, as the recipe noted it. */
function startOf(test, result) {
  const notes = [...(result.annotations || []), ...(test.annotations || [])]
  const note = notes.find(annotation => annotation.type === 'recipe-starts')
  const seconds = note ? Number(note.description) : 0
  return Number.isFinite(seconds) && seconds > 0 ? seconds : 0
}

/**
 * The passing recipes' recordings, or null when the run reached no recipe.
 *
 * A run that never got that far -- no stack on the port, so global setup
 * failed -- says nothing about any recipe, and clearing every GIF on its word
 * would delete the lot. A recipe that ran and failed is another matter: its
 * GIF goes.
 */
function videosFromReport(reportPath) {
  const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
  const found = []
  let ran = 0

  const walk = suites => {
    for (const suite of suites || []) {
      for (const spec of suite.specs || []) {
        // The docs project takes the screenshots too; those are not recipes.
        if (!/^recipe:/i.test(spec.title)) continue
        for (const test of spec.tests || []) {
          for (const result of test.results || []) {
            ran += 1
            // Only a recipe that passed gets a GIF. A broken recipe leaving
            // no footage is the point: generating demonstrations from tests is
            // only worth anything if a failing one cannot ship a recording.
            if (result.status !== 'passed') continue
            for (const attachment of result.attachments || []) {
              if (attachment.name === 'video' && attachment.path) {
                found.push({
                  title: spec.title,
                  path: attachment.path,
                  start: startOf(test, result),
                })
              }
            }
          }
        }
      }
      walk(suite.suites)
    }
  }
  walk(report.suites)
  return ran && !(report.errors || []).length ? found : null
}

function main() {
  const reportPath = process.argv[2] || path.join(WEBSITE, 'recipe-report.json')
  // Whatever happens below, no list from an earlier run is left for the
  // converter to work from.
  fs.rmSync(MANIFEST, { force: true })
  if (!fs.existsSync(reportPath)) {
    console.error(`no report at ${reportPath}`)
    console.error('run: npx playwright test --project=docs --reporter=json > recipe-report.json')
    process.exit(1)
  }

  let videos
  try {
    videos = videosFromReport(reportPath)
  } catch {
    videos = null // empty or cut short: the run printed no report
  }
  if (!videos) {
    console.error(`${reportPath} reports no recipe run; docs/recipes is left as it was`)
    process.exit(1)
  }

  fs.mkdirSync(OUT, { recursive: true })

  // Clear stale GIFs and recordings first, so a removed or newly failing
  // recipe leaves nothing behind for the cookbook to keep linking to.
  for (const existing of fs.readdirSync(OUT)) {
    if (/\.(gif|webm|svg)$/.test(existing)) {
      fs.unlinkSync(path.join(OUT, existing))
    }
  }

  const collected = []
  for (const video of videos) {
    if (!fs.existsSync(video.path)) continue
    const slug = slugFor(video.title)
    fs.copyFileSync(video.path, path.join(OUT, `${slug}.webm`))
    collected.push({
      slug,
      start: video.start,
      bytes: fs.statSync(path.join(OUT, `${slug}.webm`)).size,
    })
  }

  collected.sort((a, b) => a.slug.localeCompare(b.slug))
  const listed = { recipes: collected.map(({ slug, start }) => ({ slug, start })) }
  fs.writeFileSync(MANIFEST, JSON.stringify(listed, null, 2) + '\n', 'utf8')
  for (const { slug, start, bytes } of collected) {
    console.log(
      `  ${slug}.webm  ${(bytes / 1024).toFixed(0)} kB, the recipe from ${start.toFixed(2)} s`
    )
  }
  console.log(
    `docs/recipes: ${collected.length} recordings, which git ignores; ` +
      'scripts/recipe_gifs.py makes the GIFs'
  )
}

main()
