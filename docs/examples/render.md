# Render a video
Render an `Edl` on the server and download the final video when finished.

## Edl
A single video clip.
``` json title="data.json"
{
  "edl": {
    "clips": [
      {
        "type": "video",
        "name": "https://storage.googleapis.com/tower-bucket/moon.mp4"
      }
    ]
  }
}
```

## Request
``` bash title="Render Video"
curl -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @data.json \
  https://alfred.quaternion.media/render
```
## Result
If the render process started successfully, this returns the `id` of the render process.
``` bash title="RenderId"
"61a43a5d6f511ec4ba99ac63"
```
## Check status


``` bash title="Render Video"
curl -H "Authorization: Bearer $TOKEN" \
  https://alfred.quaternion.media/render/$RENDER_ID
```
