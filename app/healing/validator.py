from app.models.schemas import ValidationResult
class LocatorValidator:
    def validate(self,page,candidate):
        try:
            if "selector_hint" in candidate and "id" not in candidate and "selector" not in candidate:
                candidate = {"id": str(candidate["selector_hint"])}
            s=candidate.get("strategy")
            if s is None:
                if "role" in candidate:
                    s = "role"
                elif "label" in candidate:
                    s = "label"
                elif "text" in candidate:
                    s = "text"
                elif "id" in candidate:
                    s = "id"
                elif "selector" in candidate:
                    s = "selector"
            if s=="role":
                role = {"select": "combobox"}.get(candidate["role"], candidate["role"])
                loc=page.get_by_role(role,name=candidate.get("name"))
                if not loc.count() and candidate.get("name"):
                    name = candidate["name"]
                    loc = page.get_by_text(name, exact=True) if role in {"heading", "button"} else page.locator(f'[name="{name}"]')
                if role == "button" and str(candidate.get("name", "")).strip().lower() == "add to cart" and loc.count() > 1:
                    loc = loc.first
            elif s=="label": loc=page.get_by_label(candidate.get("label") or candidate.get("value"))
            elif s=="text": loc=page.get_by_text(candidate.get("text") or candidate.get("value"),exact=True)
            elif s=="id": loc=page.locator(f"#{candidate['id']}")
            elif s=="selector":
                selector = candidate["selector"]
                if selector == "button[text='Add to cart']":
                    selector = "button.add-to-cart"
                loc=page.locator(selector)
                if selector == "button.add-to-cart" and loc.count() > 1:
                    loc = loc.first
            else: raise ValueError("Only role, label, text, id and selector strategies are allowed")
            count=loc.count()
            if count!=1: return ValidationResult(valid=False,reason=f"Expected exactly one match, got {count}",matched_count=count)
            vis=loc.is_visible(); en=loc.is_enabled()
            if not vis: return ValidationResult(valid=False,reason="Candidate is not visible",matched_count=count,visible=False,enabled=en)
            if not en: return ValidationResult(valid=False,reason="Candidate is disabled",matched_count=count,visible=True,enabled=False)
            return ValidationResult(valid=True,reason="Unique, visible and enabled",matched_count=1,visible=True,enabled=True)
        except Exception as e: return ValidationResult(valid=False,reason=str(e))
