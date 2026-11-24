# Examples
The following are several examples, demonstrating basic and advanced capabilities of alfred.


!!! abstract "Usage notes"
    The examples use `curl`; any request library works.
    
    Every API call needs a valid jwt `TOKEN`; see [Login](login.md).

    The examples are sent to `http://127.0.0.1:8000`, the dev stack that `./al dev` starts ([Get started](../start.md)). For another server, such as the production one at `https://alfred.quaternion.media`, use its address instead. A development stack started with `ALFRED_DEV_SKIP_AUTH=1` serves every request as its development user, token or not; see [Skipping login in development](../dev-auth.md).

!!! abstract "Media"
    A `video`, `image` or `audio` clip names a file in the server's media library, as `GET /videos` lists it: `videos/<file>`. The examples use the three clips `POST /demo/media` makes there, the editor's *Generate demo media*, without the network: `videos/demo-bars.mp4` (colour bars), `videos/demo-colour.mp4` (a plain dark colour) and `videos/demo-testcard.mp4` (a test card whose counter shows the second), each 3.0 seconds long. So every example works on a fresh install once they are made. `./al demo` downloads longer footage, `videos/moon.mp4` and `videos/train.mp4`, for examples of your own. `GET /media` lists the library with each file's kind, length and size.

    A clip may name an `http(s)` URL only on a server whose `ALFRED_REMOTE_MEDIA_HOSTS` lists the URL's host (see [Configuration](../configuration.md)). The list is empty by default, so every URL is refused; with `ALFRED_REMOTE_MEDIA_HOSTS=storage.googleapis.com`, a clip may name `https://storage.googleapis.com/tower-bucket/moon.mp4`.

    A clip naming anything else, such as a path outside the library or a host not on the list, is refused with a 422 that names the clip, before anything is stored or queued.

!!! abstract "Examples as files, and their pictures"
    Each request body below is a file in `docs/examples/edl/`, which its page includes. A browser test, `website/e2e/examples.spec.js`, previews every one of them on the demo media and fetches its frame, so an example that stops working fails the suite rather than the reader.

    The pictures are each example made into a project and opened in the editor, with the playhead at the moment the test previews: the middle of the first clip, or part way through a fade or the animation. The panels on the left are closed and the timeline zoomed in as far as it still fits, so each clip shows its in-point and out-point after its name. `./al recipes` takes them (`website/e2e/screens-examples.spec.js`). A clip without a `duration` is shown at the length otto gives it, five seconds. The editor's viewer plays a clip's own file, or draws its template, under the playhead: a resize, a position or a fade is drawn in a [preview frame](preview.md) or a render, and not in the viewer.
