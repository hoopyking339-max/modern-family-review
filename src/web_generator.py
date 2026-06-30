"""Generate interactive static HTML review pages — clean accordion style."""

import json
from pathlib import Path
from typing import Optional

from .config import OUTPUT_DIR
from .llm_organizer import EpisodeReview


CATEGORY_ICONS = {
    "phrase": "💬",
    "vocabulary": "📖",
    "grammar": "📐",
    "culture": "🇺🇸",
    "pronunciation": "🔊",
    "pragmatics": "🎭",
}


def build_episode_html(review: EpisodeReview) -> str:
    """Generate a single-episode review with collapsible cards."""

    scene_sections = []
    toc_items = []
    point_index = 0  # global index for review mode navigation

    for scene in review.scenes:
        scene_id = scene["name"].replace(" ", "-").replace("'", "")[:40]
        points_html = []

        for p in scene["points"]:
            is_user = p.source == "user_annotation"
            badge_class = "badge-user" if is_user else "badge-ai"
            badge_text = "Your note" if is_user else "AI found"
            icon = CATEGORY_ICONS.get(p.category, "💡")

            examples_html = ""
            if p.examples:
                items = "".join(f"<li>{e}</li>" for e in p.examples[:3])
                examples_html = f'<div class="examples"><span class="label">Examples</span><ul>{items}</ul></div>'

            related_html = ""
            if p.related:
                tags = ''.join('<span class="tag">' + r + '</span>' for r in p.related[:6])
                related_html = '<div class="related"><span class="label">See also</span> ' + tags + '</div>'

            # YouTube search query — generic phrase search, any show
            yt_query = p.original_text.strip().replace('"', '').replace("'", "")
            if len(yt_query) > 60:
                yt_query = yt_query[:60]
            yt_query += " tv show scene"

            # Store point data as JSON for review mode
            point_json = json.dumps({
                "quote": p.original_text,
                "category": p.category,
                "frequency": p.frequency,
                "context": p.context,
                "explanation": p.explanation,
                "examples": p.examples[:3],
                "related": p.related[:6],
                "formality": p.formality,
                "source": "user" if is_user else "ai",
            }, ensure_ascii=False).replace("'", "&#39;").replace("\\", "\\\\")

            points_html.append(f'''
            <div class="point { 'user' if is_user else 'ai' }" data-source="{'user' if is_user else 'ai'}" data-index="{point_index}" data-quote="{p.original_text.replace(chr(34), '&quot;')}" data-ytquery="{yt_query}" data-point='{point_json}'>
                <div class="point-summary" onclick="togglePoint(this)">
                    <div class="point-left">
                        <span class="badge {badge_class}">{badge_text}</span>
                        <span class="cat">{icon} {p.category}</span>
                        <span class="freq freq-{p.frequency}">{p.frequency}</span>
                    </div>
                    <div class="point-quote">"{p.original_text}"</div>
                    <div class="point-hint">{p.explanation[:80]}{'...' if len(p.explanation) > 80 else ''}</div>
                    <div class="point-actions">
                        <button class="btn-record" onclick="event.stopPropagation();toggleRecord(this)" title="Record your voice">🎤</button>
                        <span class="expand-icon">▸</span>
                    </div>
                </div>
                <div class="point-detail">
                    <div class="detail-context">{p.context}</div>
                    <div class="detail-explanation">{p.explanation}</div>
                    {examples_html}
                    {related_html}
                    {f'<div class="detail-meta">{p.formality}</div>' if p.formality else ''}
                    <div class="video-container" data-loaded="0">
                        <div class="video-placeholder">Loading video clip...</div>
                    </div>
                </div>
            </div>
            ''')
            point_index += 1

        if points_html:
            scene_id_attr = scene_id
            toc_items.append(f'<li data-scene="{scene_id_attr}"><a href="#{scene_id_attr}">{scene["name"]} <span class="count">{len(points_html)}</span></a></li>')
            scene_sections.append(f'''
            <section id="{scene_id_attr}" class="scene">
                <h3>{scene["name"]}</h3>
                <div class="points">{"".join(points_html)}</div>
            </section>
            ''')

    total_user = sum(1 for s in review.scenes for p in s["points"] if p.source == "user_annotation")
    total_ai = sum(1 for s in review.scenes for p in s["points"] if p.source == "ai_discovery")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#2563eb">
