FROM alfred_api

COPY requirements-tests.txt .
RUN pip3 install -r ./requirements-tests.txt

ENTRYPOINT [ "nox" ]

CMD [ "-f", "tests/noxfile.py" ]