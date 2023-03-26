import nox
from os.path import join


@nox.session
def blacken(session):
    session.install("black")
    session.run("black", "-S", "-v", ".")


@nox.session
def lint(session):
    session.install("flake8")
    session.run("flake8", "-v", ".")


@nox.session(tags=["test"])
def coverage(session):
    session.install("-e", "../alfred/otto")
    session.install("-r", "requirements-tests.txt")
    session.install("-e", "..")
    session.run("mkdir", "-p", "data")
    session.run("mkdir", "-p", "dist")
    session.run("mkdir", "-p", "site")
    session.run("touch", join("dist", "index.html"))
    session.run(
        "pytest",
        "-vv",
        "--timeout=600",
        "-n",
        "auto",
    )