<link rel="manifest" href="/manifest.json">
<title>{review.episode_label} · Modern Family</title>
<style>
:root {{
    --bg: #fff;
    --card: #fafafa;
    --text: #222;
    --muted: #888;
    --border: #eee;
    --accent: #2563eb;
    --user-stripe: #f59e0b;
    --ai-stripe: #3b82f6;
    --user-bg: #fffbeb;
    --ai-bg: #eff6ff;
    --sidebar-w: 260px;
}}
[data-theme="dark"] {{
    --bg: #1a1a1a;
    --card: #252525;
    --text: #ddd;
    --muted: #999;
    --border: #333;
    --user-bg: #2d2410;
    --ai-bg: #101d2d;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}

/* Top bar */
.topbar {{ border-bottom: 1px solid var(--border); padding: 14px 24px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; position: sticky; top: 0; background: var(--bg); z-index: 10; }}
.topbar h1 {{ font-size: 1.1em; font-weight: 600; white-space: nowrap; }}
.topbar .ep {{ color: var(--muted); font-size: 0.9em; }}
.topbar .spacer {{ flex: 1; }}
.topbar input {{ border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; font-size: 0.85em; background: var(--card); color: var(--text); width: 180px; }}
.topbar button, .topbar a.btn {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 6px 14px; cursor: pointer; font-size: 0.82em; color: var(--text); text-decoration: none; }}
.topbar button:hover {{ background: var(--border); }}
.topbar .stats {{ display: flex; gap: 6px; font-size: 0.78em; }}
.topbar .stat {{ padding: 3px 10px; border-radius: 20px; font-weight: 600; }}
.stat-u {{ background: #fef3c7; color: #92400e; }}
.stat-a {{ background: #dbeafe; color: #1e40af; }}
[data-theme="dark"] .stat-u {{ background: #422006; color: #fbbf24; }}
[data-theme="dark"] .stat-a {{ background: #1e3a5f; color: #93c5fd; }}

/* Layout */
.layout {{ display: flex; }}
.sidebar {{ width: var(--sidebar-w); border-right: 1px solid var(--border); padding: 20px 16px; position: sticky; top: 57px; height: calc(100vh - 57px); overflow-y: auto; flex-shrink: 0; }}
.sidebar h4 {{ font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 16px 0 6px; }}
.sidebar h4:first-child {{ margin-top: 0; }}
.sidebar ul {{ list-style: none; }}
.sidebar li {{ margin: 2px 0; }}
.sidebar a {{ color: var(--text); text-decoration: none; font-size: 0.83em; display: flex; justify-content: space-between; padding: 4px 8px; border-radius: 4px; }}
.sidebar a:hover {{ background: var(--border); }}
.sidebar .count {{ color: var(--muted); font-size: 0.8em; }}
.sidebar .filter-row {{ display: flex; gap: 4px; margin-bottom: 12px; }}
.sidebar .filter-chip {{ font-size: 0.75em; padding: 3px 8px; border-radius: 12px; border: 1px solid var(--border); cursor: pointer; background: none; color: var(--text); }}
.sidebar .filter-chip.active {{ background: var(--text); color: var(--bg); }}

/* Main */
.main {{ flex: 1; padding: 24px 32px; max-width: 860px; }}
.scene {{ margin-bottom: 40px; }}
.scene h3 {{ font-size: 1em; font-weight: 600; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }}

/* Point card — collapsed by default */
.point {{ border-radius: 8px; margin-bottom: 6px; overflow: hidden; border-left: 3px solid var(--ai-stripe); background: var(--card); }}
.point.user {{ border-left-color: var(--user-stripe); }}
.point-summary {{ display: grid; grid-template-columns: auto 1fr auto; grid-template-rows: auto auto; gap: 2px 12px; padding: 10px 14px; cursor: pointer; align-items: center; user-select: none; }}
.point-summary:hover {{ background: rgba(0,0,0,0.02); }}
.point-left {{ grid-column: 1; grid-row: 1 / 3; display: flex; gap: 4px; align-items: center; flex-wrap: wrap; white-space: nowrap; }}
.point-quote {{ grid-column: 2; grid-row: 1; font-style: italic; font-size: 0.95em; color: var(--text); white-space: normal; overflow: visible; word-break: break-word; }}
.point-hint {{ grid-column: 2; grid-row: 2; font-size: 0.78em; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.expand-icon {{ grid-column: 3; grid-row: 1 / 3; font-size: 0.7em; color: var(--muted); transition: transform 0.15s; }}
.point.open .expand-icon {{ transform: rotate(90deg); }}
.point-actions {{ grid-column: 3; grid-row: 1 / 3; display: flex; align-items: center; gap: 6px; }}
.btn-record {{ background: none; border: 1px solid var(--border); border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 0.8em; color: var(--text); text-decoration: none; flex-shrink: 0; transition: all 0.2s; }}
.btn-record:hover {{ background: var(--border); }}
.btn-record.recording {{ background: #fef2f2; border-color: #ef4444; color: #ef4444; animation: pulse 0.8s infinite; }}
.btn-record.has-recording {{ background: #ecfdf5; border-color: #10b981; color: #10b981; }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.5}} }}
.detail-links {{ margin-top: 10px; font-size: 0.82em; }}
.detail-links a {{ color: var(--accent); }}
.video-container {{ margin-top: 12px; }}
.video-wrapper {{ position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; border-radius: 8px; }}
.video-wrapper iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; }}
.video-caption {{ font-size: 0.8em; color: var(--muted); margin-top: 4px; }}
.video-placeholder, .video-fallback {{ font-size: 0.82em; color: var(--muted); padding: 12px; text-align: center; background: var(--border); border-radius: 6px; }}
.video-fallback a {{ color: var(--accent); }}

/* Badge & tags */
.badge {{ font-size: 0.68em; font-weight: 700; padding: 2px 7px; border-radius: 3px; text-transform: uppercase; letter-spacing: 0.03em; }}
.badge-user {{ background: #fef3c7; color: #b45309; }}
.badge-ai {{ background: #dbeafe; color: #1d4ed8; }}
.cat {{ font-size: 0.75em; color: var(--muted); }}
.freq {{ font-size: 0.65em; padding: 1px 5px; border-radius: 3px; font-weight: 700; text-transform: uppercase; }}
.freq-high {{ color: #dc2626; }}
.freq-medium {{ color: #d97706; }}
.freq-low {{ color: var(--muted); }}

/* Detail — hidden by default */
.point .point-detail {{ display: none; padding: 0 14px 12px; font-size: 0.88em; border-top: 1px solid var(--border); margin: 0 14px; }}
.point.open .point-detail {{ display: block; }}
.point.open .point-summary {{ background: rgba(0,0,0,0.03); }}
.detail-context {{ color: var(--muted); font-size: 0.85em; margin: 8px 0; }}
.detail-explanation {{ margin: 8px 0; line-height: 1.7; }}
.examples {{ margin: 8px 0; }}
.examples ul {{ margin: 4px 0 0 18px; }}
.examples li {{ margin: 2px 0; font-style: italic; }}
.label {{ font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-weight: 600; }}
.related {{ margin: 8px 0; }}
.tag {{ display: inline-block; border: 1px solid var(--border); border-radius: 12px; padding: 1px 8px; margin: 2px 3px 2px 0; font-size: 0.82em; }}
.detail-meta {{ color: var(--muted); font-size: 0.8em; margin-top: 6px; }}

.hidden {{ display: none !important; }}

@media (max-width: 768px) {{
    .layout {{ flex-direction: column; }}
    .sidebar {{ width: 100%; height: auto; position: static; border-right: none; border-bottom: 1px solid var(--border); }}
    .main {{ padding: 16px; }}
    .topbar {{ padding: 10px 14px; gap: 8px; }}
    .topbar h1 {{ font-size: 1em; }}
    .topbar input {{ width: 120px; }}
    .sidebar {{ display: none; }}
}}

/* ===== Review Mode ===== */
.review-progress {{ font-size: 0.75em; color: var(--muted); white-space: nowrap; }}
#reviewBtn {{ background: var(--accent); color: #fff; border: none; font-weight: 600; padding: 7px 16px; position: relative; }}
#reviewBtn:hover {{ opacity: 0.85; }}
#reviewBtn .due-badge {{ position: absolute; top: -6px; right: -6px; background: #dc2626; color: #fff; font-size: 0.65em; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }}

/* Sidebar review stats */
.review-stats {{ margin-bottom: 8px; }}
.rs-row {{ display: flex; justify-content: space-between; font-size: 0.78em; padding: 3px 0; color: var(--muted); }}
.rs-val {{ font-weight: 600; color: var(--text); }}

/* Review overlay */
.review-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 100; backdrop-filter: blur(4px); }}
.review-overlay.active {{ display: flex; align-items: center; justify-content: center; }}
.review-container {{ width: 100%; max-width: 600px; padding: 20px; display: flex; flex-direction: column; gap: 12px; }}
.review-topbar {{ display: flex; align-items: center; gap: 12px; }}
.review-close {{ cursor: pointer; font-size: 1.2em; color: #fff; padding: 4px 8px; border-radius: 4px; }}
.review-close:hover {{ background: rgba(255,255,255,0.15); }}
.review-progress-bar {{ flex: 1; height: 4px; background: rgba(255,255,255,0.2); border-radius: 2px; overflow: hidden; }}
.review-progress-fill {{ height: 100%; background: #4ade80; border-radius: 2px; transition: width 0.2s; }}
.review-counter {{ font-size: 0.82em; color: #fff; font-weight: 600; white-space: nowrap; }}

/* Flashcard */
.review-card {{ perspective: 1000px; cursor: pointer; }}
.review-card-inner {{ position: relative; width: 100%; min-height: 220px; transition: transform 0.4s; transform-style: preserve-3d; }}
.review-card-inner.flipped {{ transform: rotateY(180deg); }}
.review-card-front, .review-card-back {{ position: absolute; inset: 0; backface-visibility: hidden; border-radius: 12px; padding: 24px; display: flex; flex-direction: column; justify-content: center; align-items: center; }}
.review-card-front {{ background: #fff; color: #222; text-align: center; gap: 16px; z-index: 2; }}
[data-theme="dark"] .review-card-front {{ background: #2a2a2a; color: #ddd; }}
.review-card-back {{ background: #fff; color: #222; transform: rotateY(180deg); overflow-y: auto; gap: 10px; font-size: 0.88em; line-height: 1.6; padding: 20px 24px; }}
[data-theme="dark"] .review-card-back {{ background: #2a2a2a; color: #ddd; }}
.rcf-badges {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; }}
.rcf-badges .badge {{ font-size: 0.75em; }}
.rcf-quote {{ font-size: 1.3em; font-style: italic; font-weight: 500; line-height: 1.5; max-width: 480px; }}
.rcf-tap {{ font-size: 0.75em; color: #999; margin-top: 8px; }}
.rcb-context {{ color: #888; font-size: 0.85em; font-style: italic; }}
.rcb-explanation {{ line-height: 1.7; }}
.rcb-examples {{ margin-top: 6px; }}
.rcb-examples ul {{ margin: 4px 0 0 18px; }}
.rcb-examples li {{ margin: 2px 0; font-style: italic; }}
.rcb-related {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }}

/* Rating buttons */
.review-actions {{ display: none; gap: 8px; justify-content: center; flex-wrap: wrap; }}
.review-actions.visible {{ display: flex; }}
.ra-btn {{ padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-size: 0.9em; font-weight: 600; color: #fff; transition: transform 0.1s; }}
.ra-btn:active {{ transform: scale(0.95); }}
.ra-again {{ background: #dc2626; }}
.ra-hard {{ background: #d97706; }}
.ra-good {{ background: #2563eb; }}
.ra-easy {{ background: #16a34a; }}
.review-nav {{ display: flex; justify-content: space-between; align-items: center; }}
.ra-nav {{ background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.82em; }}
.ra-nav:hover {{ background: rgba(255,255,255,0.2); }}
.review-due-info {{ font-size: 0.75em; color: rgba(255,255,255,0.5); }}
.review-shortcuts {{ display: flex; gap: 16px; justify-content: center; font-size: 0.68em; color: rgba(255,255,255,0.3); }}
.review-done {{ text-align: center; color: #fff; }}
.review-done h2 {{ font-size: 1.5em; margin-bottom: 8px; }}
.review-done p {{ color: rgba(255,255,255,0.6); font-size: 0.9em; }}
</style>
</head>
<body>
<div class="topbar">
    <h1>{review.episode_label}</h1>
    <span class="ep">{review.episode_title}</span>
    <span class="spacer"></span>
    <span class="stats">
        <span class="stat stat-u">Your notes {total_user}</span>
        <span class="stat stat-a">AI found {total_ai}</span>
    </span>
    <span class="review-progress" id="reviewProgress" title="Review progress"></span>
    <button id="reviewBtn" onclick="startReview()" title="Start flashcard review">🎯 Review</button>
    <input type="text" id="search" placeholder="Filter..." oninput="filter()">
    <a href="index.html" class="btn">← Index</a>
    <button onclick="toggleTheme()" id="themeBtn">Dark</button>
</div>

<div class="layout">
<nav class="sidebar">
    <div class="filter-row">
        <button class="filter-chip active" onclick="filterBy('all', this)">All</button>
        <button class="filter-chip" onclick="filterBy('user', this)">Notes</button>
        <button class="filter-chip" onclick="filterBy('ai', this)">AI</button>
    </div>
    <h4>📊 Review Stats</h4>
    <div class="review-stats" id="reviewStats">
        <div class="rs-row"><span>Mastered</span><span class="rs-val" id="rsMastered">-</span></div>
        <div class="rs-row"><span>Learning</span><span class="rs-val" id="rsLearning">-</span></div>
        <div class="rs-row"><span>Due today</span><span class="rs-val" id="rsDue">-</span></div>
        <div class="rs-row"><span>Streak</span><span class="rs-val" id="rsStreak">-</span></div>
    </div>
    <h4>Scenes</h4>
    <ul>{"".join(toc_items)}</ul>
</nav>

<main class="main">
    {"".join(scene_sections) if scene_sections else '<p style="color:var(--muted);text-align:center;padding:60px;">No content yet</p>'}
</main>
</div>

<!-- ===== Review Overlay ===== -->
<div class="review-overlay" id="reviewOverlay">
    <div class="review-container">
        <div class="review-topbar">
            <span class="review-close" onclick="exitReview()" title="Exit review (Esc)">✕</span>
            <div class="review-progress-bar">
                <div class="review-progress-fill" id="reviewProgressFill"></div>
            </div>
            <span class="review-counter" id="reviewCounter">0/0</span>
        </div>
        <div class="review-card" id="reviewCard" onclick="flipCard()">
            <div class="review-card-inner" id="reviewCardInner">
                <div class="review-card-front">
                    <div class="rcf-badges" id="rcfBadges"></div>
                    <div class="rcf-quote" id="rcfQuote"></div>
                    <div class="rcf-tap">👆 Tap to reveal</div>
                </div>
                <div class="review-card-back">
                    <div class="rcb-context" id="rcbContext"></div>
                    <div class="rcb-explanation" id="rcbExplanation"></div>
                    <div class="rcb-examples" id="rcbExamples"></div>
                    <div class="rcb-related" id="rcbRelated"></div>
                </div>
            </div>
        </div>
        <div class="review-actions" id="reviewActions">
            <button class="ra-btn ra-again" onclick="rateCard(0)" title="Again (key: 1)">🔁 Again</button>
            <button class="ra-btn ra-hard" onclick="rateCard(1)" title="Hard (key: 2)">😐 Hard</button>
            <button class="ra-btn ra-good" onclick="rateCard(2)" title="Good (key: 3)">😊 Good</button>
            <button class="ra-btn ra-easy" onclick="rateCard(3)" title="Easy (key: 4)">😎 Easy</button>
        </div>
        <div class="review-nav">
            <button class="ra-nav" onclick="prevCard()">← Previous</button>
            <span class="review-due-info" id="reviewDueInfo"></span>
            <button class="ra-nav" onclick="nextCard()">Next →</button>
        </div>
        <div class="review-shortcuts">
            <span>Space: flip</span><span>1-4: rate</span><span>←→: nav</span><span>Esc: exit</span>
        </div>
    </div>
</div>

<script>
function togglePoint(summary) {{
    const point = summary.parentElement;
    const wasOpen = point.classList.contains('open');
    point.classList.toggle('open');

    // Load video on first expand
    if (!wasOpen && point.classList.contains('open')) {{
        const videoDiv = point.querySelector('.video-container');
        if (videoDiv && videoDiv.dataset.loaded === '0') {{
            loadVideo(videoDiv, point.dataset.ytquery);
        }}
    }}
}}

async function loadVideo(container, query) {{
    if (!query) return;
    container.dataset.loaded = '1';
    container.innerHTML = '<div class="video-placeholder">Searching video...</div>';

    try {{
        const resp = await fetch('/api/youtube?q=' + encodeURIComponent(query));
        const data = await resp.json();
        if (data.videoId) {{
            container.innerHTML = `
                <div class="video-wrapper">
                    <iframe src="${{data.embedUrl}}"
                            frameborder="0"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowfullscreen></iframe>
                    <div class="video-caption">${{data.title}}</div>
                </div>`;
        }} else {{
            container.innerHTML = `
                <div class="video-fallback">
                    No clip found — <a href="https://www.youtube.com/results?search_query=${{encodeURIComponent(query)}}" target="_blank">search YouTube</a>
                </div>`;
        }}
    }} catch (e) {{
        container.innerHTML = `
            <div class="video-fallback">
                <a href="https://www.youtube.com/results?search_query=${{encodeURIComponent(query)}}" target="_blank">🔗 Search on YouTube</a>
            </div>`;
    }}
}}

// ---- Voice Recording ----
const recordingState = {{}};  // key: quote text -> {{ blob, url }}

async function toggleRecord(btn) {{
    const point = btn.closest('.point');
    const text = point ? point.dataset.quote : '';
    if (!text) return;

    // If currently recording, stop
    if (btn.classList.contains('recording')) {{
        stopRecording(btn, text);
        return;
    }}

    // If has existing recording
    if (recordingState[text]) {{
        const now = Date.now();
        // Double-click detection: if last click was within 600ms -> re-record
        if (btn._lastClick && (now - btn._lastClick) < 600) {{
            clearRecording(btn, text);
            startRecording(btn, text);
            return;
        }}
        btn._lastClick = now;
        playRecording(btn, text);
        return;
    }}

    // Start recording
    startRecording(btn, text);
}}

async function startRecording(btn, text) {{
    // Stop any playing audio
    if (btn._audio) {{ btn._audio.pause(); btn._audio = null; }}
    try {{
        const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus' : 'audio/webm';
        const mediaRecorder = new MediaRecorder(stream, {{ mimeType }});
        const chunks = [];

        mediaRecorder.ondataavailable = e => chunks.push(e.data);
        mediaRecorder.onstop = () => {{
            const blob = new Blob(chunks, {{ type: mimeType }});
            const url = URL.createObjectURL(blob);
            // Revoke old URL to free memory
            if (recordingState[text]) URL.revokeObjectURL(recordingState[text].url);
            recordingState[text] = {{ blob, url }};
            btn.classList.remove('recording');
            btn.classList.add('has-recording');
            btn.title = '▶️ Play · Double-click to re-record';
            btn.textContent = '▶️';
            stream.getTracks().forEach(t => t.stop());
        }};

        btn._recorder = mediaRecorder;
        btn._stream = stream;
        mediaRecorder.start();
        btn.classList.add('recording');
        btn.classList.remove('has-recording');
        btn.textContent = '⏺️';
        btn.title = 'Recording... click to stop';

        // Auto-stop after 30 seconds
        setTimeout(() => {{
            if (btn.classList.contains('recording')) stopRecording(btn, text);
        }}, 30000);
    }} catch (e) {{
        console.log('Microphone unavailable:', e.message);
        alert('🎤 Microphone access needed. Please allow microphone permissions in browser settings.');
    }}
}}

function stopRecording(btn, text) {{
    if (btn._recorder && btn._recorder.state === 'recording') {{
        btn._recorder.stop();
    }}
}}

function clearRecording(btn, text) {{
    if (recordingState[text]) {{
        URL.revokeObjectURL(recordingState[text].url);
        delete recordingState[text];
    }}
    btn.classList.remove('has-recording', 'playing');
    btn.textContent = '🎤';
    btn.title = 'Record your voice';
    btn._lastClick = null;
    if (btn._audio) {{ btn._audio.pause(); btn._audio = null; }}
}}

function playRecording(btn, text) {{
    const data = recordingState[text];
    if (!data) return;
    const audio = new Audio(data.url);
    btn._audio = audio;
    btn.textContent = '⏸️';
    btn.classList.add('playing');
    audio.onended = () => {{
        btn.textContent = '▶️';
        btn.classList.remove('playing');
        btn._audio = null;
    }};
    audio.onerror = () => {{
        clearRecording(btn, text);
    }};
    audio.play();
}}


function filterBy(type, btn) {{
    document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.point').forEach(p => {{
        if (type === 'all') p.classList.remove('hidden');
        else if (type === 'user') p.classList.toggle('hidden', !p.classList.contains('user'));
        else p.classList.toggle('hidden', !p.classList.contains('ai'));
    }});
    document.querySelectorAll('.scene').forEach(s => {{
        const visible = s.querySelectorAll('.point:not(.hidden)');
        s.classList.toggle('hidden', visible.length === 0);
    }});
}}

function filter() {{
    const q = document.getElementById('search').value.toLowerCase();
    document.querySelectorAll('.point').forEach(p => {{
        if (!q) {{ p.classList.remove('hidden'); return; }}
        p.classList.toggle('hidden', !p.textContent.toLowerCase().includes(q));
    }});
    document.querySelectorAll('.scene').forEach(s => {{
        const visible = s.querySelectorAll('.point:not(.hidden)');
        s.classList.toggle('hidden', visible.length === 0);
    }});
}}

function toggleTheme() {{
    const h = document.documentElement;
    const b = document.getElementById('themeBtn');
    if (h.getAttribute('data-theme') === 'dark') {{
        h.removeAttribute('data-theme'); b.textContent = 'Dark';
    }} else {{
        h.setAttribute('data-theme', 'dark'); b.textContent = 'Light';
    }}
    localStorage.setItem('theme', h.getAttribute('data-theme')||'light');
}}
(function(){{
    if (localStorage.getItem('theme')==='dark'){{
        document.documentElement.setAttribute('data-theme','dark');
        document.getElementById('themeBtn').textContent='Light';
    }}
}})();

// ===== Review Mode =====
const TOTAL_POINTS = {point_index};
const EPISODE = '{review.episode_label}';
const STORAGE_KEY = 'mf_review_' + EPISODE;
let reviewQueue = [];
let reviewIdx = 0;
let reviewFlipped = false;

// ---- SM-2 Algorithm ----
function sm2(ease, interval, rating) {{
    // rating: 0=Again, 1=Hard, 2=Good, 3=Easy
    if (rating === 0) {{ interval = 1; ease = Math.max(1.3, ease - 0.20); }}
    else if (rating === 1) {{ interval = Math.max(1, interval * 1.2); ease = Math.max(1.3, ease - 0.15); }}
    else if (rating === 2) {{ interval = Math.max(1, interval * ease); }}
    else {{ interval = Math.max(1, interval * ease * 1.3); ease = Math.min(3.0, ease + 0.15); }}
    return {{ ease: Math.round(ease * 100) / 100, interval: Math.round(interval) }};
}}

function todayStr() {{ return new Date().toISOString().slice(0,10); }}

// ---- Data ----
function loadData() {{
    try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {{ stats: {{}}, points: {{}} }}; }}
    catch(e) {{ return {{ stats: {{}}, points: {{}} }}; }}
}}

function saveData(d) {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(d)); }}

// ---- Stats helpers ----
function getMasteredCount(d) {{
    return Object.values(d.points).filter(p => p.interval >= 21).length;
}}

function getLearningCount(d) {{
    return Object.values(d.points).filter(p => p.reviews > 0 && p.interval < 21).length;
}}

function getDueCount(d) {{
    const today = todayStr();
    let count = 0;
    for (let i = 0; i < TOTAL_POINTS; i++) {{
        const p = d.points[i];
        if (!p || !p.nextReview || p.nextReview <= today) count++;
    }}
    return count;
}}

function updateStats() {{
    const d = loadData();
    const mastered = getMasteredCount(d);
    const learning = getLearningCount(d);
    const due = getDueCount(d);
    const streak = d.stats && d.stats.streak ? d.stats.streak : 0;
    const totalReviewed = Object.values(d.points).filter(p => p.reviews > 0).length;

    document.getElementById('rsMastered').textContent = mastered;
    document.getElementById('rsLearning').textContent = learning;
    document.getElementById('rsDue').textContent = due;
    document.getElementById('rsStreak').textContent = streak + 'd';
    document.getElementById('reviewProgress').textContent = totalReviewed + '/' + TOTAL_POINTS + ' reviewed';

    // Due badge on review button
    const badge = document.getElementById('reviewBtn').querySelector('.due-badge');
    if (due > 0) {{
        if (!badge) {{
            const b = document.createElement('span');
            b.className = 'due-badge';
            b.textContent = due;
            document.getElementById('reviewBtn').appendChild(b);
        }} else badge.textContent = due;
    }} else if (badge) badge.remove();
}}

// ---- Review Logic ----
function startReview() {{
    const d = loadData();
    const today = todayStr();

    // Collect all point indices, sort by: unreviewed first, then overdue first
    const allIndices = Array.from({{length: TOTAL_POINTS}}, (_,i) => i);
    reviewQueue = allIndices.sort((a,b) => {{
        const pa = d.points[a], pb = d.points[b];
        const aNew = !pa || !pa.reviews ? 0 : 1;
        const bNew = !pb || !pb.reviews ? 0 : 1;
        if (aNew !== bNew) return aNew - bNew; // new cards first
        const aDue = pa && pa.nextReview ? pa.nextReview : '0000';
        const bDue = pb && pb.nextReview ? pb.nextReview : '0000';
        return aDue.localeCompare(bDue);
    }});

    if (reviewQueue.length === 0) {{ alert('No points to review!'); return; }}

    reviewIdx = 0;
    document.getElementById('reviewOverlay').classList.add('active');
    document.body.style.overflow = 'hidden';
    showCard();
}}

function showCard() {{
    if (reviewIdx >= reviewQueue.length) {{
        finishReview();
        return;
    }}
    const idx = reviewQueue[reviewIdx];
    const el = document.querySelector('.point[data-index="' + idx + '"]');
    if (!el) {{ nextCard(); return; }}

    let point;
    try {{ point = JSON.parse(el.dataset.point.replace(/&#39;/g, "'")); }}
    catch(e) {{ point = {{ quote: el.dataset.quote, category: 'phrase', frequency: 'medium', context: '', explanation: '', examples: [], related: [], formality: '', source: 'ai' }}; }}

    // Front
    const icon = ({{phrase:'💬',vocabulary:'📖',grammar:'📐',culture:'🇺🇸',pronunciation:'🔊',pragmatics:'🎭'}})[point.category] || '💡';
    document.getElementById('rcfBadges').innerHTML = `
        <span class="badge badge-${{point.source === 'user' ? 'user' : 'ai'}}">${{point.source === 'user' ? 'Your note' : 'AI found'}}</span>
        <span class="cat">${{icon}} ${{point.category}}</span>
        <span class="freq freq-${{point.frequency}}">${{point.frequency}}</span>
    `;
    document.getElementById('rcfQuote').textContent = '"' + point.quote + '"';

    // Back
    document.getElementById('rcbContext').textContent = point.context || '';
    document.getElementById('rcbExplanation').textContent = point.explanation || '';
    let exHtml = '';
    if (point.examples && point.examples.length) {{
        exHtml = '<div class="rcb-examples"><span class="label">Examples</span><ul>';
        point.examples.forEach(e => exHtml += '<li>' + e + '</li>');
        exHtml += '</ul></div>';
    }}
    document.getElementById('rcbExamples').innerHTML = exHtml;
    let relHtml = '';
    if (point.related && point.related.length) {{
        relHtml = '<div class="rcb-related"><span class="label">See also</span> ';
        point.related.forEach(r => relHtml += '<span class="tag">' + r + '</span>');
        relHtml += '</div>';
    }}
    document.getElementById('rcbRelated').innerHTML = relHtml;

    // Reset state
    reviewFlipped = false;
    document.getElementById('reviewCardInner').classList.remove('flipped');
    document.getElementById('reviewActions').classList.remove('visible');
    document.getElementById('reviewDueInfo').textContent = '';

    // Progress
    document.getElementById('reviewCounter').textContent = (reviewIdx + 1) + '/' + reviewQueue.length;
    const pct = ((reviewIdx) / reviewQueue.length * 100).toFixed(0);
    document.getElementById('reviewProgressFill').style.width = pct + '%';
}}

function flipCard() {{
    reviewFlipped = !reviewFlipped;
    document.getElementById('reviewCardInner').classList.toggle('flipped', reviewFlipped);
    document.getElementById('reviewActions').classList.toggle('visible', reviewFlipped);
}}

function rateCard(rating) {{
    if (!reviewFlipped) {{ flipCard(); setTimeout(() => rateCard(rating), 450); return; }}

    const idx = reviewQueue[reviewIdx];
    const d = loadData();
    const today = todayStr();

    // Update streak
    if (!d.stats) d.stats = {{}};
    const lastDate = d.stats.lastReviewDate || '';
    if (lastDate === today) {{ /* same day, no streak change */ }}
    else if (lastDate === yesterdayStr()) {{ d.stats.streak = (d.stats.streak || 0) + 1; }}
    else {{ d.stats.streak = 1; }}
    d.stats.lastReviewDate = today;
    d.stats.totalReviews = (d.stats.totalReviews || 0) + 1;

    // Update point
    if (!d.points[idx]) d.points[idx] = {{ reviews: 0, ease: 2.5, interval: 1, nextReview: today, history: [] }};
    const p = d.points[idx];
    const result = sm2(p.ease || 2.5, p.interval || 1, rating);
    p.ease = result.ease;
    p.interval = result.interval;
    p.reviews = (p.reviews || 0) + 1;
    p.lastReview = today;
    p.nextReview = addDays(today, result.interval);
    const labels = ['again','hard','good','easy'];
    p.history = (p.history || []).concat([labels[rating]]).slice(-10);

    saveData(d);
    updateStats();

    // Show due info
    const dueDate = p.nextReview;
    document.getElementById('reviewDueInfo').textContent = 'Next review: ' + formatDate(dueDate) + ' (' + p.interval + 'd)';

    // Auto-advance after short delay
    setTimeout(() => nextCard(), 600);
}}

function nextCard() {{
    if (reviewIdx < reviewQueue.length - 1) {{
        reviewIdx++;
        showCard();
    }} else {{
        finishReview();
    }}
}}

function prevCard() {{
    if (reviewIdx > 0) {{
        reviewIdx--;
        showCard();
    }}
}}

function exitReview() {{
    document.getElementById('reviewOverlay').classList.remove('active');
    document.body.style.overflow = '';
    updateStats();
}}

function finishReview() {{
    const d = loadData();
    const mastered = getMasteredCount(d);
    const due = getDueCount(d);
    const today = todayStr();
    document.getElementById('reviewCard').innerHTML = `
        <div class="review-done">
            <h2>🎉 Session complete!</h2>
            <p>Mastered: ${{mastered}} | Due today: ${{due}}</p>
            <p style="margin-top:12px">${{due === 0 ? 'All caught up! 🎯' : due + ' cards still due — keep going!'}}</p>
            <button class="ra-nav" onclick="exitReview()" style="margin-top:16px">Back to browse</button>
        </div>`;
    document.getElementById('reviewActions').classList.remove('visible');
    document.getElementById('reviewCounter').textContent = reviewQueue.length + '/' + reviewQueue.length;
    document.getElementById('reviewProgressFill').style.width = '100%';
    updateStats();
}}

// ---- Helpers ----
function yesterdayStr() {{
    const d = new Date(); d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0,10);
}}

function addDays(dateStr, days) {{
    const d = new Date(dateStr + 'T00:00:00');
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0,10);
}}

function formatDate(dateStr) {{
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }});
}}

// ---- Keyboard shortcuts ----
document.addEventListener('keydown', function(e) {{
    const overlay = document.getElementById('reviewOverlay');
    if (!overlay.classList.contains('active')) return;
    // Don't capture when typing in input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch(e.key) {{
        case ' ': e.preventDefault(); flipCard(); break;
        case '1': case 'a': rateCard(0); break;
        case '2': case 'h': rateCard(1); break;
        case '3': case 'g': rateCard(2); break;
        case '4': case 'e': rateCard(3); break;
        case 'ArrowLeft': prevCard(); break;
        case 'ArrowRight': nextCard(); break;
        case 'Escape': exitReview(); break;
    }}
}});

// ---- Init ----
updateStats();
</script>
<script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('/sw.js');}}</script>
</body>
</html>'''
    return html


def build_index_html(episodes: list[EpisodeReview], all_episodes_info: dict = None) -> str:
    """Build the index page.

    Args:
        episodes: list of processed EpisodeReview objects
        all_episodes_info: optional dict from StateManager.get_all_episodes(),
            mapping pdf_name -> {total, processed, unprocessed, titles}
    """
    import re as _re

    # Build lookup of processed episode data from reviews
    processed_map = {}
    for ep in episodes:
        u = sum(1 for s in ep.scenes for p in s["points"] if p.source == "user_annotation")
        a = sum(1 for s in ep.scenes for p in s["points"] if p.source == "ai_discovery")
        processed_map[ep.episode_label.upper()] = {
            "title": ep.episode_title,
            "notes": u,
            "ai": a,
        }

    # Use all_episodes_info as the single source for episode list
    total_from_pdf = 0
    all_labels = set()
    if all_episodes_info:
        for _pdf_name, info in all_episodes_info.items():
            total_from_pdf += info.get("total", 0)
            titles = info.get("titles", {})
            # Collect all episode labels from processed + unprocessed lists
            for label in info.get("processed", []):
                if label and _re.match(r'S\d+E\d+', label, _re.IGNORECASE):
                    all_labels.add(label.upper())
            for label in info.get("unprocessed", []):
                if label and _re.match(r'S\d+E\d+', label, _re.IGNORECASE):
                    all_labels.add(label.upper())
            # Also add from titles if not already covered
            for label, title in titles.items():
                if label and _re.match(r'S\d+E\d+', label, _re.IGNORECASE):
                    all_labels.add(label.upper())
                # Merge title into processed_map if not already present
                upper = label.upper()
                if upper not in processed_map and title:
                    processed_map[upper] = {"title": title, "notes": 0, "ai": 0}

    # If no all_episodes_info, fall back to reviews only
    if not all_labels:
        all_labels = set(processed_map.keys())

    def sort_key(label):
        m = _re.match(r'S(\d+)E(\d+)', label, _re.IGNORECASE)
        if m:
            return (int(m.group(1)), int(m.group(2)))
        return (99, 0)

    sorted_labels = sorted(all_labels, key=sort_key)

    # Build cards
    processed_count = 0
    cards = []
    for label in sorted_labels:
        info = processed_map.get(label, {})
        title = info.get("title", "")
        notes = info.get("notes", 0)
        ai = info.get("ai", 0)
        is_processed = notes > 0 or ai > 0

        if is_processed:
            processed_count += 1
            cards.append(f'''
        <a href="{label.lower()}.html" class="ep-card ep-done">
            <span class="ep-label">{label}</span>
            <span class="ep-title">{title}</span>
            <span class="ep-nums"><span class="n-u">Notes {notes}</span> <span class="n-a">AI {ai}</span></span>
            <span class="ep-review-stat" data-ep="{label}"></span>
        </a>''')
        else:
            cards.append(f'''
        <div class="ep-card ep-pending">
            <span class="ep-label ep-label-off">{label}</span>
            <span class="ep-title">{title or 'Episode ' + label[4:]}</span>
            <span class="ep-nums"><span class="n-pending">待处理</span></span>
        </div>''')

    total_episodes = total_from_pdf or processed_count
    pct = round(processed_count / total_episodes * 100) if total_episodes else 0

    # Build progress bar HTML
    progress_html = ""
    if total_episodes > 1:
        progress_html = f'''
    <div class="progress-wrap">
        <div class="progress-bar"><div class="progress-fill" style="width:{pct}%"></div></div>
        <span class="progress-text">{processed_count}/{total_episodes} episodes · {pct}%</span>
    </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#2563eb">
<link rel="manifest" href="/manifest.json">
<title>Modern Family · Speaking Review</title>
<style>
:root{{--bg:#fff;--text:#222;--muted:#888;--border:#eee;--card:#fafafa;--accent:#2563eb;--done-bg:#f0f7ff;}}
[data-theme="dark"]{{--bg:#1a1a1a;--text:#ddd;--muted:#999;--border:#333;--card:#252525;--accent:#60a5fa;--done-bg:#1a2a3a;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;}}
.top{{text-align:center;padding:48px 20px 24px;}}
.top h1{{font-size:1.6em;margin-bottom:6px;}}
.top p{{color:var(--muted);font-size:0.95em;}}
.top button{{margin-top:12px;background:var(--card);border:1px solid var(--border);border-radius:6px;padding:6px 16px;cursor:pointer;font-size:0.85em;color:var(--text);}}
.progress-wrap{{max-width:640px;margin:0 auto 8px;padding:0 20px;display:flex;align-items:center;gap:12px;}}
.progress-bar{{flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden;}}
.progress-fill{{height:100%;background:var(--accent);border-radius:3px;transition:width 0.3s;}}
.progress-text{{font-size:0.8em;color:var(--muted);white-space:nowrap;}}
.grid{{max-width:640px;margin:0 auto;padding:8px 20px 40px;display:flex;flex-direction:column;gap:8px;}}
.ep-card{{display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:8px;border:1px solid var(--border);text-decoration:none;color:var(--text);background:var(--card);flex-wrap:wrap;}}
.ep-card.ep-done:hover{{border-color:var(--accent);background:var(--done-bg);}}
.ep-card.ep-pending{{opacity:0.55;pointer-events:none;}}
.ep-label{{font-weight:700;font-size:0.95em;background:var(--text);color:var(--bg);padding:3px 10px;border-radius:4px;}}
.ep-label-off{{background:var(--border);color:var(--muted);}}
.ep-title{{font-size:0.9em;color:var(--muted);flex:1;}}
.ep-nums{{font-size:0.8em;display:flex;gap:8px;}}
.n-u{{color:#b45309;font-weight:600;}}
.n-a{{color:#1d4ed8;font-weight:600;}}
.n-pending{{color:var(--muted);font-style:italic;}}
.ep-review-stat{{font-size:0.75em;color:var(--accent);min-width:50px;text-align:right;}}
.empty{{text-align:center;padding:64px;color:var(--muted);}}
.stats-row{{max-width:640px;margin:0 auto 16px;padding:0 20px;display:flex;gap:12px;flex-wrap:wrap;justify-content:center;}}
.stat-chip{{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:6px 16px;font-size:0.85em;}}
.stat-chip .val{{font-weight:700;color:var(--accent);}}
</style>
</head>
<body>
<div class="top">
    <h1>Modern Family · Speaking Review</h1>
    <p>Your notes + AI discoveries from each episode</p>
    <button onclick="toggleTheme()" id="themeBtn">Dark</button>
</div>
{progress_html}
<div class="stats-row" id="reviewSummary"></div>
<div class="grid">
    {"".join(cards) if cards else '<div class="empty">No episodes processed yet<br><small>Run: python cli.py process-all</small></div>'}
</div>
<script>
function toggleTheme(){{
    const h=document.documentElement,b=document.getElementById('themeBtn');
    if(h.getAttribute('data-theme')==='dark'){{h.removeAttribute('data-theme');b.textContent='Dark';}}
    else{{h.setAttribute('data-theme','dark');b.textContent='Light';}}
    localStorage.setItem('theme',h.getAttribute('data-theme')||'light');
}}
(function(){{if(localStorage.getItem('theme')==='dark'){{document.documentElement.setAttribute('data-theme','dark');document.getElementById('themeBtn').textContent='Light';}}}})();

// Show review stats from localStorage for each episode
(function(){{
    const stats = document.querySelectorAll('.ep-review-stat');
    let totalReviewed = 0, totalMastered = 0;
    stats.forEach(el => {{
        const ep = el.dataset.ep;
        const key = 'mf_review_' + ep;
        try {{
            const data = JSON.parse(localStorage.getItem(key));
            if (data && data.stats) {{
                const pts = data.points || {{}};
                const vals = Object.values(pts);
                const reviewed = vals.length;
                const mastered = vals.filter(p => (p.ease||0) >= 2.7 && (p.interval||0) >= 21).length;
                totalReviewed += reviewed;
                totalMastered += mastered;
                if (reviewed > 0) {{
                    el.textContent = '📝' + reviewed;
                    if (mastered > 0) el.textContent += ' ⭐' + mastered;
                }}
            }}
        }} catch(e) {{}}
    }});
    const row = document.getElementById('reviewSummary');
    if (totalReviewed > 0) {{
        row.innerHTML =
            '<div class="stat-chip">📝 Reviewed: <span class="val">' + totalReviewed + '</span></div>' +
            '<div class="stat-chip">⭐ Mastered: <span class="val">' + totalMastered + '</span></div>';
    }}
}})();
</script>
<script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('/sw.js');}}</script>
</body>
</html>'''
    return html


def _pwa_manifest() -> str:
    """Generate manifest.json for PWA."""
    return json.dumps({
        "name": "Modern Family · Speaking Review",
        "short_name": "MF Review",
        "description": "Interactive English learning from Modern Family scripts",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2563eb",
        "orientation": "any",
        "icons": [
            {"src": "data:image/svg+xml," + _svg_icon(192), "sizes": "192x192", "type": "image/svg+xml"},
            {"src": "data:image/svg+xml," + _svg_icon(512), "sizes": "512x512", "type": "image/svg+xml"},
        ],
    }, indent=2)


def _svg_icon(size: int) -> str:
    """Minimal SVG icon with emoji."""
    import urllib.parse
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}"><rect width="{size}" height="{size}" fill="#2563eb" rx="{size//4}"/><text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" font-size="{size//2}px">🎬</text></svg>'
    return urllib.parse.quote(svg)


def _service_worker() -> str:
    """Generate service worker for offline caching."""
    return """// Modern Family Review — Service Worker
const CACHE = 'mf-review-v1';
const ASSETS = [
    '/',
    '/index.html',
    '/manifest.json',
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(cache => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys => Promise.all(
            keys.filter(k => k !== CACHE).map(k => caches.delete(k))
        ))
    );
    self.clients.claim();
});

self.addEventListener('fetch', e => {
    // Only handle navigation and same-origin requests
    if (e.request.method !== 'GET') return;
    e.respondWith(
        caches.match(e.request).then(cached => {
            const fetched = fetch(e.request).then(response => {
                if (response.ok && response.type === 'basic') {
                    const clone = response.clone();
                    caches.open(CACHE).then(cache => cache.put(e.request, clone));
                }
                return response;
            }).catch(() => cached);
            return cached || fetched;
        })
    );
});
"""


def generate_site(reviews: list[EpisodeReview], output_dir: Optional[Path] = None,
                 all_episodes_info: dict = None) -> Path:
    """Generate static HTML site.

    Args:
        reviews: list of processed EpisodeReview objects
        output_dir: output directory (default: data/output)
        all_episodes_info: optional dict of all known episodes for index page

    Returns:
        Path to the output directory
    """
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    # Write PWA manifest
    manifest = _pwa_manifest()
    (out / "manifest.json").write_text(manifest, encoding="utf-8")

    # Write service worker
    sw = _service_worker()
    (out / "sw.js").write_text(sw, encoding="utf-8")

    # Generate index page (pass all_episodes_info for full episode listing)
    index_html = build_index_html(reviews, all_episodes_info=all_episodes_info)
    (out / "index.html").write_text(index_html, encoding="utf-8")

    # Generate individual episode pages
    for review in reviews:
        ep_html = build_episode_html(review)
        filename = f"{review.episode_label.lower()}.html"
        (out / filename).write_text(ep_html, encoding="utf-8")

    return out


def regenerate_index(output_dir: Optional[Path] = None,
                     all_episodes_info: dict = None) -> Path:
    """Regenerate only the index page by reading all existing episode HTMLs.

    This is used after processing a single episode to update the index
    without regenerating all pages.
    """
    out = output_dir or OUTPUT_DIR
    from .llm_organizer import EpisodeReview

    # Ensure PWA files exist
    if not (out / "manifest.json").exists():
        (out / "manifest.json").write_text(_pwa_manifest(), encoding="utf-8")
    if not (out / "sw.js").exists():
        (out / "sw.js").write_text(_service_worker(), encoding="utf-8")

    reviews = []
    if out.exists():
        for f in sorted(out.glob("s*.html")):
            # Parse episode label from filename
            label = f.stem.upper()
            # Try to extract basic info from the HTML
            html = f.read_text(encoding="utf-8")
            import re
            # Count user annotations and AI discoveries
            n_u = len(re.findall(r'"source":\s*"user"', html))
            n_a = len(re.findall(r'"source":\s*"ai"', html))
            title_m = re.search(r'<span class="ep-title">([^<]+)</span>', html)
            title = title_m.group(1) if title_m else ""
            if n_u or n_a:
                reviews.append(EpisodeReview(
                    episode_label=label,
                    episode_title=title,
                    scenes=[],
                    user_annotations_count=n_u,
                    ai_discoveries_count=n_a,
                ))

    return generate_site(reviews, output_dir=out, all_episodes_info=all_episodes_info)
