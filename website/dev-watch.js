#!/usr/bin/env node
/**
 * Rebuild the bundle when sources change, by polling.
 *
 * `parcel watch` does not work when the repository is bind-mounted from a
 * non-Linux host. @parcel/watcher subscribes to inotify, and inotify events do
 * not cross a Docker Desktop bind mount from Windows or macOS: the container
 * sees the edited file -- content and mtime both update -- but is never told it
 * changed. So parcel sits idle, dist/ goes stale, and every frontend edit needs
 * a container restart before it appears.
 *
 * Parcel's own polling backend is not usable here. `--watch-backend
 * brute-force` aborts on startup with SIGABRT ("terminate called after throwing
 * an instance of 'char const*'"), and watchman is not in the image.
 *
 * So: stat the source tree on an interval and shell out to `parcel build` when
 * something moves. Parcel's cache makes a rebuild about as fast as an
 * incremental watch rebuild, so the cost is the polling itself.
 *
 * What this does not give you is HMR -- the browser will not refresh itself.
 * dist/ is current within one poll interval; reload the page to see it. That is
 * the trade for a dev loop that works on every host rather than only on Linux.
 */

const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const ROOT = path.join(__dirname, 'src')
const ENTRY = 'src/index.html'
const INTERVAL = Number(process.env.WATCH_INTERVAL_MS || 1000)

// Directories whose contents are outputs or caches, never inputs.
const SKIP = new Set(['node_modules', '.parcel-cache', 'dist', '.git'])

function snapshot(dir, acc = new Map()) {
  let entries
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true })
  } catch (e) {
    return acc
  }
  for (const entry of entries) {
    if (SKIP.has(entry.name)) continue
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      snapshot(full, acc)
    } else {
      try {
        acc.set(full, fs.statSync(full).mtimeMs)
      } catch (e) {
        // deleted between readdir and stat; the next poll will settle it
      }
    }
  }
  return acc
}

function changes(before, after) {
  const changed = []
  for (const [file, mtime] of after) {
    if (!before.has(file) || before.get(file) !== mtime) changed.push(file)
  }
  for (const file of before.keys()) {
    if (!after.has(file)) changed.push(file)
  }
  return changed
}

function build(reason) {
  const started = Date.now()
  try {
    execFileSync('npx', ['parcel', 'build', ENTRY, '--no-optimize'], {
      cwd: __dirname,
      stdio: ['ignore', 'inherit', 'inherit'],
    })
    console.log(`built in ${Date.now() - started}ms (${reason})`)
  } catch (e) {
    // A build error is information, not a reason to stop watching: the next
    // save is usually the fix.
    console.error(`build failed (${reason}); watching for the next change`)
  }
}

console.log(`polling ${ROOT} every ${INTERVAL}ms (parcel watch cannot see this mount)`)
build('startup')

let previous = snapshot(ROOT)
setInterval(() => {
  const current = snapshot(ROOT)
  const changed = changes(previous, current)
  previous = current
  if (changed.length) {
    const names = changed.slice(0, 3).map(f => path.relative(ROOT, f))
    const suffix = changed.length > 3 ? ` +${changed.length - 3} more` : ''
    build(`${names.join(', ')}${suffix}`)
  }
}, INTERVAL)
