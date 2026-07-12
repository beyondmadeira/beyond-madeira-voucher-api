"""
EditorAgent — download (só de conteúdo autorizado) + edição com FFmpeg.

Regras:
  - NÃO remove watermark do autor original. Só ACRESCENTA crédito visível.
  - Formata para vertical (Reels/TikTok) com scale+pad, sem distorcer.
  - Modo 'news' adiciona um banner de contexto no topo.

Só é chamado para candidatos com permissão concedida (garantido pelo pipeline).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import yt_dlp

from ..core.config import BASE_DIR
from .base import BaseAgent

DOWNLOAD_DIR = BASE_DIR / "downloads"
PROCESSED_DIR = BASE_DIR / "processed"


def _escape_drawtext(text: str) -> str:
    """Escapa caracteres especiais do filtro drawtext do FFmpeg."""
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "’")  # apóstrofo tipográfico evita partir a expressão
        .replace("%", "\\%")
    )


class EditorAgent(BaseAgent):
    name = "editor"

    def __init__(self) -> None:
        super().__init__()
        DOWNLOAD_DIR.mkdir(exist_ok=True)
        PROCESSED_DIR.mkdir(exist_ok=True)

    def process(self, *, permalink: str, creator: str, caption: str) -> str | None:
        """Faz download + edição e devolve o caminho do ficheiro final."""
        source = self._download(permalink)
        if not source:
            return None
        return self._edit(source, creator=creator)

    # ── Download (yt-dlp) ──────────────────────────────────────────────
    def _download(self, url: str) -> Path | None:
        if self.dry_run:
            # Gera um clip de teste sintético para o pipeline correr sem rede.
            return self._synthetic_clip()

        opts = {
            "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
            "format": "bestvideo+bestaudio/best",
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return Path(ydl.prepare_filename(info))
        except Exception as exc:  # noqa: BLE001 — yt-dlp lança vários tipos
            self.log.error("download.error", url=url, error=str(exc))
            return None

    def _synthetic_clip(self) -> Path | None:
        """Cria um clip 3s de teste (requer FFmpeg) para o modo DRY_RUN."""
        out = DOWNLOAD_DIR / f"synthetic_{int(time.time())}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=teal:s=1080x1920:d=3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-shortest", "-pix_fmt", "yuv420p", str(out),
        ]
        return out if self._run_ffmpeg(cmd) else None

    # ── Edição (FFmpeg) ────────────────────────────────────────────────
    def _edit(self, source: Path, *, creator: str) -> str | None:
        ed = self.config.get("editor", {})
        brand = self.config.get("brand", {})
        res = ed.get("output_resolution", "1080x1920")
        width, height = (int(x) for x in res.split("x"))

        credit = brand.get("credit_template", "Créditos: @{creator}").format(creator=creator or "criador")
        watermark = brand.get("watermark", "")

        out = PROCESSED_DIR / f"viral_{int(time.time())}.mp4"

        # scale+pad → vertical sem distorção
        vf = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
            # crédito visível (rodapé)
            f"drawtext=text='{_escape_drawtext(credit)}':fontcolor=white:fontsize={ed.get('credit_fontsize', 42)}"
            f":x=(w-tw)/2:y=h-th-60:box=1:boxcolor=black@0.6:boxborderw=12",
        ]
        if watermark:
            vf.append(
                f"drawtext=text='{_escape_drawtext(watermark)}':fontcolor=yellow:fontsize=30"
                f":x=w-tw-30:y=40:box=1:boxcolor=black@0.5:boxborderw=10"
            )
        if ed.get("news_overlay"):
            vf.append(
                "drawbox=x=0:y=0:w=iw:h=90:color=black@0.55:t=fill,"
                f"drawtext=text='{_escape_drawtext(brand.get('name', ''))}':fontcolor=white:fontsize=34"
                ":x=30:y=28"
            )

        cmd = [
            "ffmpeg", "-y", "-i", str(source),
            "-vf", ",".join(vf),
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(out),
        ]
        if not self._run_ffmpeg(cmd):
            return None
        self.log.info("editor.done", output=str(out), creator=creator)
        return str(out)

    def _run_ffmpeg(self, cmd: list[str]) -> bool:
        if shutil.which("ffmpeg") is None:
            self.log.error("ffmpeg.missing", hint="instala FFmpeg (apt install ffmpeg)")
            return False
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as exc:
            self.log.error("ffmpeg.error", stderr=exc.stderr.decode(errors="ignore")[-500:])
            return False
