# Refusals
A request alfred refuses answers with an HTTP status and a JSON body. When alfred's own code refused it, the body says why twice:

``` json title="POST /project/{id}/captions/transcribe, with no audio engine"
{
  "detail": "No audio engine is configured: set ALFRED_AUDIO_ENGINE_URL to its address (docs/captions.md says how to run one).",
  "code": "audio_engine_missing"
}
```

`detail` is a sentence for a person, and the editor shows it as it is. `code` is for a program: what the refusal means, in a word that stays the same when the sentence is reworded. Switch on `code`, never on the wording -- the two 503s a transcription can meet, for one, differ only in it. Each code has one status, so the code says everything the status does.

| Code | Status | Means | Answered by |
|---|---|---|---|
| `invalid_id` | 422 | the id in the path is not an id -- not an ObjectId's 24 hex digits -- refused before anything is looked up | every project, captions and render route that takes an id |
| `not_found` | 404 | no such project or render, or not yours: alfred does not say which | every project, captions and render route that takes an id |
| `too_many_captions` | 422 | more captions than the 1000 a project carries | `PUT /project/{id}/captions`, `POST /project`, `POST /render` |
| `caption_file_unreadable` | 422 | the subtitle file cannot be read; `detail` names the line | `POST /project/{id}/captions/import` |
| `audio_engine_missing` | 503 | no audio engine alfred can ask: none is configured, or a setting or this build cannot reach one; `detail` is the reason `GET /health` gives as `audio_engine.detail` | `POST /project/{id}/captions/transcribe` |
| `timeline_empty` | 422 | the project has no saved timeline to transcribe | `POST /project/{id}/captions/transcribe` |
| `timeline_unplayable` | 422 | the saved timeline cannot be played; `detail` names the clip | `POST /project/{id}/captions/transcribe` |
| `timeline_silent` | 422 | nothing in the timeline can make a sound: no video or audio clips | `POST /project/{id}/captions/transcribe` |
| `transcription_running` | 409 | a transcription of this project is under way; `GET /project/{id}/captions` follows it | `POST /project/{id}/captions/transcribe` |
| `transcription_not_queued` | 503 | the broker would not take the job; the project's job is recorded `failed` with the reason | `POST /project/{id}/captions/transcribe` |
| `encoder_options_refused` | 422 | `ffmpeg_params` or `bitrate` was sent: a render chooses a `quality` instead | `POST /render` |
| `frame_size_out_of_range` | 422 | a `width` or `height` outside 16 to 7680 pixels | `POST /render` |
| `fps_out_of_range` | 422 | an `fps` outside 1 to 120 | `POST /render` |
| `unknown_quality` | 422 | a `quality` that is not one of the presets | `POST /render` |
| `edl_refused` | 422 | a clip this server will not render: media outside the library, a template it does not offer, a type it does not know; `detail` names the clip | `POST /render`, `POST /render/rerender/{id}` |
| `render_not_queued` | 503 | the broker would not take the render; the render is recorded `failed` with the reason, which `GET /render/{id}/status` gives as `error`, and `POST /render/rerender/{id}` queues it again | `POST /render`, `POST /render/rerender/{id}` |
| `render_not_finished` | 409 | the render has no finished file yet | `POST /render/{id}/deliver`, `GET /render/{id}/download` |
| `destination_unknown` | 502 | no destination has that name; `detail` lists those that do | `POST /render/{id}/deliver` |
| `delivery_failed` | 502 | the destination would not take the render; asking again may deliver it | `POST /render/{id}/deliver` |
| `delivered_without_link` | 502 | the render was uploaded to the bucket, and recorded so, but no link to it could be signed | `POST /render/{id}/deliver` |
| `cloud_link_unavailable` | 502 | no link to the render's copy in the cloud bucket can be signed: always, on a server with no cloud account | `GET /render/{id}` |

`tests/unit/test_refusal_codes.py` holds this table to alfred's code: every code alfred has is here with its status, and each is answered, with its sentence, by a request through the API.

## What carries no code
- **A request FastAPI refuses** before a route runs -- a body or parameter that does not fit the route's model -- answers 422 with a list of `{loc, msg, type}` as its `detail`, which already says where and what.
- **No session**: 401, `{"detail": "Unauthorized"}`.
- **Signing in and accounts** (`/auth/...`, `/users/...`): fastapi-users answers its own codes as the `detail` itself, such as `LOGIN_BAD_CREDENTIALS`.
- **A route alfred does not have**: FastAPI's 404, `{"detail": "Not Found"}`, which a client tells from `not_found` by the code it lacks.
- **The routes not covered yet** answer `detail` alone: the media library and how a file sounds (`/media`, `/videos`), previews, demo media, templates, a signed link's refusal on the file routes, issue reports and invoices.

A client that has to work with an alfred from before codes reads `detail`, as it always could; one that finds a `code` switches on it.
