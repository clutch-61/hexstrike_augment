from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise RuntimeError(
        "PyYAML is required for UltraRAG integration. "
        "Please install it with `pip install pyyaml`."
    ) from exc


class UltraRAGIntegrationError(RuntimeError):
    """Raised when we cannot talk to the UltraRAG repository."""


class _NoOpMCP:
    """Stub that satisfies the MCP server interface used inside UltraRAG."""

    def tool(self, fn, *_, **__) -> Any:  # pragma: no cover - trivial
        return fn


class UltraRAGKnowledgeBase:
    """
    Thin wrapper around UltraRAG's retriever server so the Ollama MCP client
    can issue knowledge-base searches via a normal Python API.
    """

    def __init__(
        self,
        *,
        ultrarag_root: Optional[Path | str] = None,
        config_path: Optional[Path | str] = None,
    ) -> None:
        self._lock = asyncio.Lock()
        self.ultrarag_root = self._resolve_root(ultrarag_root)
        self._ensure_python_path()

        self.config_path = self._resolve_config_path(config_path)
        self.config = self._load_config(self.config_path)

        self.corpus_path = self._resolve_to_root(self.config.get("corpus_path"))
        self.embedding_path = self._resolve_to_root(self.config.get("embedding_path"))
        self.query_instruction = self.config.get("query_instruction", "") or ""
        self.is_multimodal = bool(self.config.get("is_multimodal", False))

        self._corpus_entries = self._load_corpus_entries(self.corpus_path)
        self._content_positions = self._build_content_positions(self._corpus_entries)
        self._content_offsets: Dict[str, int] = defaultdict(int)

        self.retriever = self._create_retriever()
        self._prepare_index()

    # --------------------------------------------------------------------- utils
    def _resolve_root(self, override: Optional[Path | str]) -> Path:
        root = (
            Path(override)
            if override
            else Path(os.environ.get("ULTRARAG_ROOT", Path.cwd() / "UltraRAG"))
        ).expanduser().resolve()
        if not root.exists():
            raise UltraRAGIntegrationError(
                f"UltraRAG root '{root}' does not exist. "
                "Set ULTRARAG_ROOT to the cloned UltraRAG repository."
            )
        return root

    def _resolve_config_path(self, override: Optional[Path | str]) -> Path:
        if override:
            cfg_path = Path(override).expanduser()
        else:
            cfg_path = self.ultrarag_root / "servers" / "retriever" / "parameter.yaml"
        if not cfg_path.exists():
            raise UltraRAGIntegrationError(
                f"UltraRAG retriever config '{cfg_path}' was not found."
            )
        return cfg_path

    def _ensure_python_path(self) -> None:
        for sub in ("src", "servers/retriever/src"):
            path = self.ultrarag_root / sub
            if not path.exists():
                raise UltraRAGIntegrationError(
                    f"Required UltraRAG path missing: {path}"
                )
            path_str = str(path)
            if path_str not in sys.path:
                sys.path.append(path_str)

    def _resolve_to_root(self, value: Optional[str]) -> Path:
        if not value:
            raise UltraRAGIntegrationError(
                "Retriever parameter file is missing required path entries."
            )
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.ultrarag_root / path).resolve()

    def _load_config(self, cfg_path: Path) -> Dict[str, Any]:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        # Deep copy so we can safely mutate nested structures.
        cfg = copy.deepcopy(data)
        backend_cfg = cfg.get("backend_configs", {})
        faiss_cfg = (
            cfg.get("index_backend_configs", {}).get("faiss", {})
            if cfg.get("index_backend_configs")
            else {}
        )

        if "save_path" in backend_cfg.get("bm25", {}):
            backend_cfg["bm25"]["save_path"] = str(
                self._resolve_to_root(backend_cfg["bm25"]["save_path"])
            )

        if "index_path" in faiss_cfg:
            faiss_cfg["index_path"] = str(self._resolve_to_root(faiss_cfg["index_path"]))

        cfg.setdefault("backend_configs", backend_cfg)
        cfg.setdefault("index_backend_configs", {"faiss": faiss_cfg})
        return cfg

    def _load_corpus_entries(self, corpus_path: Path) -> List[Dict[str, Any]]:
        if not corpus_path.exists():
            raise UltraRAGIntegrationError(
                f"UltraRAG corpus file '{corpus_path}' does not exist."
            )
        entries: List[Dict[str, Any]] = []
        with corpus_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:  # pragma: no cover - data issue
                    raise UltraRAGIntegrationError(
                        f"Corrupt JSON line in corpus '{corpus_path}': {exc}"
                    ) from exc
        if not entries:
            raise UltraRAGIntegrationError(
                f"UltraRAG corpus '{corpus_path}' is empty. "
                "Generate the corpus before starting the MCP server."
            )
        return entries

    def _build_content_positions(
        self, entries: List[Dict[str, Any]]
    ) -> Dict[str, List[int]]:
        positions: Dict[str, List[int]] = defaultdict(list)
        for idx, entry in enumerate(entries):
            content = entry.get("contents")
            if not isinstance(content, str):
                continue
            positions[content].append(idx)
        if not positions:
            raise UltraRAGIntegrationError(
                "No valid entries found in the UltraRAG corpus."
            )
        return positions

    def _create_retriever(self):
        try:
            from retriever import Retriever  # type: ignore
        except Exception as exc:  # pragma: no cover - handled at runtime
            raise UltraRAGIntegrationError(
                "Unable to import UltraRAG retriever. "
                "Install the UltraRAG dependencies inside this environment."
            ) from exc

        retriever = Retriever(_NoOpMCP())
        backend_configs = self.config.get("backend_configs", {})
        index_backend_cfg = self.config.get("index_backend_configs", {})
        gpu_ids = os.environ.get("ULTRARAG_GPU_IDS", self.config.get("gpu_ids"))
        if gpu_ids == "" or gpu_ids is None:
            gpu_ids = None
        elif isinstance(gpu_ids, str) and gpu_ids.lower() in {"cpu", "none"}:
            gpu_ids = None

        retriever.retriever_init(
            model_name_or_path=self.config.get("model_name_or_path"),
            backend_configs=backend_configs,
            batch_size=int(self.config.get("batch_size", 8)),
            corpus_path=str(self.corpus_path),
            gpu_ids=gpu_ids,
            is_multimodal=self.is_multimodal,
            backend=self.config.get("backend", "sentence_transformers"),
            index_backend=self.config.get("index_backend", "faiss"),
            index_backend_configs=index_backend_cfg,
        )
        return retriever

    def _prepare_index(self) -> None:
        backend = getattr(self.retriever, "index_backend", None)
        if backend is None:
            raise UltraRAGIntegrationError(
                "UltraRAG retriever index backend did not initialize."
            )

        backend.load_index()
        if getattr(backend, "index", None) is not None:
            return

        async def _build():
            if not self.embedding_path.exists():
                await self.retriever.retriever_embed(
                    embedding_path=str(self.embedding_path),
                    overwrite=False,
                    is_multimodal=self.is_multimodal,
                )
            self.retriever.retriever_index(
                embedding_path=str(self.embedding_path),
                overwrite=False,
            )
            backend.load_index()

        asyncio.run(_build())

    # ---------------------------------------------------------------- interface
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return UltraRAG passages plus basic metadata for Ollama tools."""
        if not query or not query.strip():
            raise ValueError("Query text cannot be empty.")

        top_k = max(1, min(int(top_k or 5), 20))

        async with self._lock:
            raw = await self.retriever.retriever_search(
                query_list=[query.strip()],
                top_k=top_k,
                query_instruction=self.query_instruction,
            )

        passages = raw.get("ret_psg", [[]])
        if not passages:
            return []

        ranked = []
        for rank, passage in enumerate(passages[0], 1):
            idx = self._next_index_for_passage(passage)
            meta = self._corpus_entries[idx] if idx is not None else {}
            ranked.append(
                {
                    "rank": rank,
                    "id": meta.get("id", idx),
                    "title": meta.get("title"),
                    "metadata": {
                        k: v for k, v in meta.items() if k not in {"contents"}
                    },
                    "content": passage.strip(),
                }
            )
        return ranked

    def _next_index_for_passage(self, passage: str) -> Optional[int]:
        indices = self._content_positions.get(passage)
        if not indices:
            return None
        offset = self._content_offsets[passage]
        idx = indices[offset % len(indices)]
        self._content_offsets[passage] = (offset + 1) % len(indices)
        return idx

    def stats(self) -> Dict[str, Any]:
        backend = getattr(self.retriever, "index_backend", None)
        index_path = getattr(backend, "index_path", None) if backend else None
        return {
            "documents": len(self._corpus_entries),
            "corpus_path": str(self.corpus_path),
            "embedding_path": str(self.embedding_path),
            "index_path": str(index_path) if index_path else "N/A",
            "backend": self.config.get("backend", "sentence_transformers"),
            "index_backend": self.config.get("index_backend", "faiss"),
            "query_instruction": self.query_instruction,
        }

