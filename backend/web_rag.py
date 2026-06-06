"""
web_rag.py — Real-time Web-RAG (Retrieval-Augmented Generation) pipeline.

Pipeline:
  1. Intent Detection & Query Reformulation  (Gemini)
  2. Google Search                           (requests + scraping)
  3. Web Page Scraping & Parsing             (BeautifulSoup)
  4. Context Synthesis                       (Gemini)
"""

import datetime
import logging
import re
import urllib.parse
import time

import requests

from backend.config import GEMINI_API_KEY
from backend.monitor import log_api_call, log_error

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

_SCRAPE_TIMEOUT = 8          # seconds per page fetch
_MAX_SCRAPE_PAGES = 3        # number of top results to deep-scrape
_MAX_CHARS_PER_PAGE = 4000   # truncate scraped text per page
_MAX_CONTEXT_CHARS = 12000   # total context limit sent to the LLM


# ─────────────────────────────────────────────────────────────────────────────
# 1. INTENT DETECTION & QUERY REFORMULATION
# ─────────────────────────────────────────────────────────────────────────────
def detect_search_intent_and_reformulate(query: str, current_time: str) -> dict:
    """
    Use Gemini to decide if a query needs a live web search
    and, if so, produce an optimised search-engine query.

    Returns:
        {
            "search_required": True/False,
            "search_query": "optimised query string" | None,
            "reason": "brief explanation"
        }
    """
    from google import genai

    if not GEMINI_API_KEY:
        # If no API key, assume search is needed and use the raw query
        return {"search_required": True, "search_query": query, "reason": "No API key — defaulting to search."}

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = (
        "You are a search-intent classifier. "
        f"The current date and time is: {current_time}.\n\n"
        "Given the user's query below, decide:\n"
        "1. Does this query require a LIVE web search to answer accurately?\n"
        "   - Queries about recent events, news, scores, stock prices, weather, "
        "current people/facts that change => YES\n"
        "   - Creative tasks (write a poem, tell a joke), general knowledge that "
        "doesn't change, math, coding help => NO\n"
        "2. If YES, rewrite the query into an optimised Google search query. "
        "Resolve relative dates (e.g. 'yesterday' => the actual date), expand "
        "abbreviations, and add context.\n\n"
        f"User query: \"{query}\"\n\n"
        "Respond in EXACTLY this format (no markdown, no extra text):\n"
        "SEARCH_REQUIRED: YES or NO\n"
        "SEARCH_QUERY: <optimised query or NONE>\n"
        "REASON: <one-sentence explanation>"
    )

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
    response = None

    start = time.time()
    success = False
    used_model = None
    last_err = None
    try:
        for idx, model_name in enumerate(models_to_try):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                success = True
                used_model = model_name
                break
            except Exception as e:
                logger.warning("Intent detection model %s failed: %s", model_name, e)
                last_err = e
                if idx < len(models_to_try) - 1:
                    continue
                raise
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log_api_call(
            service="intent_detection",
            model="gemini-2.5-flash",
            latency_ms=elapsed,
            success=False,
            error_msg=str(e)
        )
        log_error("intent_detection", f"Intent detection failed: {e}", severity="warning")
        raise

    elapsed = int((time.time() - start) * 1000)
    tokens_used = 0
    if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens_used = getattr(response.usage_metadata, 'total_token_count', 0)

    log_api_call(
        service="intent_detection",
        model=used_model,
        latency_ms=elapsed,
        tokens_used=tokens_used,
        success=True
    )

    if not response or not response.text:
        return {"search_required": True, "search_query": query, "reason": "LLM returned empty — defaulting to search."}

    text = response.text.strip()
    logger.info("Intent detection raw response:\n%s", text)

    # Parse the structured response
    result = {"search_required": False, "search_query": None, "reason": ""}

    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("SEARCH_REQUIRED:"):
            value = line.split(":", 1)[1].strip().upper()
            result["search_required"] = value == "YES"
        elif line.upper().startswith("SEARCH_QUERY:"):
            value = line.split(":", 1)[1].strip()
            if value.upper() != "NONE":
                result["search_query"] = value
        elif line.upper().startswith("REASON:"):
            result["reason"] = line.split(":", 1)[1].strip()

    # Safety: if search is required but no query was produced, use the original
    if result["search_required"] and not result["search_query"]:
        result["search_query"] = query

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. GOOGLE SEARCH
# ─────────────────────────────────────────────────────────────────────────────
def google_search(query: str, num_results: int = 5) -> list[dict]:
    """
    Scrape Google search results and return a list of dicts:
        [{"title": ..., "url": ..., "snippet": ...}, ...]
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 is not installed. Run: pip install beautifulsoup4")
        return []

    encoded_query = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded_query}&gbv=1&num={num_results + 3}"

    start = time.time()
    try:
        resp = requests.get(url, headers=_SEARCH_HEADERS, timeout=_SCRAPE_TIMEOUT)
        elapsed = int((time.time() - start) * 1000)
        if resp.status_code == 200:
            log_api_call("google_search", latency_ms=elapsed, success=True)
        else:
            logger.warning("Google search returned status %d", resp.status_code)
            log_api_call("google_search", latency_ms=elapsed, success=False, error_msg=f"HTTP status {resp.status_code}")
            return []
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.error("Google search request failed: %s", e)
        log_api_call("google_search", latency_ms=elapsed, success=False, error_msg=str(e))
        log_error("google_search", f"Google search request failed: {e}", severity="warning")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for g in soup.find_all("div", class_="g"):
        link_el = g.find("a")
        title_el = g.find("h3")

        # Try multiple selectors for the snippet
        snippet_el = (
            g.find("span", class_="st")
            or g.find("div", class_="VwiC3b")
            or g.find("span", class_="aCOpRe")
        )
        if not snippet_el:
            for s in g.find_all("span"):
                if len(s.get_text().strip()) > 30:
                    snippet_el = s
                    break

        if not link_el:
            continue

        href = link_el.get("href", "")
        # Google wraps links in /url?q=<actual_url>
        if href.startswith("/url?q="):
            parsed = urllib.parse.urlparse(href)
            qs = urllib.parse.parse_qs(parsed.query)
            if "q" in qs:
                href = qs["q"][0]

        if not href.startswith("http"):
            continue

        title = title_el.get_text().strip() if title_el else "Search Result"
        snippet = snippet_el.get_text().strip() if snippet_el else ""

        # Deduplicate by URL
        if href not in [r["url"] for r in results]:
            results.append({"title": title, "url": href, "snippet": snippet})

        if len(results) >= num_results:
            break

    logger.info("Google search returned %d results for: %s", len(results), query)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 3. WEB PAGE SCRAPING & PARSING
# ─────────────────────────────────────────────────────────────────────────────
def scrape_url(url: str) -> str:
    """
    Fetch a web page and extract clean body text.
    Returns the extracted text (truncated to _MAX_CHARS_PER_PAGE) or an empty string on failure.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    start = time.time()
    try:
        resp = requests.get(url, headers=_SEARCH_HEADERS, timeout=_SCRAPE_TIMEOUT)
        elapsed = int((time.time() - start) * 1000)
        if resp.status_code == 200:
            log_api_call("web_scrape", latency_ms=elapsed, success=True)
        else:
            log_api_call("web_scrape", latency_ms=elapsed, success=False, error_msg=f"HTTP status {resp.status_code}")
            return ""
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.warning("Failed to scrape %s: %s", url, e)
        log_api_call("web_scrape", latency_ms=elapsed, success=False, error_msg=str(e))
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove unwanted elements
    for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                              "aside", "iframe", "noscript", "form", "button"]):
        tag.decompose()

    # Extract text from content-rich elements
    paragraphs = []
    for el in soup.find_all(["p", "li", "td", "h1", "h2", "h3", "h4", "article"]):
        text = el.get_text(separator=" ", strip=True)
        # Only keep paragraphs with meaningful content
        if len(text) > 40:
            paragraphs.append(text)

    full_text = "\n".join(paragraphs)

    # Truncate to limit
    if len(full_text) > _MAX_CHARS_PER_PAGE:
        full_text = full_text[:_MAX_CHARS_PER_PAGE] + "..."

    return full_text


