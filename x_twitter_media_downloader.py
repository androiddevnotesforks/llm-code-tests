#!/usr/bin/env python3
"""
Download GIF/Video media from an X/Twitter post URL using the public
syndication endpoint. No API keys required.

Usage:
  python x_twitter_media_downloader.py <tweet_url> [-o OUTPUT] [--all] [--include-m3u8] [--force]

Examples:
  python x_twitter_media_downloader.py https://x.com/user/status/1234567890
  python x_twitter_media_downloader.py https://twitter.com/user/status/1234567890 -o media.mp4
  python x_twitter_media_downloader.py https://x.com/user/status/1234567890 --all

Notes:
  - This script targets the public "cdn.syndication.twimg.com" tweet JSON, which is commonly
    accessible without authentication. Availability may change; in that case you may need to
    provide cookies or use an alternative approach.
  - For GIFs on X/Twitter, the downloadable format is typically MP4. Converting to .gif is not
    performed by this script.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen


SYNDICATION_URLS = [
    "https://cdn.syndication.twimg.com/widgets/tweet?id={tweet_id}",
    "https://cdn.syndication.twimg.com/widgets/tweet?id={tweet_id}&lang=en",
    "https://cdn.syndication.twimg.com/widgets/tweet?dnt=false&id={tweet_id}&lang=en",
]
FXTWITTER_API = "https://api.fxtwitter.com/status/{tweet_id}"
VXTWITTER_API = "https://api.vxtwitter.com/status/{tweet_id}"


class DownloadError(Exception):
    pass


def extract_tweet_id(tweet_url: str) -> str:
    """Extracts the tweet ID from common Twitter/X URL formats.

    Supported patterns include:
    - https://x.com/<user>/status/<id>
    - https://twitter.com/<user>/status/<id>
    - https://mobile.twitter.com/<user>/status/<id>
    - https://x.com/i/web/status/<id>
    """
    try:
        parsed = urlparse(tweet_url)
    except Exception as e:
        raise ValueError(f"Invalid URL: {tweet_url}: {e}")

    # Path examples:
    # /<user>/status/<id>
    # /i/web/status/<id>
    # /status/<id>  (rare)
    path_parts = [p for p in parsed.path.split('/') if p]
    tweet_id: Optional[str] = None

    # Look for the segment 'status' and take the next segment as ID
    for i, part in enumerate(path_parts):
        if part.lower() == 'status' and i + 1 < len(path_parts):
            tweet_id = path_parts[i + 1]
            break

    # Fallback for /i/web/status/<id>
    if tweet_id is None:
        for i in range(len(path_parts) - 1):
            if path_parts[i].lower() == 'status':
                tweet_id = path_parts[i + 1]
                break

    if not tweet_id:
        # Sometimes ID may be in query, unlikely but handle graciously
        q = parse_qs(parsed.query)
        if 'id' in q and q['id']:
            tweet_id = q['id'][0]

    if not tweet_id:
        raise ValueError("Could not extract tweet ID from URL. Expected .../status/<id>.")

    # Strip extra params if any (defensive)
    tweet_id = re.split(r'[?#]', tweet_id)[0]
    if not tweet_id.isdigit():
        raise ValueError(f"Extracted tweet ID looks invalid: {tweet_id}")
    return tweet_id


def http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    """Fetch JSON from a URL with browser-like headers."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://publish.twitter.com/",
        "Origin": "https://publish.twitter.com",
        "Connection": "keep-alive",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or 'utf-8'
            body = resp.read().decode(charset, errors='replace')
    except Exception as e:
        raise DownloadError(f"HTTP error fetching JSON: {e}")

    try:
        return json.loads(body)
    except Exception as e:
        # Provide a hint if we got HTML instead (blocked / changed)
        snippet = body[:200].replace('\n', ' ')
        raise DownloadError(
            f"Failed to parse JSON. First bytes: {snippet!r}. Error: {e}"
        )


def try_fetch_syndication_json(tweet_id: str) -> Optional[Dict[str, Any]]:
    for url_tpl in SYNDICATION_URLS:
        url = url_tpl.format(tweet_id=tweet_id)
        try:
            return http_get_json(url)
        except DownloadError as e:
            # 404/blocked/etc — try next
            continue
    return None


