# Pinned by digest. Unpinned, this resolved to whatever `python:latest` meant
# on the day of the build, which reached Python 3.14 -- where setuptools is no
# longer bundled, so `pip install` of a dependency needing pkg_resources fails
# outright. Bump this deliberately, not implicitly.
FROM python:3.11@sha256:d0199e2a90bf7a206a485b115323a75bc946f30b463d704c5435a454aca084dd

WORKDIR /app
RUN mkdir -p data

COPY pyproject.toml README.md ./
COPY alfred alfred

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

CMD ["uvicorn", "alfred.main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
