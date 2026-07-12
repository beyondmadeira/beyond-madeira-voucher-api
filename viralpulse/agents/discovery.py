"""
DiscoveryAgent — descoberta de conteúdo viral por vias OFICIAIS.

NÃO faz scraping do Explore nem usa proxies/stealth. Usa:
  - Instagram Graph API → Hashtag Search + top_media (conta de negócio).
  - TikTok Research API  → query de vídeos por hashtag.

Em DRY_RUN devolve exemplos, para o pipeline correr sem credenciais.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from ..core.models import Platform
from .base import BaseAgent

GRAPH_API = "https://graph.facebook.com/v20.0"
TIKTOK_RESEARCH_API = "https://open.tiktokapis.com/v2/research/video/query/"


@dataclass
class DiscoveredItem:
    platform: Platform
    external_id: str
    permalink: str
    creator: str
    caption: str
    media_url: str
    like_count: int
    comment_count: int

    @property
    def virality_score(self) -> float:
        """Score simples: engagement ponderado. Comentários pesam mais que likes."""
        return self.like_count + self.comment_count * 3.0


class DiscoveryAgent(BaseAgent):
    name = "discovery"

    def discover(self) -> list[DiscoveredItem]:
        cfg = self.config.get("discovery", {})
        limit = cfg.get("max_candidates_per_cycle", 10)
        items: list[DiscoveredItem] = []

        if self.dry_run:
            self.log.info("dry_run.discovery", note="a usar dados de exemplo")
            return self._sample_items()[:limit]

        if cfg.get("instagram", {}).get("enabled"):
            for tag in cfg["instagram"].get("hashtags", []):
                items += self._instagram_hashtag(tag, cfg["instagram"].get("min_engagement", 0))

        if cfg.get("tiktok", {}).get("enabled"):
            for tag in cfg["tiktok"].get("hashtags", []):
                items += self._tiktok_hashtag(tag, cfg["tiktok"].get("min_engagement", 0))

        # Ordena por viralidade e corta ao limite do ciclo.
        items.sort(key=lambda i: i.virality_score, reverse=True)
        return items[:limit]

    # ── Instagram Graph API ────────────────────────────────────────────
    def _instagram_hashtag(self, hashtag: str, min_engagement: int) -> list[DiscoveredItem]:
        token = self.settings.ig_access_token
        ig_user = self.settings.ig_business_account_id
        if not token or not ig_user:
            self.log.warning("instagram.skip", reason="faltam IG_ACCESS_TOKEN/IG_BUSINESS_ACCOUNT_ID")
            return []
        try:
            # 1) hashtag → id
            r = requests.get(
                f"{GRAPH_API}/ig_hashtag_search",
                params={"user_id": ig_user, "q": hashtag, "access_token": token},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json().get("data", [])
            if not data:
                return []
            hashtag_id = data[0]["id"]

            # 2) top_media da hashtag
            fields = "id,caption,media_type,media_url,permalink,like_count,comments_count,username"
            r = requests.get(
                f"{GRAPH_API}/{hashtag_id}/top_media",
                params={"user_id": ig_user, "fields": fields, "access_token": token},
                timeout=30,
            )
            r.raise_for_status()
            out = []
            for m in r.json().get("data", []):
                likes = m.get("like_count", 0)
                comments = m.get("comments_count", 0)
                if likes + comments < min_engagement:
                    continue
                out.append(
                    DiscoveredItem(
                        platform=Platform.INSTAGRAM,
                        external_id=str(m["id"]),
                        permalink=m.get("permalink", ""),
                        creator=m.get("username", ""),
                        caption=m.get("caption", ""),
                        media_url=m.get("media_url", ""),
                        like_count=likes,
                        comment_count=comments,
                    )
                )
            return out
        except requests.RequestException as exc:
            self.log.error("instagram.error", hashtag=hashtag, error=str(exc))
            return []

    # ── TikTok Research API ────────────────────────────────────────────
    def _tiktok_hashtag(self, hashtag: str, min_engagement: int) -> list[DiscoveredItem]:
        token = self.settings.tiktok_access_token
        if not token:
            self.log.warning("tiktok.skip", reason="falta TIKTOK_ACCESS_TOKEN")
            return []
        try:
            body = {
                "query": {
                    "and": [
                        {"operation": "IN", "field_name": "hashtag_name", "field_values": [hashtag]}
                    ]
                },
                "max_count": 20,
            }
            fields = "id,video_description,like_count,comment_count,username,share_url"
            r = requests.post(
                TIKTOK_RESEARCH_API,
                params={"fields": fields},
                headers={"Authorization": f"Bearer {token}"},
                json=body,
                timeout=30,
            )
            r.raise_for_status()
            out = []
            for v in r.json().get("data", {}).get("videos", []):
                likes = v.get("like_count", 0)
                comments = v.get("comment_count", 0)
                if likes + comments < min_engagement:
                    continue
                out.append(
                    DiscoveredItem(
                        platform=Platform.TIKTOK,
                        external_id=str(v["id"]),
                        permalink=v.get("share_url", ""),
                        creator=v.get("username", ""),
                        caption=v.get("video_description", ""),
                        media_url="",  # TikTok não expõe media_url direto; download só após permissão
                        like_count=likes,
                        comment_count=comments,
                    )
                )
            return out
        except requests.RequestException as exc:
            self.log.error("tiktok.error", hashtag=hashtag, error=str(exc))
            return []

    # ── Dados de exemplo (DRY_RUN) ─────────────────────────────────────
    def _sample_items(self) -> list[DiscoveredItem]:
        return [
            DiscoveredItem(
                platform=Platform.INSTAGRAM,
                external_id="sample_ig_1",
                permalink="https://www.instagram.com/reel/SAMPLE1/",
                creator="explore_madeira",
                caption="Nascer do sol no Pico do Areeiro 🌅 #madeira",
                media_url="",
                like_count=12800,
                comment_count=340,
            ),
            DiscoveredItem(
                platform=Platform.TIKTOK,
                external_id="sample_tk_1",
                permalink="https://www.tiktok.com/@madeira.vibes/video/SAMPLE",
                creator="madeira.vibes",
                caption="Levada walk POV 🌿 #madeiraisland",
                media_url="",
                like_count=45000,
                comment_count=1200,
            ),
        ]
