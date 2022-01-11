# Animate text

The following generates a text clip which flies in from the right with a 2nd order bezier curve, according to the following control points:
: c1: `(1,0)`
: a: `(0,0)`
: c2: `(0,1)`
``` json title="Animation" hl_lines="10-17"
{
  "clips": [
    { 
      "type" : "template",
      "name" : "title",
      "data": {
        "text": "asdf",
        "fxs": [
          {
            "name": "bezier2",
            "data": {
              "c1x": 1,
              "c1y": 0,
              "ax": 0,
              "ay": 0,
              "c2x": 0,
              "c2y": 1
            }
          }
        ]
      }
    }
  ]
}
```