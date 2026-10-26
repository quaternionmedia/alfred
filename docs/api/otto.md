# Otto
`otto` is the *otto*matic rendering engine behind alfred's renders, its previews and its [`Template`](../about/template.md) logic. It is vendored at `alfred/otto`: alfred decides what a caller may ask for, and otto draws it.

## `POST /preview/`
Builds the `Edl` in the body and answers a signed URL for its frame at `t` seconds; `?t=` is required. It checks a timeline before rendering it in full.

See [examples/preview](../examples/preview.md)

## `GET /preview/template/{name}`
Draws one template and answers the image itself, a JPEG: what the editor shows while a template clip is edited. The template's data comes as `data`, a JSON object, which is how the editor sends it and the only way to send a structured field such as an animation's `fxs`. A plain field can also come as its own query parameter, such as `?text=asdf`. Beside it, `width`, `height`, `t`, `fadeIn`, `fadeOut` and `length` (the clip's length) describe the frame. There are no fades unless asked for. `data` that is not a JSON object is a 422.

``` bash title="Preview the title template at t=1"
curl -o title.jpg \
  -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/preview/template/title?text=asdf&t=1"
```

A template the server does not offer is a 404; one the data given cannot draw, such as `title` without `text`, is a 422.

## `GET /templates`
The templates the server offers, each with its `name`, a `label` for people to read, its `description`, the `parameters` it takes, and whether it is `deprecated`. See [about/template](../about/template.md).
