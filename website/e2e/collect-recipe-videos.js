#!/usr/bin/env node
/**
 * Write a placeholder for each recipe that recorded cleanly.
 *
 * `./al recipes` records the @recipe walkthroughs as video. Those recordings
 * are worth having locally -- to watch, and as the raw material for a polished
 * version -- but they are multi-megabyte binaries that regenerate on demand,
 * and committing them grows the repository permanently for something nobody
 * needs from git. They are ignored; this writes a small SVG stub in their
 * place.
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
const RESULTS = path.join(WEBSITE, 'test-results')
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

function videosFromReport(reportPath) {
  const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
  const found = []

  const walk = suites => {
    for (const suite of suites || []) {
      for (const spec of suite.specs || []) {
        for (const test of spec.tests || []) {
          for (const result of test.results || []) {
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
  return found
}

/** Escape the few characters that would break the SVG. */
function xml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** A placeholder card naming the recipe a polished recording is pending for. */
function stubFor(title) {
  const heading = xml(title.replace(/^recipe:\s*/i, ''))
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 200" role="img"
     aria-label="Recording pending: ${heading}">
  <rect width="640" height="200" rx="6" fill="#161616" stroke="#2e2e2e"/>
  <g transform="translate(40 78)">
    <circle cx="14" cy="14" r="14" fill="none" stroke="#f2aa4c" stroke-width="2"/>
    <path d="M10 7 L22 14 L10 21 Z" fill="#f2aa4c"/>
  </g>
  <text x="90" y="88" fill="#e6e6e6" font-family="system-ui, sans-serif" font-size="19">${heading}</text>
  <text x="90" y="114" fill="#8f8f8f" font-family="system-ui, sans-serif" font-size="13">Polished recording pending — run ./al recipes to watch the current one</text>
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

  fs.mkdirSync(OUT, { recursive: true })

  // Clear stale recordings, so a removed or newly failing recipe does not
  // leave its video behind for the cookbook to keep linking to.
  for (const existing of fs.readdirSync(OUT).filter(f => f.endsWith('.svg'))) {
    fs.unlinkSync(path.join(OUT, existing))
  }

  const collected = []
  for (const video of videosFromReport(reportPath)) {
    if (!fs.existsSync(video.path)) continue
    const slug = slugFor(video.title)
    const name = `${slug}.svg`
    fs.writeFileSync(path.join(OUT, name), stubFor(video.title), 'utf8')
    collected.push({ name, bytes: fs.statSync(path.join(OUT, name)).size })
  }

  collected.sort((a, b) => a.name.localeCompare(b.name))
  for (const video of collected) {
    console.log(`  ${video.name}  ${(video.bytes / 1024).toFixed(0)} kB`)
  }
  console.log(`${OUT}: ${collected.length} stubs`)
}

main()