def build_rag_context(search_results: list[dict]) -> tuple[str, list[dict]]:
    """
    Given search results, scrape the top pages and build a combined context string.

    Returns:
        (context_text, sources_list)
    """
    context_parts = []
    sources = []
    total_chars = 0

    for i, result in enumerate(search_results[:_MAX_SCRAPE_PAGES]):
        url = result["url"]
        title = result["title"]
        snippet = result.get("snippet", "")

        logger.info("Scraping [%d/%d]: %s", i + 1, _MAX_SCRAPE_PAGES, url)
        page_text = scrape_url(url)

        # Use page text if available, otherwise fall back to snippet
        content = page_text if page_text else snippet

        if content:
            source_num = len(sources) + 1
            context_parts.append(
                f"[Source {source_num}] {title}\n"
                f"URL: {url}\n"
                f"Content:\n{content}\n"
            )
            sources.append({"title": title, "url": url})
            total_chars += len(content)

        if total_chars >= _MAX_CONTEXT_CHARS:
            break

    context_text = "\n---\n".join(context_parts)

    # Final truncation safety net
    if len(context_text) > _MAX_CONTEXT_CHARS:
        context_text = context_text[:_MAX_CONTEXT_CHARS] + "\n...[truncated]"

    return context_text, sources


# ─────────────────────────────────────────────────────────────────────────────
# 4. LLM CONTEXT SYNTHESIS
# ─────────────────────────────────────────────────────────────────────────────
def synthesize_response(query: str, context: str, sources: list[dict], current_time: str) -> str:
    """
    Send the user's query + scraped web context to Gemini
    and return a comprehensive, cited answer.
    """
    from google import genai

    if not GEMINI_API_KEY:
        return "Gemini API key is not configured."

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Build a source reference block for the prompt
    source_refs = "\n".join(
        f"[{i + 1}] {s['title']} — {s['url']}" for i, s in enumerate(sources)
    )

    system_instruction = (
        "You are Jarvis, an AI desktop assistant with access to real-time web search results. "
        f"The current date and time is {current_time}. "
        "Answer the user's question accurately and comprehensively using ONLY the provided search context. "
        "Cite your sources using numbered references like [1], [2], etc. "
        "If the search context does not contain enough information, say so honestly. "
        "Detect the language of the user's input. "
        "If the user talks in Hinglish (Hindi written in Latin/Roman script), reply in Hinglish. "
        "If the user talks in Urdu (either in Urdu script or Romanized Urdu), understand their query and reply in English. "
        "Otherwise, respond in the language of the query or English. "
        "Keep your response concise but informative."
    )

    user_prompt = (
        f"User Question: {query}\n\n"
        f"--- SEARCH RESULTS ---\n{context}\n\n"
        f"--- SOURCES ---\n{source_refs}\n\n"
        "Please provide a comprehensive answer based on the search results above. "
        "Cite sources using [1], [2], etc."
    )

    start = time.time()
    success = False
    used_model = None
    last_err = None
    try:
        for idx, model_name in enumerate(models_to_try):
            try:
                logger.info("Synthesis using model: %s", model_name)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        {"role": "user", "parts": [{"text": f"System: {system_instruction}\n\n{user_prompt}"}]}
                    ],
                )
                success = True
                used_model = model_name
                break
            except Exception as e:
                logger.warning("Synthesis model %s failed: %s", model_name, e)
                last_err = e
                if idx < len(models_to_try) - 1:
                    continue
                raise
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log_api_call(
            service="rag_synthesis",
            model="gemini-2.5-flash",
            latency_ms=elapsed,
            success=False,
            error_msg=str(e)
        )
        log_error("rag_synthesis", f"RAG synthesis failed: {e}", severity="error")
        raise

    elapsed = int((time.time() - start) * 1000)
    tokens_used = 0
    if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
        tokens_used = getattr(response.usage_metadata, 'total_token_count', 0)

    log_api_call(
        service="rag_synthesis",
        model=used_model,
        latency_ms=elapsed,
        tokens_used=tokens_used,
        success=True
    )

    if not response or not response.text:
        return "I wasn't able to generate an answer from the search results."

    return response.text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# 5. FULL RAG PIPELINE  (called from feature.py)
