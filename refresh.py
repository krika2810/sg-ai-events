#!/usr/bin/env python3
"""
SG AI Events - daily refresh script.

Harvests AI events (Singapore physical + virtual) from Luma:
  1. Luma Singapore discover feed (keyword-filtered).
  2. TRUSTED calendars (AI-dedicated hosts: every event is kept).
  3. WATCH + discovered calendars (kept only on AI keyword match).
  4. data/manual-events.json (curated non-Luma entries; always preserved).
  5. New calendars spotted hosting AI events in Singapore are added to
     data/calendars.json so future runs watch them automatically.
  6. Curated public Meetup groups supplement online and Singapore discovery.

Past events are removed from the live listing once their end time has passed.
Upcoming events remain tracked unless explicitly excluded.

Run:  python3 refresh.py          (stdlib only, no dependencies)
Then commit + push, or deploy:    vercel deploy --prod --yes --token "$VERCEL_TOKEN"
"""
import json, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
SG_PLACE = "discplace-mUbtdfNjfWaLQ72"
NOW = datetime.now(timezone.utc)
PRUNE_BEFORE = NOW

# AI-dedicated calendars: keep ALL their events (SG physical or virtual)
TRUSTED_CALENDARS = {
    "cal-ERmmBH1GOCSMkgM": "Codex Community Singapore",
    "cal-63UOFcweB97l2gc": "Codex Community Events",
    "cal-Dkjza6RmAxAYMWj": "Claude SG Community",
    "cal-TOpA5LAFfuDeFpu": "Claude Community Events",
    "cal-E74MDlDKBaeAwXK": "The AI Collective",
    "cal-61Cv6COs4g9GKw7": "SpaceXAI Community",
    "cal-RxMeFi4lwLGXWjK": "SpaceXAI for Singapore",
    "cal-7Q5A70Bz5Idxopu": "Google DeepMind",
    "cal-yrYsEKDQ91hPMWy": "Build Club",
    "cal-iOipAs7mv59Hbuz": "OpenClaw Meetups",
    "cal-LwZbk7FBYGShUJS": "Llama Lounge",
    "cal-zUWmkxeBGlQQenp": "Air Street events",
    "cal-fr2yD6OOANXlGm5": "SG AI & Robotics Demo Nights",
    "cal-7xEpna9688PSFwd": "The AI Capitol / OpenBuilder",
    "cal-972ANGTZriNdiws": "SGInnovate",
    "cal-mLY1RVDaHpz9qkW": "Menlo Research",
    "cal-PKazQdrRmpFJSXz": "AI Builders",
    "cal-9g9YygWZPabmf8o": "Glints AI Transformation",
}
# General calendars: keep only AI-keyword matches
# Public Meetup groups with a verified, accessible event listing. Added after
# auditing future event yield; keep the list focused to avoid generic spam.
MEETUP_GROUPS = {
    "singapore-computer-vision-meetup": "Singapore AI, Machine Learning and Computer Vision Meetup",
    "ac-sin": "Analytics.Club Singapore",
    "ksug-sg": "KSUG.AI APAC",
    "global-ai-singapore-community": "Global AI Singapore",
    "singapore-artificial-intelligence": "Singapore Artificial Intelligence",
    "mindstone-singapore-ai-meetup": "Mindstone Singapore AI Meetup",
    "collabnix": "Collabnix - Singapore-located event check",
}

WATCH_CALENDARS = [
    "cal-LVWZwZgOAe63Rwv",  # GDG Singapore
    "cal-zwOmjavlPOCH4mp",  # Y Combinator
    "cal-LxSRAvoOnOWxF9M",  # Lenny's Newsletter Meetups
    "cal-Ve0M7LoDOpdnF3z",  # South Park Commons
    "cal-HImlOWziQ7yD36i",  # Design Buddies
    "cal-9FiK2oO6xKiqLTd",  # Reactor School
    "cal-0VIaDBPsW6guEgs",  # Tencent Cloud (hackathon)
    "cal-lOnTgBGmZlLJ6oC",  # Miro Community Events
    "cal-m6wm8HV54lYoRE3",  # Singapore Hardware Meetup
]

