# Otto
`otto` is the *otto*matic :wink: rendering engine behind alfred's renders, its previews and its [`Template`](../about/template.md) logic. It is vendored at `alfred/otto`: alfred decides what a caller may ask for, and otto draws it.

## `POST /preview/`
Builds the `Edl` in the body and answers a signed URL for its frame at `t` seconds, `?t=` being required. Useful to check a timeline before rendering it in full.

See [examples/preview](../examples/preview.md)

## `GET /preview/template/{name}`
Draws one template and answers the image itself, a JPEG: what the editor shows while a template clip is edited. The template's data comes as query parameters, such as `?text=asdf`, beside `width`, `height`, `t`, `fadeIn`, `fadeOut` and `length` (the clip's length), which describe the frame. There are no fades unless they are asked for.

``` bash title="Preview the title template at t=1"
curl -o title.jpg \
  -H "Authorization: Bearer $TOKEN" \
  "https://alfred.quaternion.media/preview/template/title?text=asdf&t=1"
```

A template the server does not offer is a 404, and one that cannot be drawn from the data given, such as `title` without `text`, a 422.

## `GET /templates`
The templates the server offers, each with its `description`, the `parameters` it takes, and whether it is `deprecated`. See [about/template](../about/template.md).
