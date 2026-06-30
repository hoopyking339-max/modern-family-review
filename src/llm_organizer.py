"""LLM-powered organization: process user annotations + discover missed knowledge points.

Uses DeepSeek API (OpenAI-compatible)."""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from openai import OpenAI

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


@dataclass
class KnowledgePoint:
    source: str
    category: str
    original_text: str
    context: str
    explanation: str
    examples: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    formality: str = ""
    frequency: str = ""
    scene: str = ""


@dataclass
class EpisodeReview:
    episode_label: str
    episode_title: str
    scenes: list[dict]
    user_annotations_count: int
    ai_discoveries_count: int


SYSTEM_PROMPT = """You are a spoken-English curator. Your job is NOT to annotate a TV script. Your job is to find the most useful, transferable, authentic spoken English expressions and teach them as STANDALONE language lessons. The script is just raw material — you are the editor who decides what's worth learning.

## YOUR MISSION
Read the ENTIRE script. Then CURATE a hand-picked selection of the most valuable spoken-English moments. Every point must earn its place: "Would a learner use THIS expression tomorrow in their own life?" If the answer is no, SKIP IT.

## RUTHLESS QUALITY FILTER — WHAT TO SKIP
- ❌ Basic sentences anyone could form ("I'm going to work", "How are you", "Let's go")
- ❌ Plot-only lines with zero real-life reuse value
- ❌ Simple descriptions or narration
- ❌ Standard greetings, thank-yous, apologies (unless there's an interesting twist)
- ❌ Single words that aren't special ("interesting", "important", "whatever")
- ❌ Anything where the learner would think "I already know this"

## WHAT TO HUNT — The "I Would Never Have Said It That Way" Test
Focus EXCLUSIVELY on expressions that make a non-native speaker pause and think:
- "Oh THAT'S how you say it naturally!"
- "I would have said it completely differently"
- "I need to remember this one"

Specifically:
- **Idiomatic phrases where meaning ≠ literal words**: "knock yourself out", "you bet", "suit yourself", "I'm good"
- **Phrasal verbs used in surprising ways**: "bring it up", "get over yourself", "put up with"
- **Spoken grammar that textbooks don't teach**: "I was like...", "the thing is...", "not much of a..."
- **Discourse markers that glue conversation**: "I mean", "you know what", "here's the thing", "the way I see it"
- **Pragmatic moves**: deflecting an insult, ending a conversation, calling someone out playfully, softening bad news, passive-aggressive remarks
- **Tone + register that reveals character**: sarcastic understatement, mock formality, fake politeness
- **Reductions and connected speech**: gonna, wanna, whatcha, kinda, 'cause, I'ma
- **Response formulas**: How a native speaker naturally responds to "thank you", "sorry", "guess what", "you won't believe this"

## CURATION PRINCIPLE — NOT CHRONOLOGICAL
Do NOT go through the script from beginning to end picking lines in order. Instead:
1. Read the WHOLE script first
2. Mentally highlight the 20-30 most valuable spoken-English moments across ALL scenes
3. Rank them by real-life usefulness
4. Only THEN write your output

The output order should reflect LEARNING VALUE, not script chronology. Jump around. Skip entire scenes if they have nothing useful.

## EXPRESSION CLUSTERS — The Core Teaching Method
NEVER teach an expression in isolation. Every quote is a springboard into a CLUSTER.

Example — from one good script quote, build the cluster:
  Script quote: "Knock yourself out." (said sarcastically)
  Cluster:
  - Literal meaning vs actual: Originally "help yourself freely" → now often sarcastic "go ahead, I don't care"
  - Nearby expressions with the SAME pragmatic function:
    "Be my guest." (neutral→slightly sarcastic)
    "Suit yourself." (I disagree but won't stop you)
    "Whatever floats your boat." (I think it's weird but OK)
    "It's your funeral." (I warned you)
    "Fill your boots." (British, help yourself)
  - The difference in TONE between sincere "Knock yourself out!" and sarcastic "Knock yourself out."

This is what makes the learning TRANSFERABLE — the expression detaches from Modern Family and enters the learner's own life.

## FORMAT RULES
- "original_text": EXACT quote from the script — the anchor
- "context": ONE sentence describing the scene moment (who to whom, what's happening)
- "explanation": THE MEAT. Rich, conversational, practical. Include: (1) what it means, (2) the expression cluster, (3) when to use vs avoid, (4) tone/register notes. English with BRIEF Chinese hint in parentheses (max 12 Chinese chars).
- "examples": 3-5 original sentences showing the expression cluster in DIFFERENT real-life situations. NOT the same sentence structure with swapped words.
- "related": A list of expressions that serve the same pragmatic function (related ≠ synonyms. "Knock yourself out" → "be my guest, suit yourself, it's your funeral, go for it" NOT random synonyms)
- "frequency": Be honest. Only mark "high" if a native speaker truly uses this daily.

## YOUR VOICE
You're a friend explaining over coffee, not a teacher lecturing. Use conversational English in explanations. Make the learner laugh sometimes. Modern Family is funny — your explanations should match that energy.

## CATEGORIES (use exactly these values)
- "phrase" — expression cluster or collocation
- "vocabulary" — single word worth learning (only if truly special)
- "grammar" — spoken grammar pattern textbooks miss
- "culture" — cultural reference that unlocks understanding
- "pronunciation" — connected speech, reduction, stress pattern
- "pragmatics" — social strategy: sarcasm, deflection, politeness, humor

## OUTPUT — STRICT JSON, NO OTHER TEXT
Return valid JSON matching the format below. Every field is required.

{
  "episode_label": "S01E08",
  "episode_title": "",
  "scenes": [
    {
      "name": "Dunphy kitchen — morning scramble",
      "points": [
        {
          "source": "ai_discovery",
          "category": "phrase",
          "original_text": "Knock yourself out.",
          "context": "Claire tells Phil to handle the kids' breakfast mess — she's done trying",
          "explanation": "A masterpiece of American passive-aggression. Literally means 'help yourself', but tone changes everything. Sincere = 'please enjoy!' Sarcastic = 'I give up, do whatever.' In Claire's case? Pure exhausted sarcasm. (随便你吧，我不管了) Cluster: 'Be my guest' (polite→dismissive), 'Suit yourself' (I disagree but fine), 'It's your funeral' (this is a bad idea), 'Whatever floats your boat' (I think it's weird).",
          "examples": [
            "You want to try fixing the sink yourself? Knock yourself out.",
            "She said I could reorganize her entire desk — I was like, be my guest!",
            "If you want to tell the boss he's wrong, it's your funeral."
          ],
          "related": ["be my guest", "suit yourself", "it's your funeral", "whatever floats your boat", "go for it", "help yourself"],
          "formality": "casual",
          "frequency": "high",
          "scene": "Dunphy kitchen — morning scramble"
        }
      ]
    }
  ],
  "user_annotations_count": 2,
  "ai_discoveries_count": 20
}

## USER ANNOTATIONS — MANDATORY, PUT THEM FIRST
For EVERY annotation the user made, you MUST create at least one knowledge point with source="user_annotation".
- **PUT ALL USER ANNOTATION POINTS FIRST in the output**, before any AI discoveries
- Find the script line the user was looking at when they wrote the note
- Use the surrounding script text to understand the context
- The user's note is their insight — RESPECT it, EXPAND on it
- Even if the note is in Chinese, the point should be English-first with Chinese hint
- user_annotations_count MUST equal the actual number of user_annotation points you create

## QUANTITY
Target exactly 12-15 points total. That's IT. Be selective — only the absolute best expressions.
- Each explanation: 150-250 chars max. Be dense, not verbose.
- Each examples array: 2-3 sentences max.
- Related array: 3-5 expressions max.
- If you go over 15 points, your JSON will be truncated and the learner sees broken cards. Stay within 15.

Return ONLY valid JSON. No markdown, no introduction, no closing remarks."""