def try_fetch_third_party_json(tweet_id: str) -> Optional[Dict[str, Any]]:
    # Try FXTwitter first
    for url_tpl in (FXTWITTER_API, VXTWITTER_API):
        url = url_tpl.format(tweet_id=tweet_id)
        try:
            data = http_get_json(url)
        except DownloadError:
            continue
        # FX/VX Twitter wrap under { tweet: {...} }
        if isinstance(data, dict) and 'tweet' in data and isinstance(data['tweet'], dict):
            return data['tweet']
        # Some variants may return top-level compatible structure
        return data
    return None


def gather_variants(obj: Any) -> List[Dict[str, Any]]:
    """Recursively search for video 'variants' within the JSON object.

    Returns a list of variant dicts, each expected to contain at least a 'src' or 'url' field.
    """
    variants: List[Dict[str, Any]] = []

    def _walk(node: Any):
        if isinstance(node, dict):
            # Direct match: { variants: [ ... ] }
            v = node.get('variants')
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and ('src' in item or 'url' in item):
                        variants.append(item)
            # Continue walking
            for k, v2 in node.items():
                _walk(v2)
        elif isinstance(node, list):
            for it in node:
                _walk(it)

    _walk(obj)

    # Deduplicate by src/url
    seen = set()
    unique: List[Dict[str, Any]] = []
    for v in variants:
        src = v.get('src') or v.get('url')
        if not src or src in seen:
            continue
        seen.add(src)
        unique.append(v)
    return unique


def filter_variants(
    variants: List[Dict[str, Any]],
    include_m3u8: bool = False,
) -> List[Dict[str, Any]]:
    """Filter variants to preferred media types (mp4 by default)."""
    filtered: List[Dict[str, Any]] = []
    for v in variants:
        src = v.get('src') or v.get('url')
        if not src:
            continue
        vtype = (v.get('type') or v.get('content_type') or '').lower()
        if 'mp4' in vtype or (include_m3u8 and 'mpegurl' in vtype):
            filtered.append(v)
        else:
            # Sometimes 'type' is absent. Try to infer from URL.
            if src.endswith('.mp4'):
                filtered.append(v)
            elif include_m3u8 and ('.m3u8' in src or 'mpegurl' in src):
                filtered.append(v)
    return filtered


