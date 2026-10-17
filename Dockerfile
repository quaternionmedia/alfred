# Pinned by digest. Unpinned, this resolved to whatever `python:latest` meant
# on the day of the build, which reached Python 3.14 -- where setuptools is no
# longer bundled, so `pip install` of a dependency needing pkg_resources fails
# outright. Bump this deliberately, not implicitly.
FROM python:3.11@sha256:d0199e2a90bf7a206a485b115323a75bc946f30b463d704c5435a454aca084dd

WORKDIR /app
RUN mkdir -p data

COPY pyproject.toml README.md requirements.lock ./
COPY alfred alfred

# Pinned dependencies first, from the lockfile.
#
# This was `pip install -e .`, which re-resolves the loose ranges in
# pyproject.toml on every build -- so the image ran beanie 1.30, fastapi 0.125
# and motor 3.7 while the test suite ran 1.20, 0.100 and 3.2. The tests were
# not testing the versions the application used, and two builds a month apart
# were not the same application.
#
# Installing the pins before the project means pip already has every version
# resolved when `pip install -e .` runs, so the ranges cannot pull anything
# newer. `--no-deps` on the project install would be stricter still, but it
# would also silently skip a dependency added to pyproject.toml and not yet
# locked; letting pip check is the better failure.
RUN pip3 install --no-cache-dir -r requirements.lock

RUN BEZIER_NO_EXTENSION=true pip3 install -e alfred/otto[render]
RUN pip3 install -e . uvicorn

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