AI_KW = [" ai", "a.i.", "artificial intelligence", "llm", "agentic", "agent", "openai", "astra",
         "chatgpt", "codex", "anthropic", "claude", "xai", "grok", "cursor", "gpt",
         "gemini", "deepmind", "machine learning", "genai", "gen ai", "generative ai",
         "copilot", "mistral", "llama", "qwen", "deepseek", "hugging face", "langchain",
         "langfuse", "rag ", "vector", "foundation model", "vibe", "n8n", "perplexity",
         "minimax", "midjourney", "elevenlabs", "manus", "devin", "windsurf",
         "ai-native", "ai native", "mcp", "text-to", "diffusion", "transformer"]
VENDOR_KW = {
    "OpenAI": ["openai", "chatgpt", "codex", "gpt-"],
    "Anthropic": ["anthropic", "claude"],
    "xAI / SpaceXAI": ["xai", "grok", "spacexai", "spacex ai"],
    "Cursor": ["cursor"],
    "Google": ["gemini", "deepmind", "google ai", "build with ai"],
    "Meta": ["meta llama", "llama lounge"],
    "Mistral": ["mistral"],
    "NVIDIA": ["nvidia"],
    "AWS": ["aws", "amazon web services"],
    "Microsoft": ["copilot", "azure ai"],
    "Perplexity": ["perplexity"],
    "MiniMax": ["minimax"],
    "Miro": ["miro"],
    "Hugging Face": ["hugging face", "huggingface", "lerobot"],
    "ClickHouse": ["clickhouse"],
    "Base44": ["base44"],
    "Bitdeer": ["bitdeer"],
    "ElevenLabs": ["elevenlabs"],
    "Kiro": ["kiro"],
    "GMI Cloud": ["gmi cloud"],
    "Qwen / Alibaba": ["qwen"],
    "Daytona": ["daytona"],
    "Nosana": ["nosana"],
    "vLLM": ["vllm"],
    "Vultr": ["vultr"],
}


