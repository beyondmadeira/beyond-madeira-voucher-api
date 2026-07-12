"""
Modelos de dados do ViralPulse.

O fluxo de estados é o coração do sistema e o que garante que NADA é
publicado sem passar por permissão:

    Candidate (DISCOVERED)
        └─ pedido enviado ─▶ PermissionRequest (PENDING)
                                  ├─ GRANTED ─▶ Post (QUEUED → EDITED → PUBLISHED)
                                  └─ DENIED / EXPIRED ─▶ fim (descartado)

Sem um PermissionRequest.GRANTED, um Candidate nunca chega a Post.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Platform(str, enum.Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class CandidateStatus(str, enum.Enum):
    DISCOVERED = "discovered"      # encontrado pela descoberta
    REQUESTED = "requested"        # pedido de permissão enviado
    APPROVED = "approved"          # criador autorizou
    REJECTED = "rejected"          # negado ou expirado
    PUBLISHED = "published"        # já publicado


class PermissionStatus(str, enum.Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"


class PostStatus(str, enum.Enum):
    QUEUED = "queued"
    EDITED = "edited"
    PUBLISHED = "published"
    FAILED = "failed"


class Candidate(Base):
    """Conteúdo viral descoberto via API oficial. Metadata guardada aqui."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform))
    external_id: Mapped[str] = mapped_column(String(255), unique=True)  # id na plataforma
    permalink: Mapped[str] = mapped_column(String(1024))
    creator: Mapped[str] = mapped_column(String(255), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    media_url: Mapped[str] = mapped_column(String(1024), default="")
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    virality_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus), default=CandidateStatus.DISCOVERED
    )
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    permission: Mapped["PermissionRequest | None"] = relationship(
        back_populates="candidate", uselist=False
    )
    post: Mapped["Post | None"] = relationship(back_populates="candidate", uselist=False)


class PermissionRequest(Base):
    """Registo do pedido de autorização ao criador — a 'licença' do conteúdo."""

    __tablename__ = "permission_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    channel: Mapped[str] = mapped_column(String(64))          # instagram_dm | email | manual
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[PermissionStatus] = mapped_column(
        Enum(PermissionStatus), default=PermissionStatus.PENDING
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Prova de consentimento (screenshot url, texto da resposta, etc.)
    proof: Mapped[str] = mapped_column(Text, default="")

    candidate: Mapped["Candidate"] = relationship(back_populates="permission")


class Post(Base):
    """Um item que passou na permissão e está no pipeline de edição/publicação."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    edited_path: Mapped[str] = mapped_column(String(1024), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PostStatus] = mapped_column(Enum(PostStatus), default=PostStatus.QUEUED)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="post")
