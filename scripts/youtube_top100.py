#!/usr/bin/env python3
"""
Top 100 vídeos do YouTube sobre a Madeira — via YouTube Data API v3 (oficial).

Uso:
    export YOUTUBE_API_KEY="a-tua-chave"   # Google Cloud Console → YouTube Data API v3
    python scripts/youtube_top100.py

Escreve content/madeiradaily/data/youtube-top100.md (tabela ordenada por views
exatas) e youtube-top100.csv. Custo de quota: ~1.300 unidades (limite diário
gratuito: 10.000).
"""

import csv
import os
import sys
from datetime import date

import requests

API = "https://www.googleapis.com/youtube/v3"
KEY = os.environ.get("YOUTUBE_API_KEY", "")

QUERIES = [
    "madeira island",
    "madeira 4k drone",
    "madeira travel guide",
    "madeira things to do",
    "madeira hiking levada",
    "madeira airport landing",
    "funchal madeira",
    "pico do arieiro",
    "madeira before you go tips",
    "madeira itinerary",
    "madeira cost budget",
    "living in madeira",
]

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "content", "madeiradaily", "data")


def search_ids(query):
    """IDs dos ~50 vídeos mais vistos para uma query."""
    resp = requests.get(
        f"{API}/search",
        params={
            "key": KEY,
            "q": query,
            "part": "id",
            "type": "video",
            "order": "viewCount",
            "maxResults": 50,
            "relevanceLanguage": "en",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return [item["id"]["videoId"] for item in resp.json().get("items", [])]


def video_details(ids):
    """Estatísticas exatas (views, likes) + título/canal/data por lote de 50."""
    out = []
    for i in range(0, len(ids), 50):
        resp = requests.get(
            f"{API}/videos",
            params={
                "key": KEY,
                "id": ",".join(ids[i : i + 50]),
                "part": "snippet,statistics,contentDetails",
            },
            timeout=30,
        )
        resp.raise_for_status()
        for item in resp.json().get("items", []):
            stats = item.get("statistics", {})
            snip = item.get("snippet", {})
            out.append(
                {
                    "id": item["id"],
                    "titulo": snip.get("title", ""),
                    "canal": snip.get("channelTitle", ""),
                    "data": (snip.get("publishedAt") or "")[:10],
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)) if "likeCount" in stats else None,
                    "duracao": item.get("contentDetails", {}).get("duration", ""),
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                }
            )
    return out


def main():
    if not KEY:
        sys.exit("Define YOUTUBE_API_KEY (Google Cloud Console → YouTube Data API v3).")

    seen, all_ids = set(), []
    for q in QUERIES:
        for vid in search_ids(q):
            if vid not in seen:
                seen.add(vid)
                all_ids.append(vid)
        print(f"  pesquisa '{q}': acumulados {len(all_ids)} vídeos únicos")

    videos = sorted(video_details(all_ids), key=lambda v: v["views"], reverse=True)[:100]

    os.makedirs(OUT_DIR, exist_ok=True)
    hoje = date.today().isoformat()

    csv_path = os.path.join(OUT_DIR, "youtube-top100.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(videos[0].keys()))
        writer.writeheader()
        writer.writerows(videos)

    md_path = os.path.join(OUT_DIR, "youtube-top100.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Top 100 YouTube — Madeira (views exatas, API oficial)\n\n")
        fh.write(f"**Snapshot: {hoje}** · Fonte: YouTube Data API v3 · ")
        fh.write(f"Queries: {', '.join(QUERIES)}\n\n")
        fh.write("| # | Título | Canal | Views | Data | Link |\n|---|---|---|---|---|---|\n")
        for i, v in enumerate(videos, 1):
            titulo = v["titulo"].replace("|", "/")[:80]
            fh.write(
                f"| {i} | {titulo} | {v['canal']} | {v['views']:,} | {v['data']} | [▶]({v['url']}) |\n"
            )

    print(f"\nOK: {len(videos)} vídeos → {md_path} e {csv_path}")


if __name__ == "__main__":
    main()
