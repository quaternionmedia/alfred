# API
Sometimes, it is more convenient to interact directly with the API, bypassing the browser based client entirely. The following is a guide to interacting with the video renderer directly and generating videos from a data object.

This is an advanced topic, and requires some tool to make requests to the server. The following examples are provided using `curl`, but any requests library will have comparable features.

!!! note
    For the full API reference (including interactive request generator), visit [alfred.quaternion.media/api](https://alfred.quaternion.media/api)


## issues
Report any issues with renders with the `/report/{render}` endpoint.
