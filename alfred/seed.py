seed = [
    {
        "name": "Magnussens",
        "logic": {
            "merge": [
                {
                    "eachKey": {
                        "type": "video",
                        "name": "https://storage.googleapis.com/tower-bucket/alfred/car/Magnussens%20(check%20out%20offer).mp4",
                        "duration": {"var": "duration"},
                        "start": 0,
                        "inpoint": 0,
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "makeColor",
                        "duration": 7.2,
                        "start": 17.1,
                        "data": {"preserve": {"color": [255, 255, 255], "opacity": 1}},
                    }
                },
                {
                    "eachKey": {
                        "type": "image",
                        "name": "https://storage.googleapis.com/tower-bucket/alfred/car/magnussens-screengrab%20logo-fixed-with-toyota.png",
                        "position": ["center", "top"],
                        "resize": {
                            "/": [
                                {"sqrt": {"*": [{"var": "width"}, {"var": "height"}]}},
                                3600,
                            ]
                        },
                        "start": 17.1,
                        "duration": 7.2,
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 7.2,
                        "start": 17.1,
                        "data": {
                            "eachKey": {
                                "text": {"var": "carname"},
                                "color": "#EB0A1E",
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.3, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type-Bold",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        15,
                                    ]
                                },
                                "position": [
                                    "center",
                                    {"floor": {"*": [0.1, {"var": "height"}]}},
                                ],
                                "opacity": 1,
                                "fxs": {
                                    "preserve": [
                                        {
                                            "name": "bezier2",
                                            "data": {
                                                "c1x": 1,
                                                "c1y": 0,
                                                "ax": 0,
                                                "ay": 0,
                                                "c2x": 0,
                                                "c2y": 1,
                                            },
                                        }
                                    ]
                                },
                            }
                        },
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 7.2,
                        "start": 17.1,
                        "relative": True,
                        "data": {
                            "eachKey": {
                                "color": "#EB0A1E",
                                "text": {"var": "offerinfo"},
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.5, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        32,
                                    ]
                                },
                                "opacity": 1,
                                "position": "center",
                                "align": {
                                    "if": [
                                        {"==": [{"var": "offeralign"}, "left"]},
                                        "west",
                                        {"var": "offeralign"},
                                    ]
                                },
                            }
                        },
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 7.2,
                        "start": 17.1,
                        "data": {
                            "eachKey": {
                                "color": "#333333",
                                "text": {"var": "legaltext"},
                                "method": "caption",
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.35, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type-Book",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        60,
                                    ]
                                },
                                "position": ["center", "bottom"],
                                "align": "west",
                                "opacity": 1,
                            }
                        },
                    }
                },
            ]
        },
        "fields": [
            {
                "type": "Selector",
                "attrs": {"name": "duration", "text": "Duration"},
                "children": ["30", "15"],
            },
            {"type": "Textarea", "attrs": {"name": "carname", "text": "Car Name"}},
            {"type": "Textarea", "attrs": {"name": "offerinfo", "text": "Offer Info"}},
            {
                "type": "Selector",
                "attrs": {"name": "offeralign", "text": "Offer alignment"},
                "children": ["left", "center"],
            },
            {"type": "Textarea", "attrs": {"name": "legaltext", "text": "Legal Text"}},
        ],
    },
    {
        "name": "Magnussens 2021_2",
        "logic": {
            "merge": [
                {
                    "eachKey": {
                        "type": "video",
                        "name": "https://storage.googleapis.com/tower-bucket/alfred/car/Magnussens%202021_2.mp4",
                        "duration": {"var": "duration"},
                        "start": 0,
                        "inpoint": 0,
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 4.5,
                        "start": 27.5,
                        "data": {
                            "eachKey": {
                                "text": {"var": "carname"},
                                "color": "#EB0A1E",
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.3, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type-Bold",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        15,
                                    ]
                                },
                                "position": [
                                    "center",
                                    {"floor": {"*": [0.14, {"var": "height"}]}},
                                ],
                                "opacity": 1,
                                "fxs": {
                                    "preserve": [
                                        {
                                            "name": "bezier2",
                                            "data": {
                                                "c1x": 1,
                                                "c1y": 0,
                                                "ax": 0,
                                                "ay": 0,
                                                "c2x": 0,
                                                "c2y": 1,
                                            },
                                        }
                                    ]
                                },
                            }
                        },
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 4.5,
                        "start": 27.5,
                        "data": {
                            "eachKey": {
                                "color": "#EB0A1E",
                                "text": {"var": "offerinfo"},
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.5, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        32,
                                    ]
                                },
                                "opacity": 1,
                                "position": "center",
                                "align": {
                                    "if": [
                                        {"==": [{"var": "offeralign"}, "left"]},
                                        "west",
                                        {"var": "offeralign"},
                                    ]
                                },
                            }
                        },
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 4.5,
                        "start": 27.5,
                        "data": {
                            "eachKey": {
                                "color": "#333333",
                                "text": {"var": "legaltext"},
                                "method": "caption",
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.35, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type-Book",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        60,
                                    ]
                                },
                                "position": ["center", "bottom"],
                                "align": "west",
                                "opacity": 1,
                            }
                        },
                    }
                },
            ]
        },
        "fields": [
            {
                "type": "Selector",
                "attrs": {"name": "duration", "text": "Duration"},
                "children": ["34"],
            },
            {"type": "Textarea", "attrs": {"name": "carname", "text": "Car Name"}},
            {"type": "Textarea", "attrs": {"name": "offerinfo", "text": "Offer Info"}},
            {
                "type": "Selector",
                "attrs": {"name": "offeralign", "text": "Offer alignment"},
                "children": ["left", "center"],
            },
            {"type": "Textarea", "attrs": {"name": "legaltext", "text": "Legal Text"}},
        ],
    },
    {
        "name": "RSG",
        "logic": {
            "merge": [
                {
                    "eachKey": {
                        "type": "video",
                        "name": "https://storage.googleapis.com/tower-bucket/alfred/car/315048_MUL_MY21_MRE_RSG_LVStory_Downtown_Non-New_ENG_17-10-03_ProdAssetDlrNFA_SSSH2955000H.mp4",
                        "duration": {"var": "duration"},
                        "start": 0,
                        "inpoint": 7,
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 10.7,
                        "start": 14.4,
                        "data": {
                            "eachKey": {
                                "text": {"var": "carname"},
                                "color": "#EB0A1E",
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.3, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type-Bold",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        15,
                                    ]
                                },
                                "position": [
                                    "center",
                                    {"floor": {"*": [0.1, {"var": "height"}]}},
                                ],
                                "opacity": 1,
                                "fxs": {
                                    "preserve": [
                                        {
                                            "name": "bezier2",
                                            "data": {
                                                "c1x": 1,
                                                "c1y": 0,
                                                "ax": 0,
                                                "ay": 0,
                                                "c2x": 0,
                                                "c2y": 1,
                                            },
                                        }
                                    ]
                                },
                            }
                        },
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 10.7,
                        "start": 14.4,
                        "data": {
                            "eachKey": {
                                "color": "#EB0A1E",
                                "text": {"var": "offerinfo"},
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.5, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        32,
                                    ]
                                },
                                "opacity": 1,
                                "position": "center",
                                "align": {
                                    "if": [
                                        {"==": [{"var": "offeralign"}, "left"]},
                                        "west",
                                        {"var": "offeralign"},
                                    ]
                                },
                            }
                        },
                    }
                },
                {
                    "eachKey": {
                        "type": "template",
                        "name": "textBox",
                        "duration": 10.7,
                        "start": 14.4,
                        "data": {
                            "eachKey": {
                                "color": "#333333",
                                "text": {"var": "legaltext"},
                                "method": "caption",
                                "textsize": [
                                    {"floor": {"*": [0.9, {"var": "width"}]}},
                                    {"floor": {"*": [0.35, {"var": "height"}]}},
                                ],
                                "font": "Toyota-Type-Book",
                                "fontsize": {
                                    "/": [
                                        {
                                            "sqrt": {
                                                "*": [
                                                    {"var": "width"},
                                                    {"var": "height"},
                                                ]
                                            }
                                        },
                                        60,
                                    ]
                                },
                                "position": ["center", "bottom"],
                                "align": "west",
                                "opacity": 1,
                            }
                        },
                    }
                },
            ]
        },
        "fields": [
            {
                "type": "Selector",
                "attrs": {"name": "duration", "text": "Duration"},
                "children": ["30", "15"],
            },
            {"type": "Textarea", "attrs": {"name": "carname", "text": "Car Name"}},
            {"type": "Textarea", "attrs": {"name": "offerinfo", "text": "Offer Info"}},
            {
                "type": "Selector",
                "attrs": {"name": "offeralign", "text": "Offer alignment"},
                "children": ["left", "center"],
            },
            {"type": "Textarea", "attrs": {"name": "legaltext", "text": "Legal Text"}},
        ],
    },
]
seed_v1 = [
    {
        "filename": "tala",
        "edl": [
            {
                "type": "template",
                "name": "title",
                "data": {"text": "Business Name"},
                "duration": 5,
            },
            {
                "type": "template",
                "name": "initial",
                "data": {"text": "initial text"},
                "duration": 5,
            },
            {
                "type": "template",
                "name": "bullets",
                "data": {"text": "bullet points"},
                "duration": 5,
            },
            {
                "type": "template",
                "name": "initial",
                "data": {"text": "call to action"},
                "duration": 5,
            },
            {
                "type": "template",
                "name": "final",
                "data": {
                    "text": "Business Name",
                    "address": "address",
                    "website": "alfred.quaternion.media",
                    "phone": "(xxx) xxx-xxxx",
                },
                "duration": 5,
            },
        ],
    },
    {
        "filename": "demo",
        "edl": [
            {
                "name": "videos/train.mp4",
                "type": "video",
                "inpoint": 37.52,
                "outpoint": 42.05,
                "duration": 5.05,
                "description": "shooter",
            },
            {
                "name": "videos/moon.mp4",
                "type": "video",
                "inpoint": 30.15,
                "outpoint": 38.02,
                "duration": 7.86,
                "description": "moon",
            },
        ],
    },
    {
        "filename": "moon",
        "edl": [
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 81.64999999999985,
                "outpoint": 87.43,
                "duration": 5.7800000000001575,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 205.65,
                "outpoint": 207.65,
                "duration": 2,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 332.31,
                "outpoint": 338.38000000000034,
                "duration": 6.070000000000334,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 356.3067715379373,
                "outpoint": 360.3267715379374,
                "duration": 4.0200000000000955,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 373.0109889360814,
                "outpoint": 378.2209889360809,
                "duration": 5.209999999999525,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 383.0000000000012,
                "outpoint": 386.47000000000025,
                "duration": 3.469999999999061,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 414.1900000000003,
                "outpoint": 419.22,
                "duration": 5.029999999999745,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 459.13536573855606,
                "outpoint": 462.555365738556,
                "duration": 3.419999999999959,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 479.999366577526,
                "outpoint": 483.809366577526,
                "duration": 3.8100000000000023,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 563.6299999999998,
                "outpoint": 567.89,
                "duration": 4.260000000000218,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 589.6899999999995,
                "outpoint": 595.05,
                "duration": 5.360000000000468,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 639.6725541397925,
                "outpoint": 643.7525541397926,
                "duration": 4.080000000000041,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 657.0499999999996,
                "outpoint": 660.88,
                "duration": 3.830000000000382,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 691.4699999999993,
                "outpoint": 696.19,
                "duration": 4.720000000000709,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 705.88,
                "outpoint": 709.6299999999998,
                "duration": 3.7499999999997726,
                "description": "moon shot",
            },
            {
                "name": "videos/ATripToTheMoon-300k.mp4",
                "type": "video",
                "inpoint": 759.1699999999992,
                "outpoint": 766.9199999999989,
                "duration": 7.749999999999773,
                "description": "moon shot",
            },
        ],
    },
    {
        "filename": "external",
        "edl": [
            {
                "name": "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
                "type": "video",
                "inpoint": 60,
                "outpoint": 70,
                "duration": 10,
                "description": "clip 2",
            },
            {
                "name": "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "type": "video",
                "inpoint": 0,
                "outpoint": 10,
                "duration": 10,
                "description": "clip 1",
            },
        ],
    },
]


def edl1to2(edl):
    res = []
    for clip in edl:
        res.append(
            {
                "name": clip[0],
                "type": "video",
                "inpoint": clip[1],
                "outpoint": clip[2],
                "duration": clip[3],
                "description": clip[4],
            }
        )
    return res


def migrate1to2(db):
    res = []
    for i in db:
        edl = i.pop("edl")
        i["edl"] = edl1to2(edl)
        res.append(i)
    return res
