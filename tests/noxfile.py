import nox


@nox.session
def blacken(session):
    session.install("black")
    session.run("black", "-v", ".")
    # session.run("black", "-v", "..")


@nox.session
def lint(session):
    session.install("flake8")
    session.run("flake8", "-v", ".")


@nox.session(python="3.9", tags=["test"])
def coverage(session):
    session.install("-r", "../requirements.txt")
    session.install("-r", "requirements-tests.txt")
    session.install("-r", "../alfred/otto/requirements.txt")
    session.install("-e", "../alfred/otto")
    session.install("-e", "..")
    session.run(
        "pytest",
        "-vv",
        "--timeout=600",
        "-n",
        "auto",
    )
