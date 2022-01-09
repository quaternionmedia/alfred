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
You have a commercial template which contains a spot for a feature product. This template will always include a single image, with the name of the product above it.

The desired `Edl` will include the base video, with an image and text overlayed on top. 

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

By creating a template, we can automatically create a commercial for each product, with an automatically generated form to fill out.


We can also render each project to multiple formats, or use the entire project as a portion of a larger project!

!!! abstract "`Edl` vs `Project`"
    By definition, an `Edl` is a `Project` that has no special logic, and therefore needs no data.

For a full working example, see [examples/project](../../examples/project).
