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

## USER ANNOTATIONS — ABSOLUTE PRIORITY, MUST COME FIRST

The user has manually marked lines in the script. These are the MOST IMPORTANT points. You MUST:

1. **IDENTIFY EXACTLY**: Read the user's note AND the surrounding script text carefully. Find the SPECIFIC line the note refers to. The note is a reaction to something in the script — figure out what.

2. **MERGE RELATED ANNOTATIONS**: If the user wrote multiple notes about the SAME expression or topic, CONSOLIDATE them into ONE knowledge point. Do NOT split them into separate points. For example, if the user highlighted "knock yourself out" on page 3 and wrote another note about it on page 5, create ONE point with a richer, deeper explanation that covers all their observations. The user may annotate the same thing repeatedly — that means they really care about it. Give it extra depth.

3. **USE THE NOTE'S INSIGHT**: The user's note (even if in Chinese) tells you what caught their attention. EXPAND on that exact insight. If they wrote "专程串门", explain the cluster around "pop in / swing by / stop by". If they wrote a dictionary definition, build a full expression cluster around that word. For merged annotations, weave ALL their notes into one comprehensive explanation.

4. **EXACT QUOTE**: The "original_text" field MUST be the EXACT line from the script the user was reacting to. Don't make up a similar sentence. Find it in the surrounding text.

5. **PUT USER POINTS FIRST**: All source="user_annotation" points go BEFORE any ai_discovery points in the output.

6. **ACCURATE COUNT**: user_annotations_count MUST equal the actual count of user_annotation points you output. Count them AFTER merging related annotations.

**CRITICAL**: Every user annotation must be covered, but related notes on the same topic should be MERGED. If there are 8 raw annotations but 3 are about the same expression, you should have ~5-6 user_annotation points, not 8. Quality depth over quantity of points.

## AI EXTENSIONS — SUPPLEMENTARY

After user annotations, add ai_discovery points for other valuable expressions the user might have missed. Focus on expressions that are genuinely useful in daily conversation.

## QUANTITY
- User annotation points: cover ALL user notes, merging related ones into richer single points
- AI discovery points: add enough to reach the total target
- **Total target: at least 30 points per episode** (combine user_annotation + ai_discovery)
- Each explanation: 200-400 chars. Rich, deep, and practical.
- Each examples array: 3-5 sentences showing real-life usage.
- Related array: 4-8 expressions in the same cluster.
- Go deep, not shallow. Every point should feel like a mini-lesson.
- IMPORTANT: Output ALL 30+ points. Do not stop early. The JSON must be complete.

## CRITICAL — OUTPUT FORMAT
You MUST output AT LEAST 30 knowledge points total. That means 30+ objects with "source" and "original_text" inside the "scenes" array. After the user_annotation points in the first scene objects, continue adding ai_discovery points as flat objects directly in the "scenes" array:
```json
{ "scenes": [
    { "name": "Scene A", "points": [ {user point 1}, {user point 2} ] },
    { "source": "ai_discovery", "category": "phrase", "original_text": "...", ... },
    { "source": "ai_discovery", "category": "phrase", "original_text": "...", ... },
    ... up to 30+ total points ...
]}
```
Every point must have: source, category, original_text, context, explanation, examples, related, formality, frequency, scene.
DO NOT stop until you have at least 30 points. Count them before finishing.

Return ONLY valid JSON. No markdown, no introduction, no closing remarks."""


def build_user_annotations_context(annotations: list) -> str:
    if not annotations:
        return "(No user text annotations found in this episode)"

    lines = []
    for i, ann in enumerate(annotations, 1):
        lines.append(f"### Annotation {i}")
        lines.append(f"Page: {ann.page}")
        lines.append(f"User wrote: \"{ann.text}\"")
        if ann.context_before:
            # Provide generous surrounding context (2000 chars) to ensure the exact line is included
            ctx = ann.context_before[:2000]
            lines.append(f"Script text surrounding this note:")
            lines.append(f"```")
            lines.append(ctx)
            lines.append(f"```")
            lines.append(f"⬆️ The user's note \"{ann.text}\" was written somewhere near these lines.")
            lines.append(f"Find the EXACT script quote the user was reacting to.")
        lines.append("")
        lines.append("REQUIRED: Create a source='user_annotation' point with the exact script quote this note refers to. Expand on the user's insight — they noticed something worth learning.")
        lines.append("")
    lines.append("⚠️ IMPORTANT: If multiple annotations above refer to the SAME expression or topic, MERGE them into ONE knowledge point with a richer explanation. Do NOT create separate points for the same thing.")
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
        max_tokens=16384,
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
    flat_scene_name = ""
    for scene_data in data.get("scenes", []):
        # Handle flat points (LLM sometimes outputs points directly in scenes array)
        if "source" in scene_data and "original_text" in scene_data:
            # This is a flat point, not wrapped in a scene object
            points = [KnowledgePoint(
                source=scene_data.get("source", "ai_discovery"),
                category=scene_data.get("category", "phrase"),
                original_text=scene_data.get("original_text", ""),
                context=scene_data.get("context", ""),
                explanation=scene_data.get("explanation", ""),
                examples=scene_data.get("examples", []),
                related=scene_data.get("related", []),
                formality=scene_data.get("formality", ""),
                frequency=scene_data.get("frequency", "medium"),
                scene=scene_data.get("scene", flat_scene_name),
            )]
            # Update flat_scene_name to the last seen scene
            if scene_data.get("scene"):
                flat_scene_name = scene_data.get("scene", "")
            scenes.append({"name": scene_data.get("scene", flat_scene_name), "points": points})
        else:
            # Normal scene object with points array
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
            if points:
                flat_scene_name = scene_data.get("name", "")
            scenes.append({"name": scene_data.get("name", ""), "points": points})

    # Count actual points (don't trust LLM's count)
    actual_user = sum(1 for s in scenes for p in s["points"] if p.source == "user_annotation")
    actual_ai = sum(1 for s in scenes for p in s["points"] if p.source == "ai_discovery")

    return EpisodeReview(
        episode_label=data.get("episode_label", episode_label),
        episode_title=data.get("episode_title", episode_title),
        scenes=scenes,
        user_annotations_count=actual_user,
        ai_discoveries_count=actual_ai,
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