def get(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if "event-deleted" in body:
                return {"__deleted": True}
            if attempt == retries:
                print(f"  WARN fetch failed {url[:90]}: HTTP {e.code}", file=sys.stderr)
                return {}
            time.sleep(1.5)
        except Exception as e:
            if attempt == retries:
                print(f"  WARN fetch failed {url[:90]}: {e}", file=sys.stderr)
                return {}
            time.sleep(1.5)


def paged(base, max_pages=20):
    out, cursor = [], None
    for _ in range(max_pages):
        url = base + ("&" if "?" in base else "?") + "pagination_limit=50"
        if cursor:
            url += "&pagination_cursor=" + urllib.parse.quote(cursor)
        d = get(url)
        entries = d.get("entries", [])
        out.extend(entries)
        cursor = d.get("next_cursor")
        if not cursor or not entries:
            break
        time.sleep(0.3)
    return out


def norm(x, source):
    ev = x.get("event") or {}
    g = ev.get("geo_address_info") or {}
    loc_type = ev.get("location_type")
    # Luma location_type is an explicit enum; missing/unknown must not mean online.
    is_virtual = loc_type in ("online", "virtual", "hybrid", "zoom", "youtube", "teams", "google_meet", "meet", "webinar", "livestream", "stream", "hopin", "airmeet", "webex", "discord", "twitch")
    is_sg = (g.get("country_code") == "SG") or (
        ev.get("timezone") == "Asia/Singapore" and loc_type in ("offline", "hybrid"))
    city = " ".join(str(g.get(k) or "") for k in ("city", "city_state", "full_address", "address")).lower()
    if any(x in city for x in ("san francisco", "california", "united states", "new york", "london", "oslo", "bogota", "bogotá")):
        is_sg = False
    hosts = [(h.get("name") or "") for h in (x.get("hosts") or [])]
    cal = x.get("calendar") or {}
    hay = " ".join([ev.get("name") or ""] + hosts + [cal.get("name") or ""]).lower()
    vendors = [v for v, kws in VENDOR_KW.items() if any(k in hay for k in kws)]
    eid = ev.get("api_id") or x.get("event_api_id") or x.get("api_id")
    slug = ev.get("url")
    return {
        "id": eid,
        "url": ("https://lu.ma/" + slug) if slug else None,
        "name": ev.get("name") or "",
        "start": ev.get("start_at") or x.get("start_at"),
        "end": ev.get("end_at"),
        "tz": ev.get("timezone"),
        "virtual": is_virtual,
        "sg": is_sg,
        "venue": (g.get("full_address") or g.get("address") or ("Online" if is_virtual else (g.get("city_state") or g.get("city") or ""))),
        "hosts": hosts,
        "calendar": cal.get("name") or "",
        "calendar_id": ev.get("calendar_api_id"),
        "cover": ev.get("cover_url"),
        "guests": x.get("guest_count"),
        "vendors": vendors,
        "source": source,
        "kind": "luma",
        "_hay": hay,
    }


def luma_event_details(event_id, slug=None):
    """Re-read archived Luma events omitted from today's feeds, never trust stale dates."""
    if slug:
        data = get("https://api.luma.com/url?url=" + urllib.parse.quote(str(slug)))
        if data and data.get("kind") == "event":
            data = data.get("data") or {}
        elif not data.get("__deleted"):
            data = get("https://api.luma.com/event/get?event_api_id=" + urllib.parse.quote(str(event_id)))
    else:
        data = get("https://api.luma.com/event/get?event_api_id=" + urllib.parse.quote(str(event_id)))
    ev = data.get("event") if isinstance(data, dict) else None
    if data.get("__deleted"):
        return {"__deleted": True}
    if not ev:
        return None
    listing = {"event": ev, "hosts": data.get("hosts") or [], "calendar": data.get("calendar") or {},
               "guest_count": data.get("guest_count")}
    n = norm(listing, "luma-live-archive-check")
    if not n["id"] or not n["url"] or not n["start"]:
        return None
    n.pop("_hay", None)
    return n


def meetup_events(slug, expected_group):
    """Parse public Meetup SSR event data; only verified Singapore groups."""
    url = f"https://www.meetup.com/{slug}/events/"
    try:
        req = urllib.request.Request(url, headers=UA)
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        match = __import__("re").search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, __import__("re").S)
        if not match:
            print(f"  WARN Meetup listing had no event data: {slug}", file=sys.stderr)
            return []
        state = json.loads(match.group(1)).get("props", {}).get("pageProps", {}).get("__APOLLO_STATE__", {})
        group = next((v for k, v in state.items() if k.startswith("Group:")), {})
        group_name = group.get("name") or expected_group
        group_country = (group.get("country") or "").lower()
        group_city = (group.get("city") or "").lower()
        is_singapore_group = group_country == "sg" or group_city == "singapore"
        # Foreign groups are accepted only when the event venue itself is verified in Singapore.
        out = []
        for key, ev in state.items():
            if not key.startswith("Event:") or not ev.get("title") or ev.get("status") != "ACTIVE":
                continue
            title, desc = ev.get("title") or "", ev.get("description") or ""
            hay = (title + " " + desc).lower()
            if not any(k.strip().lower() in hay for k in AI_KW):
                continue
            start = ev.get("dateTime")
            if not start:
                continue
            end = ev.get("endTime") or start
            try:
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            except Exception:
                continue
            if end_dt <= NOW:
                continue
            event_type = (ev.get("eventType") or "").upper()
            is_virtual = event_type in ("ONLINE", "NETWORK")
            venue_data = ev.get("venue") or {}
            if isinstance(venue_data, dict) and venue_data.get("__ref"):
                venue_data = state.get(venue_data["__ref"]) or {}
            venue = "Online" if is_virtual else ", ".join(
                part for part in (venue_data.get("name"), venue_data.get("city"), venue_data.get("country")) if part)
            venue_scope = " ".join(str(venue_data.get(k) or "") for k in ("city", "country", "name")).lower()
            # Group geography alone is insufficient: exclude out-of-country
            # physical/hybrid meetups posted by a Singapore-based group.
            event_is_sg = any(x in venue_scope for x in ("singapore", " sg", "sg "))
            if not is_singapore_group and not event_is_sg:
                continue
            if is_singapore_group and not is_virtual and not event_is_sg:
                continue
            vendors = [v for v, kws in VENDOR_KW.items() if any(k in hay for k in kws)]
            out.append({
                "id": "meetup-" + str(ev.get("id") or key.split(":", 1)[-1]),
                "name": title, "url": ev.get("eventUrl") or url,
                "start": start, "end": end, "tz": ev.get("timezone") or "Asia/Singapore",
                "virtual": is_virtual, "sg": event_is_sg and not is_virtual,
                "venue": venue or ("Singapore" if event_is_sg and not is_virtual else "Online"),
                "hosts": [group_name], "calendar": group_name, "calendar_id": None,
                "cover": ((ev.get("displayPhoto") or {}).get("source")
                          if isinstance(ev.get("displayPhoto"), dict) else None),
                "guests": ev.get("goingCount"), "vendors": vendors,
                "source": "meetup:" + slug, "kind": "meetup",
                "first_seen": NOW.date().isoformat(), "last_seen": NOW.date().isoformat(),
            })
        return out
    except Exception as e:
        print(f"  WARN Meetup fetch failed {slug}: {e}", file=sys.stderr)
        return []