# ─────────────────────────────────────────────────────────────────────────────
def run_rag_pipeline(query: str, status_callback=None) -> tuple[str, list[dict]]:
    """
    Execute the complete Web-RAG pipeline:
        Intent → Search → Scrape → Synthesize

    Args:
        query:            The user's raw question.
        status_callback:  Optional callable(step_emoji, message) for live UI updates.

    Returns:
        (answer_text, sources_list)
        If no search is required, returns (None, None) so the caller can
        fall back to the normal Gemini chatbot path.
    """

    def _status(emoji: str, msg: str):
        if status_callback:
            try:
                status_callback(emoji, msg)
            except Exception:
                pass
        logger.info("[RAG] %s %s", emoji, msg)

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Step 1: Intent Detection ──────────────────────────────────────────
    _status("🔍", "Classifying your query...")
    try:
        intent = detect_search_intent_and_reformulate(query, current_time)
    except Exception as e:
        logger.error("Intent detection failed: %s", e)
        intent = {"search_required": True, "search_query": query, "reason": "Error — defaulting to search."}

    if not intent["search_required"]:
        _status("💡", f"No search needed — {intent.get('reason', 'answering directly.')}")
        return None, None  # Signal the caller to use normal Gemini

    search_query = intent["search_query"] or query
    _status("🔎", f"Searching: \"{search_query}\"")

    # ── Step 2: Google Search ─────────────────────────────────────────────
    _status("🌐", "Querying Google...")
    search_results = google_search(search_query)

    if not search_results:
        _status("⚠️", "No search results found.")
        return None, None  # Fall back to normal Gemini

    _status("📄", f"Found {len(search_results)} results — scraping top pages...")

    # ── Step 3: Scrape & Build Context ────────────────────────────────────
    context, sources = build_rag_context(search_results)

    if not context.strip():
        _status("⚠️", "Could not extract content from search results.")
        return None, None

    _status("🧠", "Synthesizing answer from web data...")

    # ── Step 4: LLM Synthesis ─────────────────────────────────────────────
    try:
        answer = synthesize_response(query, context, sources, current_time)
    except Exception as e:
        logger.error("Synthesis failed: %s", e)
        # Return what we have from search snippets as a fallback
        snippet_answer = "Here's what I found:\n\n"
        for i, r in enumerate(search_results[:3]):
            snippet_answer += f"[{i + 1}] {r['title']}: {r.get('snippet', 'No snippet available.')}\n"
        return snippet_answer, sources

    _status("✅", "Answer ready!")
    return answer, sources
