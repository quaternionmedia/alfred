# Pinned by digest; bump it on purpose. See docs/build.md#the-image.
FROM python:3.11@sha256:d0199e2a90bf7a206a485b115323a75bc946f30b463d704c5435a454aca084dd AS api

WORKDIR /app

COPY pyproject.toml README.md requirements.lock requirements-render.lock ./
COPY alfred alfred

# The locks exactly, with --no-deps: pip resolves nothing.
# See docs/dependencies.md#lockfiles.
RUN pip3 install --no-cache-dir --no-deps -r requirements.lock -r requirements-render.lock

# The engines from their submodules; their dependencies are in the locks.
RUN pip3 install --no-deps -e alfred/otto
RUN pip3 install --no-deps -e alfred/vox
RUN pip3 install --no-deps -e .
# Not locked (a dev dependency): floats.
RUN pip3 install uvicorn

# SECURITY: removes ImageMagick's whole policy, 6 and 7. Open: relax only
# what moviepy's text needs. See docs/build.md#imagemagicks-policy.
RUN rm -f /etc/ImageMagick-6/policy.xml /etc/ImageMagick-7/policy.xml

# Courier, Helvetica and Times, which the text templates draw with.
# See docs/build.md#fonts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-urw-base35 \
    && rm -rf /var/lib/apt/lists/*

CMD ["uvicorn", "alfred.main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]


# The test runner (pytest.yml): the api image of this commit, plus nox.
FROM api AS test
COPY tests/requirements-tests.txt .
RUN pip3 install -r ./requirements-tests.txt
ENTRYPOINT [ "nox" ]
CMD [ "-f", "tests/noxfile.py" ]

# Last: a build with no target gets the api, not the test runner.
FROM api
