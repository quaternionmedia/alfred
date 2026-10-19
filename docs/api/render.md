# Render
The `render` routes accept an `Edl` with its render settings, queue a server render, and say how it is getting on until it is finished and fetched. Each needs a session and acts on your own renders, or on any for a superuser: a render that is not yours answers 404, as one that does not exist does.

| Route | |
|---|---|
| `POST /render` | queue a render, as [about/render](../about/render.md) describes; answers its id |
| `GET /render` | your renders, newest first (`skip`, `limit`), each with `download_url` |
| `GET /render/{id}/status` | `{id, state, status, progress, filename, destination, error, download_url}` |
| `GET /render/{id}/download` | the finished video, with `Range` support; with a session, or with none by the signed `download_url` |
| `POST /render/{id}/deliver` | send a finished render to `?destination=`, one of `GET /destinations`; 409 until it has finished |
| `GET /render/{id}` | a signed link to the render's copy in the cloud bucket; 502 when there is none |
| `PUT /render/{id}` | change `name`, `project`, `project_id` or `description`; any other field is a 422 |
| `POST /render/rerender/{id}` | queue it again, with the timeline and settings it was stored with |
| `DELETE /render/{id}` | delete it, with its video and any local delivery's copy |

[examples/render](../examples/render.md) follows one render from request to download. A refusal carries a `code` beside its `detail`, such as `render_not_finished` for the 409: [Refusals](errors.md) lists them.

## Issues
Report an issue with one of your renders with `POST /render/{id}/report`, whose body is the report as a JSON string:

``` bash title="Report an issue"
curl -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '"The sound is out of step with the picture."' \
  https://alfred.quaternion.media/render/$RENDER_ID/report
```

It is mailed to the addresses in `EMAIL_SENDTO`, with the mail settings the rest of the server's mail uses (`EMAIL_SERVER`, `EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`). When the mail cannot be sent, it answers 500.
