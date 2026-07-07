"""
Madeira Daily — hub de operações do media brand.
Plataforma quase-independente servida em /madeiradaily:
sidebar própria, conteúdo em markdown (content/madeiradaily/),
proteção por password simples (MADEIRADAILY_PASSWORD).
"""

import os
import re

import markdown as md_lib
from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

bp = Blueprint("madeiradaily", __name__, url_prefix="/madeiradaily")

CONTENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "content", "madeiradaily")
)

SECTIONS = [
    {"slug": "painel", "title": "Painel Geral", "icon": "📍", "file": "00-painel-geral.md"},
    {"slug": "estrategia", "title": "Estratégia", "icon": "🧠", "file": "02-estrategia.md"},
    {"slug": "blueprint", "title": "Blueprint Completo", "icon": "📘", "file": "02b-blueprint.md"},
    {"slug": "analise-mercado", "title": "Análise de Mercado", "icon": "📊", "file": "03-analise-mercado.md"},
    {"slug": "manual-normas", "title": "Manual de Normas", "icon": "📕", "file": "01-manual-normas.md"},
    {"slug": "banco-ideias", "title": "Banco de Ideias", "icon": "💡", "file": "04-banco-ideias.md"},
    {"slug": "inspiracao", "title": "Inspiração & Tendências", "icon": "🎬", "file": "04b-inspiracao.md"},
    {"slug": "top100", "title": "Top 100 por Formato", "icon": "🏆", "file": "04c-top100.md"},
    {"slug": "top100-artigos", "title": "Top 100 Artigos", "icon": "📰", "file": "04d-top100-artigos.md"},
    {"slug": "calendario", "title": "Calendário Editorial", "icon": "🗓️", "file": "05-calendario.md"},
    {"slug": "guioes", "title": "Guiões de Lançamento", "icon": "🎬", "file": "05b-guioes-lancamento.md"},
    {"slug": "copy-hooks", "title": "Copy & Hooks", "icon": "✍️", "file": "06-copy-hooks.md"},
    {"slug": "kpis", "title": "KPIs & Relatórios", "icon": "📈", "file": "07-kpis.md"},
    {"slug": "parcerias", "title": "Parcerias & Monetização", "icon": "🤝", "file": "08-parcerias.md"},
    {"slug": "legal", "title": "Legal & Compliance", "icon": "⚖️", "file": "09-legal.md"},
    {"slug": "beyond-madeira", "title": "Ligação Beyond Madeira", "icon": "🔗", "file": "10-beyond-madeira.md"},
]

# Páginas roteáveis mas fora da sidebar (bibliotecas ligadas a partir de "Top 100")
EXTRA_PAGES = [
    {"slug": "top-instagram", "title": "Top Instagram — Investigação", "icon": "🎞️", "file": "04e-top-instagram.md"},
    {"slug": "top-tiktok", "title": "Top TikToks — Investigação", "icon": "🎵", "file": "04f-top-tiktok.md"},
    {"slug": "top-youtube", "title": "Top YouTube — Investigação", "icon": "📺", "file": "04g-top-youtube.md"},
    {"slug": "influencers", "title": "Influencers & Criadores Madeira", "icon": "🌍", "file": "04h-influencers.md"},
    {"slug": "formatos", "title": "Formatos Internacionais", "icon": "🎨", "file": "04i-formatos.md"},
]

_BY_SLUG = {s["slug"]: s for s in SECTIONS + EXTRA_PAGES}


def _read_section(section):
    path = os.path.join(CONTENT_DIR, section["file"])
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _render_markdown(text):
    return md_lib.markdown(
        text,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
        output_format="html5",
    )


@bp.before_request
def _require_login():
    if request.endpoint == "madeiradaily.login":
        return None
    password = current_app.config.get("MADEIRADAILY_PASSWORD", "")
    if password and not session.get("madeiradaily_auth"):
        return redirect(url_for("madeiradaily.login", next=request.path))
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = current_app.config.get("MADEIRADAILY_PASSWORD", "")
        if request.form.get("password", "") == password:
            session["madeiradaily_auth"] = True
            session.permanent = True
            return redirect(request.args.get("next") or url_for("madeiradaily.index"))
        error = "Password incorreta."
    return render_template("madeiradaily/login.html", error=error)


@bp.route("/logout")
def logout():
    session.pop("madeiradaily_auth", None)
    return redirect(url_for("madeiradaily.login"))


@bp.route("/")
def index():
    return redirect(url_for("madeiradaily.page", slug=SECTIONS[0]["slug"]))


@bp.route("/pesquisa")
def search():
    query = (request.args.get("q") or "").strip()
    results = []
    if len(query) >= 2:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        for section in SECTIONS + EXTRA_PAGES:
            text = _read_section(section)
            if not text:
                continue
            for match in pattern.finditer(text):
                start = max(0, match.start() - 90)
                end = min(len(text), match.end() + 90)
                snippet = text[start:end].replace("\n", " ").strip()
                snippet = re.sub(r"[#*|`>\[\]]", "", snippet)
                results.append({"section": section, "snippet": snippet})
                if sum(1 for r in results if r["section"] is section) >= 3:
                    break
    return render_template(
        "madeiradaily/search.html",
        sections=SECTIONS,
        active=None,
        query=query,
        results=results,
    )


@bp.route("/<slug>")
def page(slug):
    section = _BY_SLUG.get(slug)
    if section is None:
        abort(404)
    raw = _read_section(section)
    if raw is None:
        html = (
            "<h1>%s</h1><p><em>Esta secção ainda está a ser preparada.</em></p>"
            % section["title"]
        )
    else:
        html = _render_markdown(raw)
    return render_template(
        "madeiradaily/page.html",
        sections=SECTIONS,
        active=section,
        content=html,
    )
