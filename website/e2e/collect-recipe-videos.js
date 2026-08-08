#!/usr/bin/env node
/**
 * Move the recordings the `docs` project produced into the documentation.
 *
 * Playwright names its output directories after the test title, hashed and
 * truncated -- `recipes--recipe-walkthroug-f832c-line-and-deliver-the-result-docs`
 * -- which is fine for a report and useless in a docs site. This copies each
 * `video.webm` to a name derived from the recipe it demonstrates, so the
 * cookbook can link to it.
 *
 * Run after `playwright test --project=docs`; `./al recipes` does both.
 *
 * Only the recordings that exist are copied. A recipe that failed leaves no
 * video, and that is deliberate: the point of generating demonstrations from
 * tests is that a broken recipe has no footage rather than stale footage.
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
  for (const existing of fs.readdirSync(OUT).filter(f => f.endsWith('.webm'))) {
    fs.unlinkSync(path.join(OUT, existing))
  }

  const collected = []
  for (const video of videosFromReport(reportPath)) {
    if (!fs.existsSync(video.path)) continue
    const name = `${slugFor(video.title)}.webm`
    fs.copyFileSync(video.path, path.join(OUT, name))
    collected.push({ name, bytes: fs.statSync(video.path).size })
  }

  collected.sort((a, b) => a.name.localeCompare(b.name))
  for (const video of collected) {
    console.log(`  ${video.name}  ${(video.bytes / 1024).toFixed(0)} kB`)
  }
  console.log(`${OUT}: ${collected.length} recordings`)
}

main()