def build_user_annotations_context(annotations: list) -> str:
    if not annotations:
        return "(No user text annotations found in this episode)"

    lines = []
    for i, ann in enumerate(annotations, 1):
        lines.append(f"### Annotation {i}")
        lines.append(f"Page: {ann.page}")
        lines.append(f"User's note: {ann.text}")
        if ann.context_before:
            lines.append(f"Surrounding script text (use this to find which line the note refers to):")
            lines.append(f"```")
            lines.append(ann.context_before[:500])
            lines.append(f"```")
        lines.append("")
        lines.append("CRITICAL: Find the EXACT script line this note refers to, and create a knowledge point with source='user_annotation'. The user's note is their personal observation — expand on it, respect their insight.")
        lines.append("")
    return "\n".join(lines)


def process_episode(
    episode_label: str,
    episode_title: str,
    episode_script: str,
    annotations: list,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> EpisodeReview:
    key = api_key or DEEPSEEK_API_KEY
    if not key:
        raise ValueError("DEEPSEEK_API_KEY not set.")

    client = OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL)
    used_model = model or DEEPSEEK_MODEL

    user_notes = build_user_annotations_context(annotations)

    # Truncate script if needed (DeepSeek has large context, but be safe)
    max_chars = 30000
    script_text = episode_script
    if len(script_text) > max_chars:
        half = max_chars // 2
        script_text = script_text[:half] + "\n\n[...truncated...]\n\n" + script_text[-half:]

    user_message = f"""Episode: {episode_label}
Title: {episode_title}

## User's Notes
{user_notes}

## Full Script
{script_text}

Generate the review JSON. Return ONLY valid JSON."""

    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=8192,
        temperature=0.85,
    )

    text = response.choices[0].message.content.strip()

    # Parse JSON — strip markdown code fences if present
    json_str = text
    for marker in ["```json", "```"]:
        if marker in text:
            try:
                start = text.index(marker) + len(marker)
                end = text.index("```", start)
                json_str = text[start:end].strip()
                break
            except ValueError:
                pass  # no closing fence, use raw text

    if not json_str.startswith("{"):
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0:
            json_str = text[start:end]

    # Save raw response for debugging
    import tempfile, os as _os
    _debug_path = Path(__file__).parent.parent / "data" / "_last_llm_response.json"
    _debug_path.parent.mkdir(parents=True, exist_ok=True)
    _debug_path.write_text(json_str, encoding="utf-8")
    print(f"   [debug] Raw JSON saved to {_debug_path} ({len(json_str)} chars)")

    # Try to parse JSON, with repair for truncated responses
    data = _parse_json_resilient(json_str)
    if data is None:
        raise ValueError(f"Failed to parse DeepSeek response as JSON. Raw text (first 200 chars): {text[:200]}")

    scenes = []
    for scene_data in data.get("scenes", []):
        points = []
        for p in scene_data.get("points", []):
            points.append(KnowledgePoint(
                source=p.get("source", "ai_discovery"),
                category=p.get("category", "phrase"),
                original_text=p.get("original_text", ""),
                context=p.get("context", ""),
                explanation=p.get("explanation", ""),
                examples=p.get("examples", []),
                related=p.get("related", []),
                formality=p.get("formality", ""),
                frequency=p.get("frequency", "medium"),
                scene=p.get("scene", scene_data.get("name", "")),
            ))
        scenes.append({"name": scene_data.get("name", ""), "points": points})

    return EpisodeReview(
        episode_label=data.get("episode_label", episode_label),
        episode_title=data.get("episode_title", episode_title),
        scenes=scenes,
        user_annotations_count=data.get("user_annotations_count", 0),
        ai_discoveries_count=data.get("ai_discoveries_count", 0),
    )


