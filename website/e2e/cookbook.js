#!/usr/bin/env node
/**
 * Turn the end-to-end suite into the cookbook.
 *
 * The docs, the tests and the recipes are meant to be one object rather than
 * three that drift apart. Prose describing behaviour goes stale silently;
 * a test describing behaviour goes red. So the prose is generated from the
 * tests, and the only way to change the documentation is to change something
 * that runs.
 *
 * What it reads:
 *   - the block comment at the top of each spec, as the section's introduction
 *   - each `test.describe(...)` title, as a heading
 *   - each `test(...)` title, as a step
 *   - a test's own leading comment, as the note under that step
 *
 * Deliberately a parser rather than a Playwright reporter. A reporter would
 * only describe the tests that ran, on the machine that ran them, so the
 * cookbook would quietly shrink whenever something was skipped -- and the
 * governance question this is meant to answer is "what does this project claim
 * to do", which is a property of the suite, not of one run.
 *
 * Usage:  node e2e/cookbook.js [outfile]
 * Default outfile: ../docs/cookbook.md
 */

const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')

const E2E_DIR = __dirname
const REPO = path.join(E2E_DIR, '..', '..')
const DEFAULT_OUT = path.join(REPO, 'docs', 'cookbook.md')

/** Strip comment punctuation without touching the prose inside. */
function cleanBlock(raw) {
  return raw
    .split('\n')
    .map(line => line.replace(/^\s*\/\*\*?/, '').replace(/\*\/\s*$/, '').replace(/^\s*\*ic?\s?/, '').replace(/^\s*\*\s?/, ''))
    .join('\n')
    .trim()
}

function cleanLineComments(raw) {
  return raw
    .split('\n')
    .map(line => line.replace(/^\s*\/\/\s?/, ''))
    .join('\n')
    .trim()
}

