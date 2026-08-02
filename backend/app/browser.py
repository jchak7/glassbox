"""Playwright wrapper: one browser session per run, with page distillation.

The agent never sees raw HTML. Every step we "distill" the page into a
compact, numbered inventory of interactive elements plus a text excerpt.
Elements get a data-gbid attribute so actions can target them precisely.
"""

import base64
import os
from playwright.async_api import async_playwright

# Public sites like SEC EDGAR gate datacenter traffic behind a fair-access
# wall and demand a *declared* User-Agent (name + contact), not a browser
# masquerade. A browser-looking UA from a cloud IP is the worst combination
# and gets a site-wide block. This default declares who we are and how to
# reach us; override per-deploy with GLASSBOX_USER_AGENT if a target needs
# something else — no rebuild required.
DEFAULT_UA = os.environ.get(
    "GLASSBOX_USER_AGENT",
    "Glassbox-Agent/1.0 (autonomous browser agent; "
    "contact: glassbox-demo@example.com)",
)

DISTILL_JS = """
() => {
  document.querySelectorAll('[data-gbid]').forEach(el => el.removeAttribute('data-gbid'));
  const sels = 'a[href], button, input, select, textarea, summary, ' +
    '[role="button"], [role="link"], [role="tab"], [role="menuitem"], ' +
    '[role="combobox"], [role="option"], [onclick], [type="submit"]';
  const seen = new Set();
  const out = [];
  let i = 0;
  for (const el of document.querySelectorAll(sels)) {
    if (seen.has(el)) continue;
    seen.add(el);
    const r = el.getBoundingClientRect();
    const st = window.getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none') continue;
    i += 1;
    el.setAttribute('data-gbid', String(i));
    const tag = el.tagName.toLowerCase();
    let label = '';
    if (tag === 'input' || tag === 'textarea') {
      label = el.getAttribute('placeholder') || el.getAttribute('aria-label') ||
              el.getAttribute('name') || el.value || '';
    } else if (tag === 'select') {
      label = el.getAttribute('name') || el.getAttribute('aria-label') || '';
    } else {
      label = (el.innerText || el.getAttribute('aria-label') ||
               el.getAttribute('title') || el.getAttribute('value') || '');
    }
    label = label.trim().replace(/\\s+/g, ' ').slice(0, 90);
    const entry = { id: i, tag, label };
    const type = el.getAttribute('type');
    if (type) entry.type = type;
    if (tag === 'a') entry.href = (el.getAttribute('href') || '').slice(0, 120);
    if (tag === 'select') {
      entry.options = Array.from(el.options).slice(0, 25).map(o => o.value || o.text);
    }
    entry.inView = r.top < window.innerHeight && r.bottom > 0;
    out.push(entry);
  }
  return {
    elements: out,
    text: document.body ? document.body.innerText : '',
    scrollY: Math.round(window.scrollY),
    scrollMax: Math.max(0, Math.round(
      (document.documentElement.scrollHeight || 0) - window.innerHeight)),
  };
}
"""

TEXT_CHUNK = 3500  # chars of page text shown to the model per read


class BrowserSession:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw = None
        self.browser = None
        self.page = None
        self._text_offset = 0  # paging cursor for read_more on long documents
        self._last_text = ""

    async def start(self):
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        ctx = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=DEFAULT_UA,
        )
        ctx.set_default_timeout(12_000)
        self.page = await ctx.new_page()

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    # ---- observations -------------------------------------------------

    async def screenshot_b64(self) -> str:
        # animations="disabled" is essential: pages with looping CSS/chart
        # animations (financial dashboards especially) make Playwright wait
        # for a stability that never arrives. Explicit timeout on top.
        img = await self.page.screenshot(
            type="jpeg", quality=55, timeout=8_000, animations="disabled")
        return base64.b64encode(img).decode()

    async def distill(self, fresh_text: bool = True) -> dict:
        """Compact page state for the model. Long text is paged via read_more."""
        try:
            raw = await self.page.evaluate(DISTILL_JS)
        except Exception as e:
            return {"url": self.page.url, "title": "", "error": f"distill failed: {e}",
                    "elements_desc": "", "text": ""}
        if fresh_text:
            self._last_text = " ".join(raw["text"].split())
            self._text_offset = 0
        chunk = self._last_text[self._text_offset:self._text_offset + TEXT_CHUNK]
        remaining = max(0, len(self._last_text) - (self._text_offset + TEXT_CHUNK))
        lines = []
        for el in raw["elements"][:120]:
            bits = [f"[{el['id']}] <{el['tag']}"]
            if el.get("type"):
                bits.append(f" type={el['type']}")
            bits.append(">")
            if el.get("label"):
                bits.append(f" {el['label']!r}")
            if el.get("href"):
                bits.append(f" -> {el['href']}")
            if el.get("options"):
                bits.append(f" options={el['options']}")
            if not el.get("inView"):
                bits.append(" (below fold)")
            lines.append("".join(bits))
        hidden = max(0, len(raw["elements"]) - 120)
        if hidden:
            lines.append(f"... and {hidden} more elements (scroll to reveal)")
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "elements_desc": "\n".join(lines),
            "text": chunk,
            "text_remaining": remaining,
            "scroll": f"{raw['scrollY']}/{raw['scrollMax']}px",
        }

    def read_more(self) -> dict:
        """Advance the text cursor — lets the model page through huge documents
        (e.g. SEC filings) without re-rendering or re-tokenizing everything."""
        self._text_offset += TEXT_CHUNK
        chunk = self._last_text[self._text_offset:self._text_offset + TEXT_CHUNK]
        remaining = max(0, len(self._last_text) - (self._text_offset + TEXT_CHUNK))
        return {"text": chunk, "text_remaining": remaining, "offset": self._text_offset}

    # ---- actions ------------------------------------------------------

    async def goto(self, url: str):
        if not url.startswith(("http://", "https://", "/")):
            url = "https://" + url
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await self._settle()

    async def click(self, element_id: int):
        loc = self.page.locator(f'[data-gbid="{element_id}"]')
        if await loc.count() == 0:
            raise ValueError(f"element [{element_id}] no longer exists on this page")
        await loc.first.scroll_into_view_if_needed()
        await loc.first.click()
        await self._settle()

    async def type_text(self, element_id: int, text: str, press_enter: bool = False):
        loc = self.page.locator(f'[data-gbid="{element_id}"]')
        if await loc.count() == 0:
            raise ValueError(f"element [{element_id}] no longer exists on this page")
        await loc.first.fill(text)
        if press_enter:
            await loc.first.press("Enter")
        await self._settle()

    async def select_option(self, element_id: int, value: str):
        loc = self.page.locator(f'[data-gbid="{element_id}"]')
        if await loc.count() == 0:
            raise ValueError(f"element [{element_id}] no longer exists on this page")
        try:
            await loc.first.select_option(value)
        except Exception:
            await loc.first.select_option(label=value)
        await self._settle()

    async def scroll(self, direction: str = "down"):
        dy = 600 if direction == "down" else -600
        await self.page.mouse.wheel(0, dy)
        await self.page.wait_for_timeout(300)

    async def go_back(self):
        await self.page.go_back(wait_until="domcontentloaded")
        await self._settle()

    async def _settle(self):
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=8_000)
            await self.page.wait_for_timeout(600)
        except Exception:
            pass  # a page that never settles is still observable
