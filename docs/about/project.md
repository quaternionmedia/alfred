# Project

A `Project` is a special type of `Edl` template, designed to add user data dynamically by specifying rules to create an `Edl` when **data** is applied. The end result is generates an `Edl` that is ready to be rendered.

``` json title="`Project` data format"
{
  "logic": {
    // custom Edl logic here
  },
  "fields": [
  // a description of the types of data expected,
  // used to generate a form automatically
  ]
}
```

## Use case
A commercial has a spot for a featured product: always one image, with the product's name above it.

The `Edl` is the base video, with the image and the text over it.

``` json title="Custom Product Project" hl_lines="7-9 17-19"
{
  "logic": {
    {...}, // base video
    { // product image
      "start": 5,
      "type": "image",
      "name": {
        "var": "ProductImage"
      }
    },
    { // product name
      {
        "start": 5,
        "type": "template",
        "name": "textBox",
        "data": {
          "text": {
            "var": "ProductName"
          }
        }
      }
    }
  },
  "fields": [
    { "type": "Text",
        "attrs": {
          "name": "ProductImage",
          "text": "Link to product image",
        }
    },
    { "type": "Textarea",
        "attrs": {
          "name": "ProductName",
          "text": "Product Name",
        }
    },
  ]
}
```

With this template, each product gets a commercial made automatically, from a generated form to fill out.

Each project can also be rendered to several formats, or used as part of a larger project.

!!! abstract "`Edl` vs `Project`"
    An `Edl` is a `Project` with no special logic, so it needs no data.

[examples/project](../examples/project.md) is a full working example.
