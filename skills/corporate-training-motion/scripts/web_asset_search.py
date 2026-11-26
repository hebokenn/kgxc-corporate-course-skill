#!/usr/bin/env python3
"""Search and stage open-license online visual assets (Wikimedia Commons / Openverse) for course rendering.

Usage:
  python3 web_asset_search.py search "minimalist store counter" --limit 6
  python3 web_asset_search.py fetch <image_url> --out <course>/project/assets/web/counter.png --license "CC0" --source-url <page_url>
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = "KGXC-Course-Asset-Fetcher/1.0 (https://github.com/hebokenn/kgxc-corporate-course-skill)"


def _http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def search_wikimedia(query: str, limit: int = 6):
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": f"{query} filetype:bitmap|drawing",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1280",
    })
    raw = json.loads(_http_get(f"https://commons.wikimedia.org/w/api.php?{params}").decode("utf-8"))
    pages = (raw.get("query") or {}).get("pages") or {}
    results = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value", "unknown")
        artist = (meta.get("Artist") or {}).get("value", "")
        results.append({
            "provider": "wikimedia",
            "title": page.get("title", ""),
            "url": info.get("thumburl") or info.get("url", ""),
            "original_url": info.get("url", ""),
            "source_url": info.get("descriptionurl", ""),
            "mime": info.get("mime", ""),
            "width": info.get("width", 0),
            "height": info.get("height", 0),
            "license": lic,
            "attribution": artist[:160],
        })
    return results


def search_openverse(query: str, limit: int = 6):
    params = urllib.parse.urlencode({
        "q": query,
        "page_size": str(limit),
        "license_type": "commercial,modification",
    })
    raw = json.loads(_http_get(f"https://api.openverse.org/v1/images/?{params}").decode("utf-8"))
    results = []
    for item in raw.get("results") or []:
        results.append({
            "provider": "openverse",
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "original_url": item.get("url", ""),
            "source_url": item.get("foreign_landing_url", ""),
            "mime": f"image/{item.get('filetype', 'jpeg')}",
            "width": item.get("width", 0),
            "height": item.get("height", 0),
            "license": f"{item.get('license', '')} {item.get('license_version', '')}".strip().upper(),
            "attribution": item.get("creator", "")[:160],
        })
    return results


def cmd_search(args):
    items = []
    errors = []
    if args.source in ("all", "openverse"):
        try:
            items.extend(search_openverse(args.query, args.limit))
        except Exception as exc:
            errors.append({"provider": "openverse", "error": str(exc)})
    if args.source in ("all", "wikimedia"):
        try:
            items.extend(search_wikimedia(args.query, args.limit))
        except Exception as exc:
            errors.append({"provider": "wikimedia", "error": str(exc)})
    print(json.dumps({"query": args.query, "count": len(items), "results": items[: args.limit * 2], "errors": errors}, ensure_ascii=False, indent=2))


def cmd_fetch(args):
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = _http_get(args.url, timeout=25)
    out_path.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()

    manifest_path = out_path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {"assets": []}
    entry = {
        "file": out_path.name,
        "path": str(out_path),
        "bytes": len(data),
        "sha256": sha,
        "url": args.url,
        "source_url": args.source_url or "",
        "license": args.license or "unspecified",
        "attribution": args.attribution or "",
        "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    manifest["assets"] = [a for a in manifest.get("assets", []) if a.get("file") != out_path.name]
    manifest["assets"].append(entry)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "asset": entry, "manifest": str(manifest_path)}, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Search & stage open-license online course assets")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("search", help="Search open-license images/SVGs")
    ps.add_argument("query", help="Search keywords")
    ps.add_argument("--source", choices=["all", "wikimedia", "openverse"], default="all")
    ps.add_argument("--limit", type=int, default=6)
    ps.set_defaults(func=cmd_search)

    pf = sub.add_parser("fetch", help="Download a chosen asset into course project/assets/web/")
    pf.add_argument("url", help="Direct image/SVG URL")
    pf.add_argument("--out", required=True, help="Output file path")
    pf.add_argument("--source-url", default="", help="Original landing/attribution page URL")
    pf.add_argument("--license", default="CC0/Open", help="License label")
    pf.add_argument("--attribution", default="", help="Creator / attribution text")
    pf.set_defaults(func=cmd_fetch)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
