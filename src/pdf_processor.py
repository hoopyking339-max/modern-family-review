"""PDF processing: extract script text, colored text annotations, and page structure."""

import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import fitz


@dataclass
class TextAnnotation:
    """A user text annotation (colored text) found in the PDF."""
    text: str
    color: str  # hex color e.g. "#007aff"
    page: int
    bbox: tuple  # (x0, y0, x1, y1)
    font_size: float
    context_before: str = ""  # surrounding script lines
    context_after: str = ""


@dataclass
class PageContent:
    """Content of a single PDF page."""
    page_num: int
    raw_text: str
    blocks: list  # raw text blocks from PyMuPDF
    annotations: list[TextAnnotation] = field(default_factory=list)
    episode_info: str = ""  # e.g. "Modern Family Season 1x08 page 2"


@dataclass
class Episode:
    """A detected episode with its page range."""
    season: int
    episode: int
    title: str = ""
    start_page: int = 0
    end_page: int = 0
    pages: list[PageContent] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"S{self.season:02d}E{self.episode:02d}"


@dataclass
class ScriptData:
    """Complete extracted data from a PDF script."""
    pdf_path: Path
    total_pages: int
    pages: list[PageContent]
    episodes: list[Episode]
    all_annotations: list[TextAnnotation]


def extract_page_content(page: fitz.Page, page_num: int) -> PageContent:
    """Extract text and annotations from a single page."""
    # Get all text blocks
    blocks = page.get_text("dict")["blocks"]

    # Build raw text
    raw_text = page.get_text("text")

    # Extract colored text annotations (non-standard text colors)
    annotations = []
    episode_info = ""

    for block in blocks:
        if block.get("type") != 0:  # not a text block
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                color = span.get("color", 0)
                text = span["text"].strip()

                # Grey page header (#aaaaaa) = episode info
                if color == 0xaaaaaa and "Modern Family" in text:
                    episode_info = text
                    continue

                # Non-standard colors = user annotations
                if color not in (0, 0x191919) and text:
                    annotations.append(TextAnnotation(
                        text=text,
                        color=f"#{color:06x}",
                        page=page_num,
                        bbox=tuple(span["bbox"]),
                        font_size=span.get("size", 0),
                    ))

    # Add context to annotations (surrounding script lines)
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    for ann in annotations:
        # Find the annotation text in the lines, get surrounding context
        for i, line in enumerate(lines):
            if ann.text[:20] in line:
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context_lines = lines[start:end]
                ann.context_before = " ".join(context_lines[:2])
                ann.context_after = " ".join(context_lines[2:])
                break

    return PageContent(
        page_num=page_num,
        raw_text=raw_text,
        blocks=blocks,
        annotations=annotations,
        episode_info=episode_info,
    )


def detect_episodes(pages: list[PageContent]) -> list[Episode]:
    """Detect episode boundaries from page headers."""
    episodes = []
    current_ep = None

    # Patterns to match episode headers
    ep_pattern = re.compile(
        r"(?:Modern Family\s+)?Season\s+(\d+)\s*x\s*(\d+)|"
        r"S(\d+)E(\d+)|"
        r"(\d+)x(\d+)"
    )

    for page in pages:
        match = ep_pattern.search(page.episode_info)
        if match:
            groups = match.groups()
            if groups[0] and groups[1]:
                season, ep_num = int(groups[0]), int(groups[1])
            elif groups[2] and groups[3]:
                season, ep_num = int(groups[2]), int(groups[3])
            elif groups[4] and groups[5]:
                season, ep_num = int(groups[4]), int(groups[5])
            else:
                continue

            label = f"S{season:02d}E{ep_num:02d}"

            # Start new episode
            if current_ep is None or current_ep.label != label:
                if current_ep:
                    current_ep.end_page = page.page_num - 1
                    episodes.append(current_ep)

                current_ep = Episode(
                    season=season,
                    episode=ep_num,
                    start_page=page.page_num,
                    pages=[page],
                )
            else:
                current_ep.pages.append(page)
        elif current_ep:
            current_ep.pages.append(page)

    # Last episode
    if current_ep:
        current_ep.end_page = pages[-1].page_num if pages else 0
        episodes.append(current_ep)

    return episodes


def process_pdf(pdf_path: str | Path) -> ScriptData:
    """Process a PDF script file and extract all data."""
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))

    pages = []
    all_annotations = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
        content = extract_page_content(page, page_num + 1)
        pages.append(content)
        all_annotations.extend(content.annotations)

    doc.close()

    episodes = detect_episodes(pages)

    return ScriptData(
        pdf_path=pdf_path,
        total_pages=len(pages),
        pages=pages,
        episodes=episodes,
        all_annotations=all_annotations,
    )


def get_episode_script(episode: Episode) -> str:
    """Get the full script text for an episode."""
    lines = []
    for page in episode.pages:
        text = page.raw_text.strip()
        if text:
            lines.append(text)
    return "\n\n".join(lines)


def get_annotations_for_episode(
    script_data: ScriptData, episode: Episode
) -> list[TextAnnotation]:
    """Get all user annotations that fall within an episode's page range."""
    return [
        a for a in script_data.all_annotations
        if episode.start_page <= a.page <= episode.end_page
    ]