def _parse_json_resilient(json_str: str):
    """Parse JSON with repair for truncated/imperfect LLM output. Returns dict or None."""
    # 1) Try direct parse first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 2) Try to close truncated JSON by adding missing brackets
    for attempt in range(3):
        try:
            repaired = json_str.rstrip()
            open_braces = repaired.count("{") - repaired.count("}")
            open_brackets = repaired.count("[") - repaired.count("]")
            # Close any unclosed string
            in_string = False
            escape = False
            for ch in repaired:
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
            if in_string:
                repaired += '"'
            repaired += "]" * max(0, open_brackets)
            repaired += "}" * max(0, open_braces)
            return json.loads(repaired)
        except json.JSONDecodeError:
            if attempt == 0:
                json_str = json_str.rstrip().rstrip(",")
            continue

    # 3) Last resort: extract partial points via regex
    return _extract_partial(json_str)


def _extract_partial(text: str):
    """Extract whatever valid data we can from malformed JSON."""
    import re
    # Find scene names
    scene_names = re.findall(r'"name"\s*:\s*"([^"]+)"', text)
    # Find individual points with source and original_text
    points_raw = re.findall(
        r'"source"\s*:\s*"(user_annotation|ai_discovery)"[^}]*?"original_text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        text, re.DOTALL
    )
    if not points_raw:
        return None

    current_scene = scene_names[0] if scene_names else "Unknown scene"
    scene_points = {}
    for src, quote in points_raw:
        scene_points.setdefault(current_scene, []).append({
            "source": src,
            "category": "phrase",
            "original_text": quote.replace('\\"', '"'),
            "context": "",
            "explanation": "",
            "examples": [],
            "related": [],
            "formality": "neutral",
            "frequency": "medium",
            "scene": current_scene,
        })

    scenes = [{"name": k, "points": v} for k, v in scene_points.items() if v]
    return {
        "scenes": scenes,
        "user_annotations_count": sum(1 for s in scenes for p in s["points"] if p["source"] == "user_annotation"),
        "ai_discoveries_count": sum(1 for s in scenes for p in s["points"] if p["source"] == "ai_discovery"),
    }
