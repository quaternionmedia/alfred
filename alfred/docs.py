from alfred._version import __version__

title = """Alfred API"""

description = """# Automatic video creation
Alfred is an automatic video api, designed to automate video tasks.

We believe in making video smarter, not harder.

### Created by Quaternion Media, LLC
[github.com/quaternionmedia](https://github.com/quaternionmedia)"""

version = __version__
# terms_of_service = ""

contact = {
    'name': 'Quaternion Media',
    'url': 'https://quaternion.media',
    'email': 'alfred@quaternion.media',
}
# license_info = {}

tags_metadata = [
    {
        'name': 'auth',
        'description': """# Auth
Authentication operations, including **Login** and **Registration**""",
    },
    {
        'name': 'users',
        'description': """# Users
Get information about a user, including self.""",
    },
    {
        'name': 'Project',
        'description': """# Project
A **Project** is an alfred document with a `logic` object which contains the necessary logic to create an `Edl` and an optional `fields` object, which describes the variables needed to execute the `logic` object.""",
        # 'externalDocs': {
        #     'description': 'Project reference',
        #     'url': 'https://docs.quaternion.media/alfred',
        # },
    },
    {
        'name': 'otto',
        'description': """# Otto
`otto` is the underlying template rendering engine. Use these routes to generate preview frames of an `Edl` before rendering a full project.
""",
    },
    {
        'name': 'render',
        'description': """# Render
Render an `Edl` and check status on existing renders.""",
    },
    {
        'name': 'video',
        'description': """# Video
Serve videos directly from this instance.
        """,
    },
    {
        'name': 'font',
        'description': """# Fonts
Get a list of fonts available to be rendered on this instance.""",
    },
    {
        'name': 'admin',
        'description': """# admin
Admin tasks. Only accessable for superusers.""",
    },
]
