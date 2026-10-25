# Fonts
`GET /fonts` lists the font families this server can set a template's text in, by the names a template's [`font`](../about/template.md#font) takes.

## `GET /fonts`
A JSON array of names: each is fontconfig's name for a family, with its spaces as hyphens. It needs a session, and answers `401` without one.

``` bash title="List the fonts"
curl -H "Authorization: Bearer $TOKEN" \
  https://alfred.quaternion.media/fonts
```

The api image has DejaVu, which its base ships, and the urw-base35 set its Dockerfile installs:

``` json
["C059", "D050000L", "DejaVu-Sans", "DejaVu-Sans-Mono", "DejaVu-Serif",
 "Nimbus-Mono-PS", "Nimbus-Roman", "Nimbus-Sans", "Nimbus-Sans-Narrow", "P052",
 "Standard-Symbols-PS", "URW-Bookman", "URW-Gothic", "Z003"]
```

The names come in no particular order.

## Where the list comes from
The route answers from the database, not from the fonts on disk. When the api starts, it asks fontconfig for every font installed (`fc-list`), a family and its style a line, and keeps a document per family, with its styles, in the `fonts` collection. A line naming several families, as fontconfig names a font in several languages, gives each its own. Then it deletes each family fontconfig no longer lists. So a font added to the image, or taken out of it, is listed or dropped from the api's next start.

## How the editor uses it
The template editor asks once, with a session, the first time it shows a template that takes a `font`; [`GET /templates`](otto.md#get-templates) says which do.

- It sorts the names and shows each with its hyphens as spaces, `DejaVu Sans`, after "Template default", which leaves the clip's `font` unset.
- The name chosen is sent back as the clip's `font`, hyphens and all, and the template preview and the render draw with it.
- Until the list arrives, or if the request fails, the field offers the template's default and whatever font the clip already names. A failed request is made again the next time a font field is shown, ten seconds on.
- A font the clip names that is not listed, written by a project's logic or on another server, is kept and shown as "As set", not replaced.
