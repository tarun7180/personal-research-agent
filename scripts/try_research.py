import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="  %(message)s")

from pra.budget import Budget
from pra.llm.anthropic_client import AnthropicClient
from pra.research import research
from pra.tools.notes import NoteBook
from pra.tools.search import TavilySearch

question = "How does retrieval-augmented generation differ from fine-tuning?"
notebook = NoteBook()
status = research(question, AnthropicClient(), TavilySearch(), notebook,
                  Budget(max_steps=15))
print("\nSTATUS:", status)
for n in notebook.notes:
    print("-", n.facts, "|", n.source_url)