#!/usr/bin/env python
"""Test server to verify UI routes work."""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def test_home(request: Request):
    """Test home page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <h1>UI Routes Working!</h1>
        <p>This is the home page.</p>
        <a href="/bid">Go to Bid Form</a>
    </body>
    </html>
    """

@app.get("/bid", response_class=HTMLResponse)
async def test_bid(request: Request):
    """Test bid page."""
    # Try to render actual template
    try:
        from app.ui.state import get_current_state, set_state
        from app.ui.excel_mapper import create_sample_bid_form

        state = get_current_state()
        if not state:
            sample_state = create_sample_bid_form()
            set_state("test", sample_state)
            state = sample_state

        context = {
            "request": request,
            "bid_state": state,
            "sections": state.get_sections(),
            "format_currency": lambda x: f"${x:,.2f}",
            "difficulty_options": list(range(1, 6))
        }
        return templates.TemplateResponse("bid_form.html", context)
    except Exception as e:
        return f"""
        <html>
        <body>
            <h1>Error rendering bid form</h1>
            <pre>{str(e)}</pre>
        </body>
        </html>
        """

if __name__ == "__main__":
    import uvicorn
    print("Starting test UI server on http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)