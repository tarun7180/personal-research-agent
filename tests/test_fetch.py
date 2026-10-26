import httpx

from pra.tools.fetch import fetch_page

ARTICLE = (
    "<html><head><title>RAG explained</title></head><body><article>"
    + "".join(
        f"<p>Retrieval-augmented generation combines a search step with a language "
        f"model so answers can cite their sources. This is paragraph {i}.</p>"
        for i in range(8)
    )
    + "</article></body></html>"
)
HTML = {"content-type": "text/html; charset=utf-8"}


def make_client(routes):
    def handler(request):
        if request.url.path in routes:
            status, headers, body = routes[request.url.path]
            return httpx.Response(status, headers=headers, content=body)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_html_success():
    client = make_client({"/a": (200, HTML, ARTICLE)})
    page = fetch_page("https://example.com/a", client=client)
    assert page.error is None
    assert "Retrieval-augmented generation" in page.text
    assert page.title == "RAG explained"


def test_http_error():
    page = fetch_page("https://example.com/missing", client=make_client({}))
    assert page.error == "HTTP 404"


def test_blocked_by_robots():
    client = make_client({
        "/robots.txt": (200, {}, "User-agent: *\nDisallow: /private"),
        "/private/x": (200, HTML, ARTICLE),
    })
    page = fetch_page("https://example.com/private/x", client=client)
    assert page.error == "blocked by robots.txt"


def test_bad_scheme():
    page = fetch_page("ftp://example.com/file")
    assert page.error == "unsupported or invalid URL"


def test_unsupported_content_type():
    client = make_client({"/img": (200, {"content-type": "image/png"}, b"\x89PNG")})
    page = fetch_page("https://example.com/img", client=client)
    assert page.error.startswith("unsupported content type")


def test_network_error():
    def boom(request):
        raise httpx.ConnectError("down")

    client = httpx.Client(transport=httpx.MockTransport(boom))
    page = fetch_page("https://example.com/a", client=client)
    assert page.error.startswith("request failed")