def pick_best_variant(variants: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the best quality variant based on bitrate if available, else last."""
    if not variants:
        return None
    # Prefer highest bitrate if present
    sortable: List[Tuple[int, Dict[str, Any]]] = []
    for v in variants:
        br = v.get('bitrate') or v.get('bit_rate') or 0
        try:
            br = int(br)
        except Exception:
            br = 0
        sortable.append((br, v))
    sortable.sort(key=lambda x: x[0])
    return sortable[-1][1]


def format_size(num_bytes: Optional[int]) -> str:
    if not num_bytes or num_bytes < 0:
        return "unknown"
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def stream_download(url: str, dest: Path, overwrite: bool = False) -> None:
    if dest.exists() and not overwrite:
        raise DownloadError(f"Destination file exists: {dest} (use --force to overwrite)")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Referer": "https://publish.twitter.com/",
        "Origin": "https://publish.twitter.com",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=60) as resp:
            total = resp.headers.get('Content-Length')
            total_i = int(total) if total and total.isdigit() else None
            chunk = 1024 * 256
            tmp = dest.with_suffix(dest.suffix + ".part")
            downloaded = 0
            start = time.time()
            with open(tmp, 'wb') as f:
                while True:
                    buf = resp.read(chunk)
                    if not buf:
                        break
                    f.write(buf)
                    downloaded += len(buf)
                    # Simple inline progress
                    if total_i:
                        pct = downloaded / total_i * 100
                        sys.stderr.write(
                            f"\rDownloading {dest.name}: {pct:5.1f}% ({format_size(downloaded)}/{format_size(total_i)})"
                        )
                        sys.stderr.flush()
            tmp.replace(dest)
            if total_i:
                sys.stderr.write("\n")
    except Exception as e:
        raise DownloadError(f"Error downloading media: {e}")


@dataclass
class DownloadPlan:
    tweet_id: str
    output: Optional[Path]
    download_all: bool
    include_m3u8: bool
    force: bool


def resolve_output_path(base_output: Optional[Path], tweet_id: str, variant: Dict[str, Any], index: int = 0) -> Path:
    # Determine filename
    src = variant.get('src') or variant.get('url') or ''
    # Strip query/fragment for extension inference
    try:
        parsed = urlparse(src)
        clean_path = parsed.path or src
    except Exception:
        clean_path = src

    ext = '.mp4'
    if clean_path.endswith('.m3u8'):
        ext = '.m3u8'
    else:
        suf = Path(clean_path).suffix
        if suf:
            ext = suf

    bitrate = variant.get('bitrate') or variant.get('bit_rate')
    quality_tag = f"_{bitrate}kbps" if bitrate else (f"_{index}" if index else "")

    if base_output is None:
        return Path(f"{tweet_id}{quality_tag}{ext}")

    if base_output.exists() and base_output.is_dir():
        return base_output / f"{tweet_id}{quality_tag}{ext}"

    # If provided output looks like a file (has suffix), respect it for single download
    if base_output.suffix:
        return base_output

    # Otherwise treat as a directory path even if it doesn't exist yet
    return base_output / f"{tweet_id}{quality_tag}{ext}"


def download_from_tweet_url(plan: DownloadPlan) -> List[Path]:
    # Try public syndication first
    data = try_fetch_syndication_json(plan.tweet_id)
    if data is None:
        # Fall back to third-party helper APIs that expose media variants
        data = try_fetch_third_party_json(plan.tweet_id)
    if data is None:
        raise DownloadError("Could not fetch tweet metadata from public endpoints.")

    # Quick sanity: check if we even have a video
    # The syndication JSON may include keys like 'video' or a nested object with 'variants'
    variants = gather_variants(data)
    variants = filter_variants(variants, include_m3u8=plan.include_m3u8)

    if not variants:
        # Provide a more helpful hint if this looks like a photo-only tweet
        if data.get('photos'):
            raise DownloadError("No video found; the tweet appears to contain only photos.")
        raise DownloadError("No downloadable media variants found in the tweet JSON.")

    targets: List[Dict[str, Any]]
    if plan.download_all:
        # Keep order, but group by bitrate ascending
        with_bitrate = []
        for v in variants:
            br = v.get('bitrate') or v.get('bit_rate') or 0
            try:
                br = int(br)
            except Exception:
                br = 0
            with_bitrate.append((br, v))
        with_bitrate.sort(key=lambda x: x[0])
        targets = [v for _, v in with_bitrate]
    else:
        best = pick_best_variant(variants)
        if not best:
            raise DownloadError("Could not pick a media variant to download.")
        targets = [best]

    outputs: List[Path] = []
    for idx, v in enumerate(targets):
        src = v.get('src') or v.get('url')
        if not src:
            continue
        out_path = resolve_output_path(plan.output, plan.tweet_id, v, index=idx)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        stream_download(src, out_path, overwrite=plan.force)
        outputs.append(out_path)
    return outputs


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download GIF/Video from an X/Twitter post URL (no API key).")
    p.add_argument("url", help="Tweet URL, e.g., https://x.com/<user>/status/<id>")
    p.add_argument("-o", "--output", help="Output file or directory. Defaults to '<id>.mp4'.", default=None)
    p.add_argument("--all", dest="download_all", action="store_true", help="Download all available mp4 variants (by bitrate).")
    p.add_argument("--include-m3u8", action="store_true", help="Include HLS .m3u8 variants in selection.")
    p.add_argument("--force", action="store_true", help="Overwrite existing files.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        tweet_id = extract_tweet_id(args.url)
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2

    output_path = Path(args.output).expanduser() if args.output else None
    plan = DownloadPlan(
        tweet_id=tweet_id,
        output=output_path,
        download_all=args.download_all,
        include_m3u8=args.include_m3u8,
        force=args.force,
    )

    try:
        outputs = download_from_tweet_url(plan)
    except DownloadError as e:
        sys.stderr.write(f"Download failed: {e}\n")
        return 1

    for p in outputs:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