def sginnovate_page(path):
    """A www origin error must not erase an accessible owning bare-domain page."""
    errors = []
    for origin in ("https://www.sginnovate.com", "https://sginnovate.com"):
        try:
            req = urllib.request.Request(origin + path, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8", "replace")
            if origin == "https://sginnovate.com":
                print("  SGInnovate bare-domain fallback used: " + path)
            return body, origin + path
        except Exception as error:
            errors.append(type(error).__name__)
    raise RuntimeError("both owning origins unavailable: " + ", ".join(errors))


def sginnovate_schedule(detail):
    """Return only explicit start/end clocks. Never invent midnight or a duration."""
    import re, html
    match = re.search(r'<section[^>]+class=["\']schedule["\'][^>]*>(.*?)</section>', detail, re.S | re.I)
    if not match:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))
    text = re.sub(r"\s+", " ", text).strip()
    date = re.search(r"(?:Start Date|Date):\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text, re.I)
    end_date = re.search(r"End Date:\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text, re.I)
    clocks = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*(AM|PM)\s*(?:-|–|to)\s*(\d{1,2})(?:[:.](\d{2}))?\s*(AM|PM)", text, re.I)
    if not date or not clocks:
        return None
    def day(m):
        month = m.group(2)
        return datetime.strptime(" ".join(m.group(i) for i in (1, 2, 3)), "%d %b %Y" if len(month) == 3 else "%d %B %Y").date()
    def clock(hour, minute, ap):
        hour, minute = int(hour), int(minute or 0)
        if not 1 <= hour <= 12 or not 0 <= minute < 60:
            raise ValueError("invalid explicit clock")
        return hour % 12 + (12 if ap.upper() == "PM" else 0), minute
    start_day = day(date); finish_day = day(end_date) if end_date else start_day
    sh, sm = clock(*clocks.group(1, 2, 3)); eh, em = clock(*clocks.group(4, 5, 6))
    sg = timezone(timedelta(hours=8))
    start = datetime(start_day.year, start_day.month, start_day.day, sh, sm, tzinfo=sg)
    end = datetime(finish_day.year, finish_day.month, finish_day.day, eh, em, tzinfo=sg)
    if end <= start:
        return None
    location = re.search(r"Location:\s*(.+?)(?:$|\s+(?:Registration|Agenda|Schedule):)", text, re.I)
    if not location:
        return None
    venue = location.group(1).strip()
    is_virtual = bool(re.search(r"^(?:Online|Virtual|Zoom|Microsoft Teams|Google Meet)\b", venue, re.I))
    is_sg = not is_virtual and bool(re.search(r"Singapore|\b\d{6}\b", venue, re.I))
    if not (is_virtual or is_sg):
        return None
    return start, end, venue, is_virtual, is_sg


def sginnovate_events():
    """Check each dated AI listing independently; partial failure stays explicit."""
    import re, html
    try:
        listing, listing_url = sginnovate_page("/events")
    except Exception as error:
        print("  WARN SGInnovate listing failed: " + str(error), file=sys.stderr)
        return []
    out, seen = [], set()
    for card in re.split(r'<div class="col-md-6 col-lg-4 mb-4">', listing):
        link = re.search(r'href="(/event/[^"#?]+)"', card)
        title_m = re.search(r'<h4[^>]*>.*?<a[^>]*>(.*?)</a>', card, re.S)
        if not (link and title_m):
            continue
        path = link.group(1)
        if path in seen:
            continue
        seen.add(path)
        title = html.unescape(re.sub(r"<[^>]+>", " ", title_m.group(1))).strip()
        if not any(k.strip().lower() in title.lower() for k in AI_KW):
            continue
        try:
            detail, source_url = sginnovate_page(path)
            parsed = sginnovate_schedule(detail)
            if not parsed:
                print("  WARN SGInnovate explicit schedule/location unavailable; skipped " + source_url, file=sys.stderr)
                continue
            start, end, venue, is_virtual, is_sg = parsed
            if end <= NOW:
                continue
            detail_text = html.unescape(re.sub(r"<[^>]+>", " ", detail))
            family_only = bool(re.search(r"(?:Kids|Children|Family|Ages 7)[^<]{0,30}", title, re.I))
            note = "Family/children-focused event; check age requirements and fees with the organiser." if family_only else "Check the organiser page for registration requirements and fees."
            out.append({
                "id": "sginnovate-" + path.rsplit("/", 1)[-1], "name": title,
                "url": "https://sginnovate.com" + path,
                "start": start.isoformat(), "end": end.isoformat(), "tz": "Asia/Singapore",
                "virtual": is_virtual, "sg": is_sg, "venue": venue,
                "hosts": ["SGInnovate"], "calendar": "SGInnovate", "calendar_id": None,
                "cover": None, "guests": None, "note": note,
                "vendors": [v for v, kws in VENDOR_KW.items() if any(k in (title + " " + detail_text).lower() for k in kws)],
                "source": "sginnovate-owning-page", "kind": "sginnovate",
                "first_seen": NOW.date().isoformat(), "last_seen": NOW.date().isoformat(),
            })
        except Exception as error:
            print("  WARN SGInnovate individual event failed " + path + ": " + type(error).__name__, file=sys.stderr)
            continue
    return out


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def event_url_key(url):
    """Compare canonical event identities, including Luma's two public domains."""
    parts = urllib.parse.urlsplit(url or "")
    host = (parts.hostname or "").lower()
    if host in ("lu.ma", "www.lu.ma", "luma.com", "www.luma.com"):
        host = "luma.com"
    if host == "www.sginnovate.com":
        host = "sginnovate.com"
    return host + parts.path.rstrip("/").lower()


def merge_curated_events(kept, manual_events, old_events, today):
    """Keep live scheduling/location, stable IDs and independently checked annotations.

    Curated source dates describe the annotation check, not a new live verification.
    Manual-only events remain available, with their original provenance intact.
    A title prefix is never sufficient to merge two events.
    """
    display_fields = ("note", "fee", "fee_label", "credits", "credits_kind",
                      "curated_location_note", "annotation_checked_at", "annotation_sources")
    old_by_url = {event_url_key(e.get("url")): e for e in old_events.values()}
    for raw in manual_events:
        m = dict(raw)
        key = event_url_key(m.get("url"))
        matched_id = next((eid for eid, e in kept.items()
                           if key and event_url_key(e.get("url")) == key), None)
        if matched_id is not None:
            live = dict(kept.pop(matched_id))
            previous = old_by_url.get(key) or old_events.get(m.get("id"))
            stable_id = (previous or {}).get("id") or live["id"]
            live["id"] = stable_id
            for field in display_fields:
                if field in m:
                    live[field] = m[field]
            live["first_seen"] = (previous or {}).get("first_seen") or m.get("first_seen") or today
            live["source"] = live.get("source", "live") + "+curated-annotations"
            kept[stable_id] = live
            continue
        m.setdefault("kind", "manual")
        m.setdefault("vendors", [])
        m.setdefault("hosts", [])
        m.setdefault("virtual", False)
        m.setdefault("sg", True)
        previous = old_events.get(m["id"]) or old_by_url.get(key) or {}
        m["id"] = previous.get("id") or m["id"]
        m["first_seen"] = previous.get("first_seen") or m.get("first_seen") or today
        # Do not relabel old manually curated content as checked today.
        m.setdefault("last_seen", previous.get("last_seen"))
        kept[m["id"]] = m
    return kept


def main():
    DATA.mkdir(exist_ok=True)
    old_events = {e["id"]: e for e in load_json(DATA / "events.json", [])}
    prior_urls = {(e.get("url") or "").rstrip("/").lower() for e in old_events.values()}
    discovered = load_json(DATA / "calendars.json", {})  # api_id -> {name, trusted}
    today = NOW.date().isoformat()

    kept, new_cals = {}, {}

    def ingest(entries, source):
        for x in entries:
            n = norm(x, source)
            cid = n["calendar_id"]
            if not n["id"] or not n["url"] or not n["start"]:
                continue
            trusted = cid in TRUSTED_CALENDARS or (discovered.get(cid) or {}).get("trusted", False)
            if not (n["sg"] or n["virtual"]):
                continue
            if not trusted and not any(k in n["_hay"] for k in AI_KW):
                continue
            # auto-discover calendars that host AI events in Singapore
            if cid and cid not in TRUSTED_CALENDARS and cid not in discovered and n["sg"]:
                new_cals[cid] = {"name": n["calendar"], "trusted": False}
            n.pop("_hay", None)
            if n["id"] in kept:
                kept[n["id"]]["source"] += "+" + source
                continue
            prev = old_events.get(n["id"])
            n["first_seen"] = (prev or {}).get("first_seen", today)
            n["last_seen"] = today
            kept[n["id"]] = n

    # 1) Singapore discover feed
    ingest(paged(f"https://api.lu.ma/discover/get-paginated-events?discover_place_api_id={SG_PLACE}"),
           "luma-sg-feed")
    # Luma AI and Tech categories ranked around Singapore add a broader feed
    # beyond the curated Singapore discover stream. Categories are noisy, so
    # the same AI relevance filter and strict event location/date checks apply.
    for category in ("cat-ai", "cat-tech"):
        cat_url = ("https://api.luma.com/discover/get-paginated-events?"
                   f"discover_category_api_id={category}&discover_place_api_id={SG_PLACE}")
        ingest(paged(cat_url), f"luma-category:{category}")
    # 2) trusted calendars
    for cid, name in TRUSTED_CALENDARS.items():
        ingest(paged(f"https://api.lu.ma/calendar/get-items?calendar_api_id={cid}&period=future"),
               f"cal:{name}")
    # 3) watch + previously discovered calendars
    for cid in WATCH_CALENDARS + [c for c in discovered if c not in TRUSTED_CALENDARS]:
        ingest(paged(f"https://api.lu.ma/calendar/get-items?calendar_api_id={cid}&period=future"),
               f"cal:{cid}")

    # 4) independent Meetup and SGInnovate sources supplement discovery.
    meetup_added = {}
    known_urls = {(e.get("url") or "").rstrip("/").lower() for e in old_events.values()}
    known_urls.update((e.get("url") or "").rstrip("/").lower() for e in kept.values())
    for slug, group_name in MEETUP_GROUPS.items():
        entries = meetup_events(slug, group_name)
        added = 0
        for n in entries:
            u = (n.get("url") or "").rstrip("/").lower()
            if not u or u in known_urls:
                continue
            known_urls.add(u)
            kept[n["id"]] = n
            added += 1
        meetup_added[slug] = added
        print(f"  Meetup {slug}: {added} new qualifying events ({len(entries)} candidates)")
        time.sleep(0.2)

    sginnovate = sginnovate_events()
    sgi_added = 0
    for n in sginnovate:
        u = (n.get("url") or "").rstrip("/").lower()
        if u and u not in known_urls:
            known_urls.add(u); kept[n["id"]] = n; sgi_added += 1
    print(f"  SGInnovate: {sgi_added} new qualifying events ({len(sginnovate)} candidates)")

    # 5) merge with archive: revalidate omitted Luma events from the live source.
    # Stale cached timestamps/location must not keep expired or misclassified entries.
    for eid, prev in old_events.items():
        if eid in kept:
            continue
        if prev.get("kind") == "luma":
            slug = (prev.get("url") or "").rstrip("/").rsplit("/",1)[-1]
            live = luma_event_details(eid, slug)
            if live and live.get("__deleted"):
                continue
            if live:
                cid = live.get("calendar_id")
                trusted = cid in TRUSTED_CALENDARS or (discovered.get(cid) or {}).get("trusted", False)
                hay = (live.get("name","")+" "+" ".join(live.get("hosts",[]))+" "+live.get("calendar","")).lower()
                if (live.get("sg") or live.get("virtual")) and (trusted or any(k in hay for k in AI_KW)):
                    live["first_seen"] = prev.get("first_seen", today)
                    live["last_seen"] = today
                    kept[eid] = live
                continue
            if not live:
                try:
                    cached_end = datetime.fromisoformat((prev.get("end") or prev.get("start")).replace("Z", "+00:00"))
                    if cached_end < NOW:
                        print(f"  WARN dropping stale expired Luma event without live verification: {slug}", file=sys.stderr)
                        continue
                except Exception:
                    pass
                print(f"  WARN could not revalidate archived Luma event {eid}; retaining cached record", file=sys.stderr)
        kept[eid] = prev

    # 4a) drop mirrored Luma duplicates: same normalized title and exact start.
    #     Some hosts publish the same event under two slugs/calendars.
    import re as _re
    def _event_sig(e):
        name = _re.sub(r"\s*\([^)]*\)\s*$", "", e.get("name") or "")
        name = _re.sub(r"[^a-z0-9]", "", name.lower())
        try:
            start_key = datetime.fromisoformat((e.get("start") or "").replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            start_key = e.get("start") or ""
        return (name, start_key)
    seen_sigs = {}
    for eid in list(kept):
        sig = _event_sig(kept[eid])
        if sig in seen_sigs:
            # Prefer the older tracked record to keep first_seen stable.
            prev_id = seen_sigs[sig]
            a, b = kept[prev_id], kept[eid]
            if (prev_id in old_events) != (eid in old_events):
                keep_id, drop_id = (prev_id, eid) if prev_id in old_events else (eid, prev_id)
            else:
                keep_id, drop_id = (prev_id, eid) if a.get("first_seen", today) <= b.get("first_seen", today) else (eid, prev_id)
            seen_sigs[sig] = keep_id
            del kept[drop_id]
        else:
            seen_sigs[sig] = eid

    # Curated annotations overlay an exact owning URL match. Live dates and
    # location always win; near-title matches must not delete distinct events.
    merge_curated_events(kept, load_json(DATA / "manual-events.json", []), old_events, today)

    # 5b) credits overrides: verified credit offers per event URL (data/credits.json)
    credits_map = load_json(DATA / "credits.json", {})
    for e in kept.values():
        u = (e.get("url") or "").rstrip("/").lower()
        for k, v in credits_map.items():
            if u == k.rstrip("/").lower() or u.endswith("/" + k.rstrip("/").lower()):
                if isinstance(v, dict):
                    e["credits"] = v.get("text", "")
                    if v.get("kind"):
                        e["credits_kind"] = v["kind"]
                else:
                    e["credits"] = v

    # 5c) curated exclusions (event URLs or calendar ids): non-AI items pulled in by broad feeds
    excluded = {event_url_key(u) for u in load_json(DATA / "excluded-urls.json", [])}

    # 6) prune events whose end time has passed; never show expired events
    final = []
    pruned = 0
    for e in kept.values():
        if event_url_key(e.get("url")) in excluded or \
                event_url_key(e.get("calendar_id") or "") in excluded:
            continue
        end = e.get("end") or e.get("start")
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except Exception:
            end_dt = NOW + timedelta(days=1)
        if end_dt < PRUNE_BEFORE:
            pruned += 1
            continue
        final.append(e)
    final.sort(key=lambda e: e["start"])

    (DATA / "events.json").write_text(json.dumps(final, indent=1, ensure_ascii=False))
    discovered.update(new_cals)
    (DATA / "calendars.json").write_text(json.dumps(discovered, indent=1, ensure_ascii=False))
    meta = {"refreshed_at": NOW.isoformat(timespec="seconds"), "event_count": len(final),
            "sg_count": sum(1 for e in final if e.get("sg") and not e.get("virtual")),
            "virtual_count": sum(1 for e in final if e.get("virtual")),
            "new_today": sum(1 for e in final if e.get("first_seen") == today)}
    (DATA / "meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))
    print(f"pruned {pruned} passed events; watching {len(discovered)} discovered calendars; +{len(new_cals)} new calendars")
    final_source_counts = {}
    for event in final:
        event_url = (event.get("url") or "").rstrip("/").lower()
        if event_url in prior_urls:
            continue
        src = event.get("source") or "unknown"
        if src.startswith("meetup:"):
            final_source_counts[src] = final_source_counts.get(src, 0) + 1
        elif src == "sginnovate":
            final_source_counts[src] = final_source_counts.get(src, 0) + 1
    print("Net new events after dedupe: " + json.dumps(final_source_counts, sort_keys=True))
    register_watch = [e for e in final if e.get("first_seen") == today and
                      any(k in (e.get("name","")+" "+" ".join(e.get("hosts",[]))).lower()
                          for k in ("anthropic","claude","openai","codex"))]
    print("Registration watch (new Claude/OpenAI events): " + json.dumps(
        [{k:e.get(k) for k in ("name","url","start","virtual","source")} for e in register_watch], ensure_ascii=False))


if __name__ == "__main__":
    main()
