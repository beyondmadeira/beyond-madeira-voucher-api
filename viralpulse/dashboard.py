"""
Dashboard web (FastAPI) — controlo, logs e estatísticas.

Funcionalidades:
  - Login simples por password (VIRALPULSE_DASHBOARD_PASSWORD).
  - Estatísticas: candidatos, pendentes, publicados hoje.
  - Aprovar / negar pedidos de permissão (o gate humano).
  - Adicionar fonte manual (um permalink de conteúdo a considerar).
  - Correr um ciclo à mão.

Arranca com:  uvicorn viralpulse.dashboard:app --host 0.0.0.0 --port 8090
"""

from __future__ import annotations

import secrets
from datetime import date

from fastapi import Cookie, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .agents.permission import PermissionAgent
from .core.config import get_settings
from .core.db import init_db, session_scope
from .core.models import (
    Candidate,
    CandidateStatus,
    PermissionRequest,
    PermissionStatus,
    Platform,
    Post,
    PostStatus,
)
from .pipeline import Pipeline

app = FastAPI(title="ViralPulse Dashboard")
settings = get_settings()

# Sessões em memória (suficiente para um dashboard interno single-node).
_SESSIONS: set[str] = set()


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _authed(session_token: str | None) -> bool:
    return session_token is not None and session_token in _SESSIONS


def _page(body: str, title: str = "ViralPulse") -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="pt"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto;
          padding: 0 1rem; line-height: 1.5; }}
  h1 {{ font-size: 1.4rem; }}
  .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
  .card {{ border: 1px solid #8883; border-radius: 12px; padding: 1rem 1.4rem; }}
  .card b {{ font-size: 1.8rem; display: block; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ text-align: left; padding: .5rem; border-bottom: 1px solid #8883; font-size: .9rem; }}
  button {{ cursor: pointer; border-radius: 8px; border: 1px solid #8886; padding: .4rem .8rem; }}
  .ok {{ background: #16794033; }} .no {{ background: #b0203033; }}
  form.inline {{ display: inline; }}
  input[type=text] {{ padding: .5rem; border-radius: 8px; border: 1px solid #8886; width: 60%; }}
</style></head><body>{body}</body></html>"""
    )


@app.get("/", response_class=HTMLResponse)
def home(session_token: str | None = Cookie(default=None)):
    if not _authed(session_token):
        return _page(
            """<h1>ViralPulse — Login</h1>
            <form method="post" action="/login">
              <input type="password" name="password" placeholder="Password" autofocus>
              <button type="submit">Entrar</button>
            </form>"""
        )

    with session_scope() as s:
        total = s.query(Candidate).count()
        pending = s.query(PermissionRequest).filter_by(status=PermissionStatus.PENDING).count()
        published_today = sum(
            1
            for p in s.query(Post).filter_by(status=PostStatus.PUBLISHED).all()
            if p.published_at and p.published_at.date() == date.today()
        )
        pend_rows = ""
        for r in s.query(PermissionRequest).filter_by(status=PermissionStatus.PENDING).all():
            c = r.candidate
            pend_rows += f"""<tr>
              <td>#{r.id}</td><td>{c.platform.value}</td>
              <td>@{c.creator}</td>
              <td><a href="{c.permalink}" target="_blank">ver</a></td>
              <td>{int(c.virality_score)}</td>
              <td>
                <form class="inline" method="post" action="/permission/{r.id}/grant">
                  <button class="ok" type="submit">✔ Autorizar</button></form>
                <form class="inline" method="post" action="/permission/{r.id}/deny">
                  <button class="no" type="submit">Negar</button></form>
              </td></tr>"""
        pend_rows = pend_rows or "<tr><td colspan=6>Sem pedidos pendentes.</td></tr>"

    dry = "🟡 DRY-RUN (simulação)" if settings.dry_run else "🟢 LIVE"
    body = f"""
      <h1>ViralPulse <small style="font-weight:400">· {dry}</small></h1>
      <div class="cards">
        <div class="card"><b>{total}</b>candidatos</div>
        <div class="card"><b>{pending}</b>à espera de permissão</div>
        <div class="card"><b>{published_today}</b>publicados hoje</div>
      </div>
      <form method="post" action="/run-cycle"><button>▶ Correr um ciclo agora</button></form>

      <h2>Pedidos de permissão pendentes</h2>
      <p style="opacity:.7">Só autorizas aqui quando o criador responder "sim". Isto é o que mantém a página legal.</p>
      <table><tr><th>#</th><th>Plataforma</th><th>Criador</th><th>Original</th><th>Score</th><th>Ação</th></tr>
        {pend_rows}
      </table>

      <h2>Adicionar fonte manual</h2>
      <form method="post" action="/add-source">
        <input type="text" name="permalink" placeholder="https://www.instagram.com/reel/...">
        <input type="text" name="creator" placeholder="@criador" style="width:20%">
        <button type="submit">Adicionar</button>
      </form>
      <p><form method="post" action="/logout"><button>Sair</button></form></p>
    """
    return _page(body)


@app.post("/login")
def login(password: str = Form(...)):
    resp = RedirectResponse("/", status_code=303)
    if secrets.compare_digest(password, settings.dashboard_password):
        token = secrets.token_urlsafe(24)
        _SESSIONS.add(token)
        resp.set_cookie("session_token", token, httponly=True, samesite="lax")
    return resp


@app.post("/logout")
def logout(session_token: str | None = Cookie(default=None)):
    _SESSIONS.discard(session_token or "")
    return RedirectResponse("/", status_code=303)


@app.post("/permission/{req_id}/grant")
def grant(req_id: int, session_token: str | None = Cookie(default=None)):
    if _authed(session_token):
        PermissionAgent.resolve(req_id, granted=True, proof="aprovado via dashboard")
    return RedirectResponse("/", status_code=303)


@app.post("/permission/{req_id}/deny")
def deny(req_id: int, session_token: str | None = Cookie(default=None)):
    if _authed(session_token):
        PermissionAgent.resolve(req_id, granted=False)
    return RedirectResponse("/", status_code=303)


@app.post("/add-source")
def add_source(
    permalink: str = Form(...),
    creator: str = Form(default=""),
    session_token: str | None = Cookie(default=None),
):
    if _authed(session_token) and permalink.strip():
        platform = Platform.TIKTOK if "tiktok.com" in permalink else Platform.INSTAGRAM
        with session_scope() as s:
            exists = s.query(Candidate).filter_by(permalink=permalink).first()
            if not exists:
                s.add(
                    Candidate(
                        platform=platform,
                        external_id=f"manual::{permalink}",
                        permalink=permalink,
                        creator=creator.lstrip("@"),
                        status=CandidateStatus.DISCOVERED,
                    )
                )
    return RedirectResponse("/", status_code=303)


@app.post("/run-cycle")
def run_cycle(session_token: str | None = Cookie(default=None)):
    if _authed(session_token):
        Pipeline().run_cycle()
    return RedirectResponse("/", status_code=303)
