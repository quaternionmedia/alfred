/**
 * The docs' example request bodies, one file each in docs/examples/edl/.
 * The pages include the same files. test_e2e.yml mounts the directory for the container.
 */

const fs = require('fs')
const path = require('path')

const EDL_DIR = path.join(__dirname, '..', '..', 'docs', 'examples', 'edl')

// Fewer means the directory is missing, not that there are fewer examples.
const AT_LEAST = 13

// otto's default clip length (otto.models.Clip).
const DEFAULT_SECONDS = 5

// Shown at these seconds instead of the first clip's middle.
const MOMENTS = { 'fade-in': 1, 'fade-out': 2, animation: 0.5 }

/** Every example: `{name, file, body}`, by name. */
function examples() {
  const files = fs.existsSync(EDL_DIR) ? fs.readdirSync(EDL_DIR) : []
  return files
    .filter(file => file.endsWith('.json'))
    .sort()
    .map(file => ({
      name: path.basename(file, '.json'),
      file: `docs/examples/edl/${file}`,
      body: JSON.parse(fs.readFileSync(path.join(EDL_DIR, file), 'utf-8')),
    }))
}

/** A clip's start, in-point and length in seconds, as otto reads them. */
function timing(clip) {
  const inpoint = Number(clip.inpoint) || 0
  let length = DEFAULT_SECONDS
  if (clip.outpoint != null) length = clip.outpoint - inpoint
  else if (clip.duration != null) length = clip.duration
  return { start: Number(clip.start) || 0, inpoint, length }
}

/** The second an example is previewed and shown at. */
function moment({ name, body }) {
  if (name in MOMENTS) return MOMENTS[name]
  const first = timing(body.edl.clips[0])
  return first.start + first.length / 2
}

/** An example's clips as the editor keeps them: otto's defaults written in. */
function editorClips(body) {
  let at = 0
  return body.edl.clips.map(clip => {
    const { inpoint, length } = timing(clip)
    const kept = { ...clip, start: at, duration: length }
    if (clip.type === 'video' || clip.type === 'audio') {
      Object.assign(kept, { inpoint, outpoint: inpoint + length })
    }
    at += length
    return kept
  })
}

module.exports = { AT_LEAST, EDL_DIR, editorClips, examples, moment, timing }
