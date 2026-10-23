# Pinned by digest. Unpinned, this resolved to whatever `python:latest` meant
# on the day of the build, which reached Python 3.14 -- where setuptools is no
# longer bundled, so `pip install` of a dependency needing pkg_resources fails
# outright. Bump this deliberately, not implicitly.
FROM python:3.11@sha256:d0199e2a90bf7a206a485b115323a75bc946f30b463d704c5435a454aca084dd AS api

WORKDIR /app

COPY pyproject.toml README.md requirements.lock ./
COPY alfred alfred

# Exactly the lockfile: its pins, and nothing resolved around them.
#
# This was `pip install -e .`, which re-resolves the loose ranges in
# pyproject.toml on every build -- so the image ran beanie 1.30, fastapi 0.125
# and motor 3.7 while the test suite ran 1.20, 0.100 and 3.2. The tests were
# not testing the versions the application used, and two builds a month apart
# were not the same application.
#
# --no-deps, on the lockfile and on the project, because pip cannot reproduce
# what pdm resolved. pyproject.toml overrides fastapi-users' exact pin on
# python-multipart (0.0.6, with nine advisories); pdm honours an override and
# pip has none, so resolving either the lockfile or the project fails outright
# (ResolutionImpossible). `pip check` here reports that one conflict, and it is
# the intended one. What resolving used to catch -- a dependency added to
# pyproject.toml and never locked, which --no-deps would leave out --
# tests/unit/test_stack_config.py checks against requirements.lock instead.
RUN pip3 install --no-cache-dir --no-deps -r requirements.lock

# The engine's render extras are not in the lockfile, so this install
# resolves; nothing the engine depends on reaches python-multipart, so it
# cannot undo the override.
RUN pip3 install -e alfred/otto[render]
# The sound engine's client, vendored beside the picture engine and installed
# the same way, editable from the submodule -- but with --no-deps: what its
# core imports (httpx) is in the lockfile above, and the rest of its own
# dependencies (a speech synthesizer, a CLI) serve parts alfred never loads.
RUN pip3 install --no-deps -e alfred/vox
RUN pip3 install --no-deps -e .
# Not in the lockfile either -- pyproject.toml lists the server as a
# development dependency -- so it is resolved here, and floats.
RUN pip3 install uvicorn

# The base now carries ImageMagick 7, so the hardcoded version-6 path no
# longer exists and this failed the build even once the base was pinned.
# Both paths are covered and the removal is non-fatal.
#
# SECURITY: deleting the policy wholesale is the original intent preserved,
# not a decision endorsed here. The policy is what restricts ImageMagick's
# handling of untrusted input, and this service accepts user-supplied media.
# The right fix is a targeted relaxation of only the rules moviepy's text
# rendering needs. Revisit in the security pass.
RUN rm -f /etc/ImageMagick-6/policy.xml /etc/ImageMagick-7/policy.xml

# Fonts, without which no template that draws text can render at all.
#
# moviepy's TextClip defaults to the font named "Courier". The base ships only
# DejaVu, so ImageMagick answered "unable to read font `Courier'", TextClip
# raised, and otto's template functions returned None. generateEdl reported
# that as "A clip did not get made properly" -- which named neither fonts nor
# ImageMagick, so the symptom pointed nowhere near the cause (the engine names
# the template and the error now). Five of the six templates are TextClip
# (title, textBox, bullets, initial, final), so this was most of the template
# feature.
#
# urw-base35 is the standard PostScript font set; ImageMagick's own
# type-urw-base35.xml was already present in the base, describing fonts that
# were not installed. Installing them takes the font count from 8 to 105 and
# makes Courier, Helvetica and Times resolve.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-urw-base35 \
    && rm -rf /var/lib/apt/lists/*

CMD ["uvicorn", "alfred.main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]


# The test runner: this checkout's api image, plus the tools the suite is
# driven with. pytest.yml builds this stage, so `./al pytest` and `./al nox`
# run on the system the api runs on -- the same Python, ImageMagick policy and
# fonts -- built from the same commit.
#
# It was a Dockerfile of its own in tests/, `FROM alfred_api`: a local tag,
# resolved to whichever image last carried it on the machine running the
# suite. Nothing tied that image to the checkout under test -- every test image
# built during the 0.3.x review sat on one from two months before it -- and on
# a machine that had never built the dev stack there was no such image at all,
# so the build went to Docker Hub for `alfred_api` and was refused. The suite
# installs the application into a virtualenv of its own; what this stage
# contributes is the system underneath, and nothing kept that in step.
FROM api AS test
COPY tests/requirements-tests.txt .
RUN pip3 install -r ./requirements-tests.txt
ENTRYPOINT [ "nox" ]
CMD [ "-f", "tests/noxfile.py" ]

# Last, so a build that names no target -- the api and renderer in every
# compose file -- gets the api image rather than the test runner.
FROM api
