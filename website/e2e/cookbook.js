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

const E2E_DIR = __dirname
const DEFAULT_OUT = path.join(E2E_DIR, '..', '..', 'docs', 'cookbook.md')

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

function render(specs) {
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
      // A describe block and the test that follows it can pick up the same
      // preceding comment, which printed the paragraph twice.
      if (entry.note && entry.note !== lastGroupNote) {
        const indented = entry.note
          .split('\n')
          .map(line => (line.trim() ? `  ${line}` : ''))
          .join('\n')
        out.push('', indented, '')
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

  const markdown = render(specs)
  fs.mkdirSync(path.dirname(outfile), { recursive: true })
  fs.writeFileSync(outfile, markdown, 'utf8')

  const steps = specs.reduce(
    (n, s) => n + s.entries.filter(e => e.kind === 'step').length,
    0
  )
  console.log(`${outfile}: ${specs.length} specs, ${steps} recipes`)
}

main()
