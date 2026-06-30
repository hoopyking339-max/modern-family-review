"""Processing state tracking — incremental processing & resume support.

Tracks which PDFs/episodes have been processed so we can:
- Skip already-processed episodes
- Detect when a PDF has changed (hash mismatch)
- Resume after interruption (state saved after each episode)
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from .config import DATA_DIR


STATE_FILE = DATA_DIR / "processing_state.json"


@dataclass
class PDFState:
    file_path: str           # absolute path to PDF
    file_hash: str           # SHA256 first 16 chars
    file_mtime: float        # last modified timestamp
    last_checked: str        # ISO datetime
    total_episodes: int      # total episodes detected in PDF
    episodes_processed: list[str] = field(default_factory=list)  # ["S01E01", ...]
    episode_titles: dict = field(default_factory=dict)  # {"S01E01": "Pilot", ...}
    episode_counts: dict = field(default_factory=dict)  # {"S01E01": {"notes": 3, "ai": 12}, ...}


class StateManager:
    """Manages processing state persisted to JSON."""

    def __init__(self, state_path: Optional[Path] = None):
        self._path = state_path or STATE_FILE
        self._states: dict[str, PDFState] = {}

    # ---- load / save ----

    def load(self) -> dict[str, PDFState]:
        """Load state from disk. Returns dict keyed by PDF filename."""
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._states = {}
                for name, d in raw.get("pdfs", {}).items():
                    self._states[name] = PDFState(
                        file_path=d.get("file_path", ""),
                        file_hash=d.get("file_hash", ""),
                        file_mtime=d.get("file_mtime", 0),
                        last_checked=d.get("last_checked", ""),
                        total_episodes=d.get("total_episodes", 0),
                        episodes_processed=d.get("episodes_processed", []),
                        episode_titles=d.get("episode_titles", {}),
                    )
            except (json.JSONDecodeError, KeyError):
                self._states = {}
        return self._states

    def save(self):
        """Persist current state to disk."""
        raw = {"updated": datetime.now().isoformat(), "pdfs": {}}
        for name, st in self._states.items():
            raw["pdfs"][name] = {
                "file_path": st.file_path,
                "file_hash": st.file_hash,
                "file_mtime": st.file_mtime,
                "last_checked": st.last_checked,
                "total_episodes": st.total_episodes,
                "episodes_processed": st.episodes_processed,
                "episode_titles": st.episode_titles,
            }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- hash ----

    @staticmethod
    def compute_hash(file_path: Path) -> str:
        """Compute a short hash of file contents (first 16 chars of SHA256)."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()[:16]

    # ---- query ----

    def get(self, pdf_name: str) -> Optional[PDFState]:
        """Get state for a PDF by its filename."""
        return self._states.get(pdf_name)

    def is_processed(self, pdf_path: Path, episode_label: str) -> bool:
        """Check if a specific episode has been processed from this PDF."""
        name = pdf_path.name
        st = self._states.get(name)
        if st is None:
            return False
        current_hash = self.compute_hash(pdf_path)
        if st.file_hash != current_hash:
            # PDF has changed — mark as unprocessed
            return False
        return episode_label in st.episodes_processed

    def is_pdf_current(self, pdf_path: Path) -> bool:
        """Check if the PDF hasn't changed since last processing."""
        name = pdf_path.name
        st = self._states.get(name)
        if st is None:
            return False
        return st.file_hash == self.compute_hash(pdf_path)

    def get_unprocessed(self, pdf_path: Path, all_episodes: list[str]) -> list[str]:
        """Return list of episode labels that still need processing."""
        name = pdf_path.name
        st = self._states.get(name)
        if st is None or st.file_hash != self.compute_hash(pdf_path):
            return all_episodes  # PDF is new or changed — all need processing
        return [ep for ep in all_episodes if ep not in st.episodes_processed]

    # ---- mutate ----

    def register_pdf(self, pdf_path: Path, episodes: list[str], titles: dict = None):
        """Register a PDF and its episodes in the state (doesn't mark as processed)."""
        name = pdf_path.name
        file_hash = self.compute_hash(pdf_path)
        mtime = pdf_path.stat().st_mtime
        existing = self._states.get(name)
        # Preserve already-processed episodes if the hash hasn't changed
        old_processed = []
        old_titles = {}
        if existing and existing.file_hash == file_hash:
            old_processed = existing.episodes_processed
            old_titles = existing.episode_titles
        self._states[name] = PDFState(
            file_path=str(pdf_path),
            file_hash=file_hash,
            file_mtime=mtime,
            last_checked=datetime.now().isoformat(),
            total_episodes=len(episodes),
            episodes_processed=old_processed,
            episode_titles={**old_titles, **(titles or {})},
        )

    def mark_processed(self, pdf_path: Path, episode_label: str, title: str = ""):
        """Mark an episode as successfully processed."""
        name = pdf_path.name
        if name not in self._states:
            self._states[name] = PDFState(
                file_path=str(pdf_path),
                file_hash=self.compute_hash(pdf_path),
                file_mtime=pdf_path.stat().st_mtime,
                last_checked=datetime.now().isoformat(),
                total_episodes=0,
            )
        st = self._states[name]
        if episode_label not in st.episodes_processed:
            st.episodes_processed.append(episode_label)
        if title:
            st.episode_titles[episode_label] = title
        st.last_checked = datetime.now().isoformat()
        self.save()

    def mark_failed(self, pdf_path: Path, episode_label: str, error: str):
        """Record a processing failure (logged but not blocking)."""
        name = pdf_path.name
        if name in self._states:
            st = self._states[name]
            # Don't add to processed list, but update last_checked
            st.last_checked = datetime.now().isoformat()
        self.save()

    # ---- aggregate ----

    def get_all_episodes(self) -> dict[str, dict]:
        """Return all known episodes across all PDFs.
        Returns: {pdf_name: {"total": N, "processed": [...], "unprocessed": [...], "titles": {}}}
        """
        result = {}
        for name, st in self._states.items():
            result[name] = {
                "total": st.total_episodes,
                "processed": list(st.episodes_processed),
                "unprocessed": [
                    ep for ep in self._discover_episode_list(st)
                    if ep not in st.episodes_processed
                ],
                "titles": dict(st.episode_titles),
                "last_checked": st.last_checked,
            }
        return result

    @staticmethod
    def _discover_episode_list(st: PDFState) -> list[str]:
        """Best-effort reconstruct episode list from state."""
        # Use processed + titles as the canonical list
        all_eps = set(st.episodes_processed) | set(st.episode_titles.keys())
        if not all_eps and st.total_episodes:
            # Try to reconstruct from expected range
            # Most Modern Family seasons have ~24 episodes
            return []
        return sorted(all_eps) if all_eps else []

    # ---- summary ----

    def summary(self) -> str:
        """Human-readable summary of processing state."""
        lines = []
        total_processed = 0
        total_all = 0
        for name, st in self._states.items():
            total_processed += len(st.episodes_processed)
            total_all += st.total_episodes
            lines.append(
                f"  {name}: {len(st.episodes_processed)}/{st.total_episodes} episodes"
            )
        lines.insert(0, f"Total: {total_processed}/{total_all} episodes processed across {len(self._states)} PDF(s)")
        return "\n".join(lines)
