import html

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from webcheck.main import CheckResult, check_all, normalize_urls


app = FastAPI(title="HTTPX Rich Asyncio Demo")


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return render_page()


@app.post("/check", response_class=HTMLResponse)
async def check(urls: str = Form(...), timeout: float = Form(5.0)) -> str:
    # O formulario manda um textao; cada linha vira uma URL.
    parsed_urls = normalize_urls(line.strip() for line in urls.splitlines() if line.strip())
    results = await check_all(parsed_urls, timeout=timeout, show_progress=False)
    return render_page(urls=urls, timeout=timeout, results=results)


def render_page(urls: str = "", timeout: float = 5.0, results: list[CheckResult] | None = None) -> str:
    table = render_results(results or [])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Async URL Checker</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #667085;
      --line: #d8dee8;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --accent: #0f766e;
      --fail: #b42318;
      --ok: #027a48;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    main {{
      width: min(1080px, calc(100% - 32px));
      margin: 32px auto;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 32px;
      letter-spacing: 0;
    }}
    p {{ margin: 0; color: var(--muted); }}
    form {{
      display: grid;
      gap: 12px;
      padding: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    label {{ font-weight: 700; }}
    textarea, input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      background: white;
    }}
    textarea {{ min-height: 132px; resize: vertical; }}
    .controls {{
      display: grid;
      grid-template-columns: 160px max-content;
      gap: 12px;
      align-items: end;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 11px 16px;
      font: inherit;
      font-weight: 800;
      color: white;
      background: var(--accent);
      cursor: pointer;
    }}
    table {{
      width: 100%;
      margin-top: 18px;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 11px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #eef2f6; font-size: 14px; }}
    tr:last-child td {{ border-bottom: 0; }}
    a {{ color: var(--accent); }}
    .ok {{ color: var(--ok); font-weight: 800; }}
    .fail {{ color: var(--fail); font-weight: 800; }}
    @media (max-width: 720px) {{
      header {{ display: block; }}
      .controls {{ grid-template-columns: 1fr; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Async URL Checker</h1>
        <p>FastAPI page powered by httpx, asyncio, and a shared Python checker.</p>
      </div>
    </header>

    <form method="post" action="/check">
      <label for="urls">URLs</label>
      <textarea id="urls" name="urls" placeholder="https://example.com&#10;https://python.org">{html.escape(urls)}</textarea>
      <div class="controls">
        <div>
          <label for="timeout">Timeout</label>
          <input id="timeout" name="timeout" type="number" min="1" max="30" step="0.5" value="{timeout}">
        </div>
        <button type="submit">Check URLs</button>
      </div>
    </form>

    {table}
  </main>
</body>
</html>
"""


def render_results(results: list[CheckResult]) -> str:
    if not results:
        return ""

    rows = "\n".join(
        "<tr>"
        f"<td class=\"{'ok' if result.ok else 'fail'}\">{'OK' if result.ok else 'FAIL'}</td>"
        f"<td>{html.escape(str(result.status_code or '-'))}</td>"
        f"<td>{result.elapsed_ms} ms</td>"
        f"<td>{html.escape(result.content_type)}</td>"
        f"<td><a href=\"{html.escape(result.url)}\">{html.escape(result.url)}</a></td>"
        f"<td>{html.escape(result.title or result.error)}</td>"
        "</tr>"
        for result in results
    )

    return f"""<table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Code</th>
          <th>Time</th>
          <th>Content Type</th>
          <th>URL</th>
          <th>Title / Error</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>"""