/** The block comment at the very top of a file, if there is one. */
function fileIntro(source) {
  const match = source.match(/^\s*\/\*\*([\s\S]*?)\*\//)
  return match ? cleanBlock(match[0]) : ''
}

/**
 * The comment immediately preceding an offset, whether block or line style.
 * Returns '' when the preceding lines are code.
 */
function commentBefore(source, offset) {
  const before = source.slice(0, offset).split('\n')
  const collected = []

  for (let i = before.length - 1; i >= 0; i--) {
    const line = before[i].trim()
    if (line === '') {
      if (collected.length) break
      continue
    }
    if (line.startsWith('//')) {
      collected.unshift(line)
      continue
    }
    break
  }
  if (collected.length) return cleanLineComments(collected.join('\n'))
  return ''
}

/** A test's own leading docblock, which sits inside the callback. */
function docblockInside(source, offset) {
  const after = source.slice(offset, offset + 1400)
  const match = after.match(/=>\s*\{\s*(\/\*\*[\s\S]*?\*\/)/)
  return match ? cleanBlock(match[1]) : ''
}

function parseSpec(file) {
  const source = fs.readFileSync(file, 'utf8')
  const entries = []
  const pattern =
    /(test\.describe|test)\s*(?:\.\w+)?\s*\(\s*(['"`])((?:\\.|(?!\2)[\s\S])*?)\2/g

  let match
  while ((match = pattern.exec(source)) !== null) {
    const [, kind, , title] = match
    entries.push({
      kind: kind === 'test.describe' ? 'group' : 'step',
      // Parameterised titles carry `${...}` straight from the template
      // literal. Left raw they read as broken markdown, so the expression
      // becomes a placeholder naming what varies.
      title: title.replace(/\\'/g, "'").replace(/\$\{([^}]*)\}/g, (_, expr) => {
        const name = expr.split('.')[0].trim()
        return `<${name}>`
      }),
      note: docblockInside(source, match.index) || commentBefore(source, match.index),
    })
  }

  return {
    name: path.basename(file),
    intro: fileIntro(source),
    entries,
  }
}

const RECIPE_DIR = path.join(REPO, 'docs', 'recipes')

/**
 * The GIFs in docs/recipes that a clean checkout has.
 *
 * The cookbook is committed, so it may only link what is committed with it.
 * `./al recipes` writes a GIF per passing recipe beside its recording, and
 * the recordings are ignored: asking the directory would link a file that
 * exists on one machine, and the committed cookbook would then depend on it.
 * So git is asked what it tracks, and a file counts only while it is also on
 * disk -- a GIF cleared because its recipe failed stops being linked at once,
 * rather than when the deletion is committed.
 *
 * Without git (an exported tree, say) the directory is all there is.
 */
function recipeFiles() {
  const present = fs.existsSync(RECIPE_DIR)
    ? fs.readdirSync(RECIPE_DIR).filter(file => file.endsWith('.gif'))
    : []
  let tracked
  try {
    tracked = execFileSync('git', ['ls-files', '-z', '--', 'docs/recipes'], {
      cwd: REPO,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    })
      .split('\0')
      .filter(Boolean)
      .map(file => path.posix.basename(file))
  } catch {
    tracked = present
  }
  return new Set(tracked.filter(file => present.includes(file)))
}

function slugFor(title) {
  return title
    .replace(/^recipe:\s*/i, '')
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase()
}

/** What the cookbook shows under a recipe: its GIF, once one is committed. */
function artefactFor(title, files) {
  const slug = slugFor(title)
  if (!files.has(`${slug}.gif`)) return null
  const name = title.replace(/^recipe:\s*/i, '').replace(/[[\]]/g, '\\$&')
  return `![${name}](recipes/${slug}.gif)`
}

function render(specs, files) {
  const out = []
  out.push('# Cookbook')
  out.push('')
  out.push(
    'Generated from the end-to-end suite by `website/e2e/cookbook.js`. Do not',
    'edit by hand -- change the tests instead, and regenerate.',
    ''
  )
  out.push(
    'Every recipe below is a test that runs against a real stack: a real',
    'database, a real render worker, and real files on disk. If a step here is',
    'wrong, a test is failing. That is the point -- prose describing behaviour',
    'goes stale silently, and a test describing behaviour goes red.',
    ''
  )

  for (const spec of specs) {
    if (!spec.entries.length) continue
    out.push(`## ${spec.name.replace(/\.spec\.js$/, '').replace(/[-_]/g, ' ')}`)
    out.push('')
    if (spec.intro) {
      out.push(spec.intro)
      out.push('')
    }

    let lastGroupNote = ''
    for (const entry of spec.entries) {
      if (entry.kind === 'group') {
        out.push(`### ${entry.title}`)
        out.push('')
        if (entry.note) {
          out.push(entry.note, '')
        }
        lastGroupNote = entry.note
        continue
      }
      out.push(`- **${entry.title}**`)
      const blocks = []
      // The GIF is made from the test's own recording, so a broken recipe
      // has none rather than a stale one -- which is why this checks for the
      // file rather than assuming it.
      const artefact = artefactFor(entry.title, files)
      if (artefact) {
        blocks.push(`  ${artefact}`)
      }
      // A describe block and the test that follows it can pick up the same
      // preceding comment, which printed the paragraph twice.
      if (entry.note && entry.note !== lastGroupNote) {
        blocks.push(
          entry.note
            .split('\n')
            .map(line => (line.trim() ? `  ${line}` : ''))
            .join('\n')
        )
      }
      for (const block of blocks) {
        out.push('', block)
      }
      if (blocks.length) {
        out.push('')
      }
    }
    out.push('')
  }

  out.push('---')
  out.push('')
  out.push(`Regenerate with \`node website/e2e/cookbook.js\`.`)
  out.push('')
  return out.join('\n')
}

function main() {
  const outfile = process.argv[2] || DEFAULT_OUT
  const specs = fs
    .readdirSync(E2E_DIR)
    .filter(f => f.endsWith('.spec.js'))
    .sort()
    .map(f => parseSpec(path.join(E2E_DIR, f)))

  const files = recipeFiles()
  const markdown = render(specs, files)
  fs.mkdirSync(path.dirname(outfile), { recursive: true })
  fs.writeFileSync(outfile, markdown, 'utf8')

  const steps = specs.reduce(
    (n, s) => n + s.entries.filter(e => e.kind === 'step').length,
    0
  )
  console.log(`${outfile}: ${specs.length} specs, ${steps} recipes`)

  // A GIF `./al recipes` has just written is not linked until git tracks
  // it. Say so, rather than leave it to be noticed in review.
  const untracked = fs.existsSync(RECIPE_DIR)
    ? fs.readdirSync(RECIPE_DIR).filter(f => f.endsWith('.gif') && !files.has(f))
    : []
  if (untracked.length) {
    console.log(
      `not linked until tracked: ${untracked.join(', ')}\n` +
        '  git add docs/recipes, then run this again'
    )
  }
}

main()
