#!/usr/bin/env node
/**
 * For each recipe that recorded cleanly, a stub to commit and the recording to
 * keep locally, side by side in docs/recipes.
 *
 * `./al recipes` records the @recipe walkthroughs as video. Those recordings
 * are worth having locally -- to watch, and as the raw material for a polished
 * version -- but they are multi-megabyte binaries that regenerate on demand,
 * and committing them grows the repository permanently for something nobody
 * needs from git. So each is copied here under its recipe's name, where
 * .gitignore keeps it out, and a small SVG stub is written beside it to be
 * committed in its place. The cookbook links what git tracks: the stub.
 *
 * A stub rather than a poster frame lifted from the recording: the recordings
 * are test runs, not demonstrations. A still from one would look like the
 * finished thing while being a screenshot of a robot clicking. The stub says
 * plainly that a polished recording is pending, and names the recipe it is
 * pending for.
 *
 * SVG because it is text: a few hundred bytes, diffable, scalable, and it
 * renders in mkdocs without a plugin.
 *
 * Only recipes that passed get a stub, and stale ones are cleared first -- a
 * recipe that breaks should leave no artefact claiming it works.
 */

const fs = require('fs')
const path = require('path')

const WEBSITE = path.join(__dirname, '..')
const OUT = path.join(WEBSITE, '..', 'docs', 'recipes')

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

/**
 * The passing recipes' recordings, or null when the run reached no recipe.
 *
 * A run that never got that far -- no stack on the port, so global setup
 * failed -- says nothing about any recipe, and clearing every stub on its
 * word would delete the lot. A recipe that ran and failed is another matter:
 * its stub goes.
 */
function videosFromReport(reportPath) {
  const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
  const found = []
  let ran = 0

  const walk = suites => {
    for (const suite of suites || []) {
      for (const spec of suite.specs || []) {
        for (const test of spec.tests || []) {
          for (const result of test.results || []) {
            ran += 1
            // Only a recipe that passed gets a video. A broken recipe leaving
            // no footage is the point: generating demonstrations from tests is
            // only worth anything if a failing one cannot ship a recording.
            if (result.status !== 'passed') continue
            for (const attachment of result.attachments || []) {
              if (attachment.name === 'video' && attachment.path) {
                found.push({ title: spec.title, path: attachment.path })
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

/** Escape what would break the SVG, its attribute values included. */
function xml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * A placeholder card naming the recipe a polished recording is pending for.
 *
 * Nothing in it but the recipe's title and fixed text: no path, date or
 * machine, so recording the same recipes anywhere writes the same bytes, and
 * a stub's diff is only ever a recipe renamed, added or gone. The width and
 * height give it a size of its own where the cookbook shows it as an image.
 */
function stubFor(title) {
  const heading = xml(title.replace(/^recipe:\s*/i, ''))
  return `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="200" viewBox="0 0 640 200"
     role="img" aria-label="Recording pending: ${heading}">
  <rect width="640" height="200" rx="6" fill="#161616" stroke="#2e2e2e"/>
  <g transform="translate(40 78)">
    <circle cx="14" cy="14" r="14" fill="none" stroke="#f2aa4c" stroke-width="2"/>
    <path d="M10 7 L22 14 L10 21 Z" fill="#f2aa4c"/>
  </g>
  <text x="90" y="88" fill="#e6e6e6" font-family="system-ui, sans-serif" font-size="19">${heading}</text>
  <text x="90" y="114" fill="#8f8f8f" font-family="system-ui, sans-serif" font-size="13">A polished recording is pending. ./al recipes records the current one.</text>
</svg>
`
}

function main() {
  const reportPath = process.argv[2] || path.join(WEBSITE, 'recipe-report.json')
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

  // Clear stale stubs and recordings first, so a removed or newly failing
  // recipe leaves nothing behind for the cookbook to keep linking to.
  for (const existing of fs.readdirSync(OUT)) {
    if (existing.endsWith('.svg') || existing.endsWith('.webm')) {
      fs.unlinkSync(path.join(OUT, existing))
    }
  }

  const collected = []
  for (const video of videos) {
    if (!fs.existsSync(video.path)) continue
    const slug = slugFor(video.title)
    fs.writeFileSync(path.join(OUT, `${slug}.svg`), stubFor(video.title), 'utf8')
    fs.copyFileSync(video.path, path.join(OUT, `${slug}.webm`))
    collected.push({ slug, bytes: fs.statSync(path.join(OUT, `${slug}.webm`)).size })
  }

  collected.sort((a, b) => a.slug.localeCompare(b.slug))
  for (const { slug, bytes } of collected) {
    console.log(`  ${slug}.svg, ${slug}.webm  ${(bytes / 1024).toFixed(0)} kB`)
  }
  console.log(
    `docs/recipes: ${collected.length} stubs to commit, and their recordings, ` +
      'which git ignores'
  )
}

main()
