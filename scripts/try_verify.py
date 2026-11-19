from dotenv import load_dotenv

load_dotenv()

from pra.budget import Budget
from pra.cli import make_llm
from pra.models import Page
from pra.tools.notes import NoteBook
from pra.verify import verify_report

PAGE = "RAG retrieves documents at query time and gives them to the model as context."

nb = NoteBook()
nb.add_source(Page(url="https://example.com/rag", title="RAG note", text=PAGE))
nb.save_note("https://example.com/rag", PAGE, "retrieves documents at query time")

body = ("RAG retrieves documents at query time [1]. "
        "RAG permanently changes the model weights [1]. "
        "RAG always reduces latency by 40 percent [1].")

out, summary = verify_report(body, nb, make_llm(), Budget())
print(out)
print()
print(summary)