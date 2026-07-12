"""
Pipeline — orquestra os agentes por estados, sem publicar nada sem permissão.

Um ciclo faz, por esta ordem:
  1. DESCOBRIR   candidatos novos (dedup por external_id).
  2. PEDIR       permissão para candidatos ainda sem pedido.
  3. EXPIRAR     pedidos pendentes há demasiado tempo.
  4. PROCESSAR   candidatos APROVADOS: editar + publicar (respeitando limites).
"""

from __future__ import annotations

from datetime import date

from .agents import DiscoveryAgent, EditorAgent, PermissionAgent, PublisherAgent
from .core.db import session_scope
from .core.logging_setup import get_logger
from .core.models import (
    Candidate,
    CandidateStatus,
    PermissionStatus,
    Post,
    PostStatus,
    utcnow,
)

log = get_logger("pipeline")


class Pipeline:
    def __init__(self) -> None:
        self.discovery = DiscoveryAgent()
        self.permission = PermissionAgent()
        self.editor = EditorAgent()
        self.publisher = PublisherAgent()
        self.config = self.discovery.config
        self.require_approval = self.discovery.settings.require_approval

    def run_cycle(self) -> None:
        log.info("cycle.start")
        self._discover()
        self._request_permissions()
        PermissionAgent.expire_stale()
        self._process_approved()
        log.info("cycle.end")

    # 1) Descoberta ────────────────────────────────────────────────────
    def _discover(self) -> None:
        items = self.discovery.discover()
        new = 0
        with session_scope() as s:
            for item in items:
                exists = (
                    s.query(Candidate).filter_by(external_id=item.external_id).first() is not None
                )
                if exists:
                    continue
                s.add(
                    Candidate(
                        platform=item.platform,
                        external_id=item.external_id,
                        permalink=item.permalink,
                        creator=item.creator,
                        caption=item.caption,
                        media_url=item.media_url,
                        like_count=item.like_count,
                        comment_count=item.comment_count,
                        virality_score=item.virality_score,
                    )
                )
                new += 1
        log.info("discover.done", new_candidates=new)

    # 2) Pedidos de permissão ──────────────────────────────────────────
    def _request_permissions(self) -> None:
        with session_scope() as s:
            pending = (
                s.query(Candidate)
                .filter(Candidate.status == CandidateStatus.DISCOVERED)
                .all()
            )
            ids = [c.id for c in pending]
        for cid in ids:
            self.permission.request_for_candidate(cid)

    # 4) Processar aprovados ────────────────────────────────────────────
    def _process_approved(self) -> None:
        pub_cfg = self.config.get("publishing", {})
        if not self.publisher.within_active_hours():
            log.info("process.skip", reason="fora da janela horária")
            return
        remaining = self._daily_budget_remaining(pub_cfg.get("daily_limit", 6))
        if remaining <= 0:
            log.info("process.skip", reason="limite diário atingido")
            return

        # Candidatos aprovados e ainda sem Post.
        with session_scope() as s:
            approved = (
                s.query(Candidate)
                .filter(Candidate.status == CandidateStatus.APPROVED)
                .filter(~Candidate.id.in_(s.query(Post.candidate_id)))
                .limit(remaining)
                .all()
            )
            batch = [
                {"id": c.id, "permalink": c.permalink, "creator": c.creator, "caption": c.caption}
                for c in approved
            ]

        for c in batch:
            self._edit_and_publish(c)

    def _edit_and_publish(self, c: dict) -> None:
        pub_cfg = self.config.get("publishing", {})
        # Cria o Post em estado QUEUED.
        with session_scope() as s:
            post = Post(candidate_id=c["id"], status=PostStatus.QUEUED)
            s.add(post)
            s.flush()
            post_id = post.id

        edited = self.editor.process(
            permalink=c["permalink"], creator=c["creator"], caption=c["caption"]
        )
        if not edited:
            self._fail(post_id, "edição falhou")
            return

        hashtags = " ".join(pub_cfg.get("default_hashtags", []))
        caption = f"{c['caption']}\n\n{hashtags}".strip()

        with session_scope() as s:
            post = s.get(Post, post_id)
            post.edited_path = edited
            post.caption = caption
            post.status = PostStatus.EDITED

        results = self.publisher.publish(
            video_path_or_url=edited, caption=caption, targets=pub_cfg.get("targets", [])
        )
        ok = any(results.values())
        with session_scope() as s:
            post = s.get(Post, post_id)
            candidate = s.get(Candidate, c["id"])
            if ok:
                post.status = PostStatus.PUBLISHED
                post.published_at = utcnow()
                if candidate:
                    candidate.status = CandidateStatus.PUBLISHED
            else:
                post.status = PostStatus.FAILED
                post.error = f"publicação falhou: {results}"
        log.info("process.item", post=post_id, published=ok, targets=results)

    def _fail(self, post_id: int, reason: str) -> None:
        with session_scope() as s:
            post = s.get(Post, post_id)
            if post:
                post.status = PostStatus.FAILED
                post.error = reason
        log.error("process.failed", post=post_id, reason=reason)

    def _daily_budget_remaining(self, daily_limit: int) -> int:
        today = date.today()
        with session_scope() as s:
            published_today = (
                s.query(Post)
                .filter(Post.status == PostStatus.PUBLISHED)
                .filter(Post.published_at.isnot(None))
                .all()
            )
            used = sum(1 for p in published_today if p.published_at.date() == today)
        return max(0, daily_limit - used)
