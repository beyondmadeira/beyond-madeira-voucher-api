"""
PermissionAgent — o agente que torna isto legítimo.

Gera e regista o pedido de autorização ao criador original. NENHUM
candidato avança para edição/publicação sem um PermissionRequest.GRANTED.

A aprovação é humana por defeito (VIRALPULSE_REQUIRE_APPROVAL=true):
o operador confirma a resposta do criador no dashboard ou por CLI.
"""

from __future__ import annotations

from ..core.config import get_config
from ..core.db import session_scope
from ..core.logging_setup import get_logger
from ..core.models import (
    Candidate,
    CandidateStatus,
    PermissionRequest,
    PermissionStatus,
    utcnow,
)
from .base import BaseAgent

log = get_logger("permission")


class PermissionAgent(BaseAgent):
    name = "permission"

    def request_for_candidate(self, candidate_id: int) -> PermissionRequest | None:
        """Cria e 'envia' o pedido de permissão para um candidato."""
        cfg = self.config.get("permission", {})
        channel = cfg.get("channel", "manual")

        with session_scope() as s:
            candidate = s.get(Candidate, candidate_id)
            if candidate is None or candidate.permission is not None:
                return None

            message = cfg.get("message_template", "").format(creator=candidate.creator).strip()
            req = PermissionRequest(
                candidate_id=candidate.id,
                channel=channel,
                message=message,
                status=PermissionStatus.PENDING,
            )
            candidate.status = CandidateStatus.REQUESTED
            s.add(req)
            s.flush()

            self._deliver(channel, candidate.creator, message)
            self.log.info(
                "permission.requested", candidate=candidate.id, creator=candidate.creator, channel=channel
            )
            s.refresh(req)
            return req

    def _deliver(self, channel: str, creator: str, message: str) -> None:
        """
        Entrega do pedido. Em DRY_RUN (ou canal 'manual') apenas regista;
        o envio real de DM deve ser feito por um humano ou via ferramenta
        aprovada — nunca por automação que viole os ToS da plataforma.
        """
        if self.dry_run or channel == "manual":
            self.log.info("permission.deliver.manual", to=creator, preview=message[:80])
            return
        # Espaço reservado para integração aprovada (ex.: email via API própria).
        self.log.info("permission.deliver", channel=channel, to=creator)

    # ── Resolução (humana) ─────────────────────────────────────────────
    @staticmethod
    def resolve(request_id: int, granted: bool, proof: str = "") -> bool:
        """Marca um pedido como concedido ou negado (ação do operador)."""
        with session_scope() as s:
            req = s.get(PermissionRequest, request_id)
            if req is None or req.status != PermissionStatus.PENDING:
                return False
            req.status = PermissionStatus.GRANTED if granted else PermissionStatus.DENIED
            req.resolved_at = utcnow()
            req.proof = proof
            candidate = s.get(Candidate, req.candidate_id)
            if candidate:
                candidate.status = (
                    CandidateStatus.APPROVED if granted else CandidateStatus.REJECTED
                )
            log.info("permission.resolved", request=request_id, granted=granted)
            return True

    @staticmethod
    def expire_stale() -> int:
        """Expira pedidos pendentes há mais de expiry_days. Devolve nº expirados."""
        cfg = get_config().get("permission", {})
        expiry_days = cfg.get("expiry_days", 7)
        cutoff = utcnow().timestamp() - expiry_days * 86400
        expired = 0
        with session_scope() as s:
            pending = (
                s.query(PermissionRequest)
                .filter(PermissionRequest.status == PermissionStatus.PENDING)
                .all()
            )
            for req in pending:
                if req.requested_at.timestamp() < cutoff:
                    req.status = PermissionStatus.EXPIRED
                    req.resolved_at = utcnow()
                    candidate = s.get(Candidate, req.candidate_id)
                    if candidate:
                        candidate.status = CandidateStatus.REJECTED
                    expired += 1
        if expired:
            log.info("permission.expired", count=expired)
        return expired
