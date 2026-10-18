# Examples
The following are several examples, demonstrating basic and advanced capabilities of Alfred.


!!! abstract "Usage notes"
    All examples here are shown using `curl`, but any request library will work.
    
    All API calls require authentication with a valid jwt `TOKEN`. See [Login](login.md) for details.

    The examples are sent to `https://alfred.quaternion.media`. To try them on a server of your own, send them to its address instead, such as `http://localhost:8000` for `./al dev`. A development stack started with `ALFRED_DEV_SKIP_AUTH=1` serves every request as its development user, token or not; see [Skipping login in development](../dev-auth.md).

!!! abstract "Media"
    A `video`, `image` or `audio` clip names a file in the server's media library, as `GET /videos` lists it: `videos/<file>`. The examples use `videos/moon.mp4` and `videos/train.mp4`, which `./al demo` downloads into the library. `POST /demo/media`, the editor's *Generate demo media*, makes three short clips there without the network, `videos/demo-bars.mp4` among them, and `GET /media` lists the library with each file's kind, length and size.

    A clip may name an `http(s)` URL instead only on a server whose `ALFRED_REMOTE_MEDIA_HOSTS` lists the URL's host (see [Configuration](../configuration.md)). The list is empty by default, so by default every URL is refused; with `ALFRED_REMOTE_MEDIA_HOSTS=storage.googleapis.com`, a clip may name `https://storage.googleapis.com/tower-bucket/moon.mp4`.

    A clip naming anything else, such as a path outside the library or a host not on the list, is refused with a 422 that names the clip, before anything is stored or queued.
