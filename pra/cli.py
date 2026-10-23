import typer
from dotenv import load_dotenv

from pra.orchestrator import run

app = typer.Typer(add_completion=False)


@app.command()
def main(question: str) -> None:
    """Research QUESTION and print a cited report."""
    load_dotenv()
    typer.echo(run(question))


if __name__ == "__main__":
    app()
