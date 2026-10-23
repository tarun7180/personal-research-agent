"""Pipeline: plan -> research -> write -> verify."""
from pra.budget import Budget


def run(question: str, budget: Budget | None = None) -> str:
    budget = budget or Budget()
    # TODO: 1) plan  2) research loop per sub-question  3) write  4) verify
    return f"# Report\n\n(not implemented yet) Question: {question}\n"
