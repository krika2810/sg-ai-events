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

Archive mode: events are NEVER removed until their date has passed
(end time older than 12 hours). Nothing else ever drops off.

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
PRUNE_BEFORE = NOW - timedelta(hours=12)

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
}


def get(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=30))
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
    is_virtual = loc_type not in (None, "offline")
    is_sg = (g.get("country_code") == "SG") or (
        ev.get("timezone") == "Asia/Singapore" and not is_virtual)
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
        "venue": (g.get("full_address") or g.get("address") or ("Online" if is_virtual else "")),
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


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def main():
    DATA.mkdir(exist_ok=True)
    old_events = {e["id"]: e for e in load_json(DATA / "events.json", [])}
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
    # 2) trusted calendars
    for cid, name in TRUSTED_CALENDARS.items():
        ingest(paged(f"https://api.lu.ma/calendar/get-items?calendar_api_id={cid}&period=future"),
               f"cal:{name}")
    # 3) watch + previously discovered calendars
    for cid in WATCH_CALENDARS + [c for c in discovered if c not in TRUSTED_CALENDARS]:
        ingest(paged(f"https://api.lu.ma/calendar/get-items?calendar_api_id={cid}&period=future"),
               f"cal:{cid}")

    # 4) merge with archive: previous events not seen today stay unless passed
    for eid, prev in old_events.items():
        if eid not in kept:
            kept[eid] = prev

    # 4a) drop mirrored Luma duplicates: same normalized title and exact start.
    #     Some hosts publish the same event under two slugs/calendars.
    import re as _re
    def _event_sig(e):
        name = _re.sub(r"\s*\([^)]*\)\s*$", "", e.get("name") or "")
        name = _re.sub(r"[^a-z0-9]", "", name.lower())
        return (name, e.get("start") or "")
    seen_sigs = {}
    for eid in list(kept):
        sig = _event_sig(kept[eid])
        if sig in seen_sigs:
            # Prefer the older tracked record to keep first_seen stable.
            prev_id = seen_sigs[sig]
            a, b = kept[prev_id], kept[eid]
            keep_id, drop_id = (prev_id, eid) if a.get("first_seen", today) <= b.get("first_seen", today) else (eid, prev_id)
            seen_sigs[sig] = keep_id
            del kept[drop_id]
        else:
            seen_sigs[sig] = eid

    # 4b) drop harvested events that duplicate a manual curated entry
    #     (same start date + same name prefix, e.g. official non-Luma page)
    def _sig(name):
        return _re.sub(r"[^a-z0-9]", "", (name or "").lower())[:12]
    man_sigs = {(_sig(m.get("name")), (m.get("start") or "")[:10])
                for m in load_json(DATA / "manual-events.json", [])}
    for eid in [eid for eid, e in kept.items()
                if (_sig(e.get("name")), (e.get("start") or "")[:10]) in man_sigs]:
        del kept[eid]

    # 5) manual curated entries (never overwritten); skip if the same URL
    #    was already harvested from Luma (avoid duplicates)
    kept_urls = {(e.get("url") or "").rstrip("/").lower() for e in kept.values()}
    for m in load_json(DATA / "manual-events.json", []):
        m = dict(m)
        m.setdefault("kind", "manual")
        m.setdefault("vendors", [])
        m.setdefault("hosts", [])
        m.setdefault("virtual", False)
        m.setdefault("sg", True)
        if (m.get("url") or "").rstrip("/").lower() in kept_urls:
            continue
        prev = old_events.get(m["id"])
        m["first_seen"] = (prev or {}).get("first_seen", today)
        m["last_seen"] = today
        kept[m["id"]] = m

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
    excluded = {u.rstrip("/").lower() for u in load_json(DATA / "excluded-urls.json", [])}

    # 6) prune only events whose date has passed
    final = []
    pruned = 0
    for e in kept.values():
        if (e.get("url") or "").rstrip("/").lower() in excluded or \
                (e.get("calendar_id") or "").lower() in excluded:
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


if __name__ == "__main__":
    main()
