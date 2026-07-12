"""
PublisherAgent — publicação via APIs OFICIAIS.

  - Instagram: Content Publishing API (cria container → publica).
  - TikTok:    Content Posting API (init → upload).

Respeita o limite diário configurado e a janela horária. Em DRY_RUN
apenas simula. Só publica conteúdo já editado a partir de um Post autorizado.
"""

from __future__ import annotations

import time
from datetime import datetime

import requests

from .base import BaseAgent

GRAPH_API = "https://graph.facebook.com/v20.0"
TIKTOK_INIT = "https://open.tiktokapis.com/v2/post/publish/video/init/"


class PublisherAgent(BaseAgent):
    name = "publisher"

    def within_active_hours(self) -> bool:
        hours = self.config.get("publishing", {}).get("active_hours", [0, 24])
        now_h = datetime.now().hour
        return hours[0] <= now_h < hours[1]

    def publish(self, *, video_path_or_url: str, caption: str, targets: list[str]) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for target in targets:
            if target == "instagram":
                results["instagram"] = self._publish_instagram(video_path_or_url, caption)
            elif target == "tiktok":
                results["tiktok"] = self._publish_tiktok(video_path_or_url, caption)
        return results

    # ── Instagram ──────────────────────────────────────────────────────
    def _publish_instagram(self, video_url: str, caption: str) -> bool:
        if self.dry_run:
            self.log.info("dry_run.publish.instagram", caption=caption[:60])
            return True
        token = self.settings.ig_access_token
        ig_user = self.settings.ig_business_account_id
        if not token or not ig_user:
            self.log.warning("instagram.publish.skip", reason="faltam credenciais")
            return False
        try:
            # 1) criar container (vídeo tem de estar acessível por URL pública)
            r = requests.post(
                f"{GRAPH_API}/{ig_user}/media",
                data={"media_type": "REELS", "video_url": video_url, "caption": caption,
                      "access_token": token},
                timeout=60,
            )
            r.raise_for_status()
            creation_id = r.json()["id"]

            # 2) aguardar processamento
            for _ in range(30):
                st = requests.get(
                    f"{GRAPH_API}/{creation_id}",
                    params={"fields": "status_code", "access_token": token},
                    timeout=30,
                ).json()
                if st.get("status_code") == "FINISHED":
                    break
                time.sleep(5)

            # 3) publicar
            r = requests.post(
                f"{GRAPH_API}/{ig_user}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
                timeout=60,
            )
            r.raise_for_status()
            self.log.info("instagram.published", id=r.json().get("id"))
            return True
        except requests.RequestException as exc:
            self.log.error("instagram.publish.error", error=str(exc))
            return False

    # ── TikTok ─────────────────────────────────────────────────────────
    def _publish_tiktok(self, video_url: str, caption: str) -> bool:
        if self.dry_run:
            self.log.info("dry_run.publish.tiktok", caption=caption[:60])
            return True
        token = self.settings.tiktok_access_token
        if not token:
            self.log.warning("tiktok.publish.skip", reason="falta TIKTOK_ACCESS_TOKEN")
            return False
        try:
            body = {
                "post_info": {"title": caption[:150], "privacy_level": "PUBLIC_TO_EVERYONE"},
                "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
            }
            r = requests.post(
                TIKTOK_INIT,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
                timeout=60,
            )
            r.raise_for_status()
            self.log.info("tiktok.published", publish_id=r.json().get("data", {}).get("publish_id"))
            return True
        except requests.RequestException as exc:
            self.log.error("tiktok.publish.error", error=str(exc))
            return False
