from playwright.sync_api import sync_playwright
from app.config import settings
from app.models.schemas import ApplicationObservation,ElementInfo

class BrowserExplorer:
    def explore(self,url):
        
        print()
        print("=" * 70)
        print("[AIVAR - STEP 1] APPLICATION EXPLORATION")
        print("=" * 70)
        print(f"[INPUT] URL: {url}")
        print("[ACTION] Launching Playwright browser...")

        with sync_playwright() as p:
            b=p.chromium.launch(headless=settings.HEADLESS); page=b.new_page(); page.goto(url,wait_until="domcontentloaded",timeout=15000)
            els=[]
            for loc in page.locator("button,input,a,select,textarea,h1,h2,h3").all()[:150]:
                try:
                    tag=loc.evaluate("e=>e.tagName.toLowerCase()")
                    text=(loc.inner_text(timeout=500) if tag in ("button","a","h1","h2","h3") else "").strip()
                    els.append(ElementInfo(tag=tag,text=text[:120],role=loc.get_attribute("role"),name=loc.get_attribute("name"),label=loc.get_attribute("aria-label"),selector_hint=loc.get_attribute("data-testid") or loc.get_attribute("id") or loc.get_attribute("data-product-id")))
                except Exception: pass
            links=[]
            for a in page.locator("a").all()[:50]:
                try:
                    h=a.get_attribute("href")
                    if h: links.append(h)
                except Exception: pass
            forms=[]
            for f in page.locator("form").all()[:20]:
                try: forms.append((f.inner_text(timeout=500) or "")[:300])
                except Exception: pass
            out=ApplicationObservation(url=url,title=page.title(),page_text=(page.locator("body").inner_text(timeout=2000) or "")[:5000],elements=els,links=links,forms=forms); 
            print("[OUTPUT] Application exploration completed")
            print(f"[OUTPUT] Page title: {out.title}")
            print(f"[OUTPUT] Page URL: {out.url}")
            print(f"[OUTPUT] Elements discovered: {len(out.elements)}")
            print(f"[OUTPUT] Links discovered: {len(out.links)}")
            print(f"[OUTPUT] Forms discovered: {len(out.forms)}")

            print("[OUTPUT] Elements:")
            for element in out.elements:
                print(
                    f"        tag={element.tag}, "
                    f"text='{element.text}', "
                    f"role={element.role}, "
                    f"label={element.label}"
                )

            print("=" * 70)
            b.close(); return out
