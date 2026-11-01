"""Motor de RAG Estruturado sobre Runbooks em Markdown (Frontmatter YAML + Seções + BM25)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi

load_dotenv()

RUNBOOKS_DIR = Path(
    os.getenv("OPS_KB_RUNBOOKS_DIR", str(Path(__file__).resolve().parents[2] / "runbooks"))
)


def tokenize(text: str) -> list[str]:
    """Extrai palavras e termos técnicos em minúsculas para o índice BM25."""
    return re.findall(r"[a-zA-Z0-9_À-ÿ\-\.]+", text.lower())


class RunbookRAG:
    """Indexa os arquivos Markdown divididos por seções (`## `) e busca via BM25."""

    def __init__(self, runbooks_dir: Path = RUNBOOKS_DIR) -> None:
        self.sections: list[dict[str, Any]] = []
        self._bm25: BM25Okapi | None = None
        self._load_runbooks(runbooks_dir)

    def _load_runbooks(self, runbooks_dir: Path) -> None:
        if not runbooks_dir.exists():
            return

        for md_file in sorted(runbooks_dir.glob("*.md")):
            raw = md_file.read_text(encoding="utf-8")

            # 1. Extrai metadados do Frontmatter YAML (entre --- e ---)
            meta: dict[str, Any] = {}
            body = raw
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) == 3:
                    meta = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()

            # 2. Divide o Markdown em seções estruturadas (## ou ### Título da Seção)
            chunks = re.split(r"\n(?=#{2,3}\s+)", body)
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk or chunk.startswith("# "):
                    continue

                first_line, _, content = chunk.partition("\n")
                heading = first_line.lstrip("#").strip()

                # Texto combinado (Metadados + Título + Conteúdo) usado pelo BM25
                search_blob = " ".join(
                    [
                        str(meta.get("id", md_file.stem)),
                        str(meta.get("service", "")),
                        heading,
                        " ".join(meta.get("tags", [])),
                        " ".join(meta.get("symptoms", [])),
                        content,
                    ]
                )

                self.sections.append(
                    {
                        "runbook_id": meta.get("id", md_file.stem),
                        "service": str(meta.get("service", "general")).lower(),
                        "severity": str(meta.get("severity", "medium")).lower(),
                        "section": heading,
                        "content": content.strip(),
                        "file": md_file.name,
                        "_tokens": tokenize(search_blob),
                    }
                )

        if self.sections:
            self._bm25 = BM25Okapi([s["_tokens"] for s in self.sections])

    def search(
        self, query: str, service: str | None = None, top_k: int = 3
    ) -> list[dict[str, Any]]:
        """Busca as seções mais relevantes usando pontuação BM25 + filtro de serviço."""
        if not self.sections or not self._bm25:
            return []

        scores = self._bm25.get_scores(tokenize(query))
        ranked: list[tuple[float, dict[str, Any]]] = []

        for score, sec in zip(scores, self.sections):
            if service and sec["service"] != service.lower():
                continue
            # Bônus simples se o serviço ou termo exato estiver no título da seção
            bonus = 2.0 if query.lower() in sec["section"].lower() else 0.0
            if score + bonus > 0:
                ranked.append((float(score + bonus), sec))

        ranked.sort(key=lambda item: item[0], reverse=True)

        return [
            {
                "score": round(score, 2),
                "runbook_id": sec["runbook_id"],
                "service": sec["service"],
                "severity": sec["severity"],
                "section": sec["section"],
                "content": sec["content"],
                "file": sec["file"],
            }
            for score, sec in ranked[:top_k]
        ]
