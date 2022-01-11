# Render video
Render an `Edl` with a single video and download the result when finished.

## Request
=== "Edl"
    ``` json title="data.json"
    {
      "edl": {
        "clips": [
          {
            "type": "video",
            "name": "https://storage.googleapis.com/tower-bucket/moon.mp4"
          }
        ]
      },
      "width": 1920,
      "height": 1080,
      "fps": 30
    }
    ```

=== "Request"
    ``` bash title="Render Video"
    curl -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d @data.json \
      https://alfred.quaternion.media/render
    ```

!!! note "Parameter passing"
    Render parameters such as `width` and `height` can also be specified as query parameters, instead of being passed in the data object.
    
    ```
    https://alfred.quaternion.media/render?width=1920&height=1080&fps=30
    ```

## Result
If the render process started successfully, this returns the `id` of the render process.
``` bash title="RenderId"
"61a43a5d6f511ec4ba99ac63"
```
## Check status
``` bash title="Render Video"
curl -H "Authorization: Bearer $TOKEN" \
  https://alfred.quaternion.media/render/
```
This returns the progress of all current renders, each with their specified `RENDER_ID`. When `status = 100%`, rendering is complete, and the video is ready to be viewed, shared, or downloaded.

## Download
To retrieve a signed link to a render video:
``` bash title="Get signed render link"
curl -H "Authorization: Bearer $TOKEN" \
  https://alfred.quaternion.media/render/$RENDER_ID
```

!!! note "Link expiration"
    All links are generated on demand and are valid for 15 minutes

## Multiple formats
Multiple output formats can be generated from the same `Edl`. 

For example:

- HD / SD resolutions
- Horizontal / Vertical aspect ratios
- Output format
- Bitrate settings (Web, TV, etc)

For each desired output, generate an API request with the specified render settings and receive an `id` to use when downloading.
