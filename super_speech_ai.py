import json
import math
import re
import textwrap
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html import unescape

import streamlit as st


APP_TITLE = "Super Speech AI"

GRADE_SETTINGS = {
    "Grade 3-4": {
        "wpm": (95, 115),
        "sentence_words": 10,
        "paragraph_words": 45,
        "voice": "Use short, friendly sentences. Explain hard words simply.",
        "connectors": ["First", "Next", "Also", "Finally"],
    },
    "Grade 5-6": {
        "wpm": (105, 125),
        "sentence_words": 13,
        "paragraph_words": 60,
        "voice": "Use clear school-level language with simple examples.",
        "connectors": ["First", "Another reason", "For example", "In conclusion"],
    },
    "Grade 7-8": {
        "wpm": (110, 130),
        "sentence_words": 16,
        "paragraph_words": 75,
        "voice": "Use confident language, topic words, and clear explanations.",
        "connectors": ["To begin", "This matters because", "A useful example is", "To conclude"],
    },
    "Grade 9-10": {
        "wpm": (115, 135),
        "sentence_words": 19,
        "paragraph_words": 90,
        "voice": "Use mature but readable language, evidence, and transitions.",
        "connectors": ["The central point is", "Evidence suggests", "This shows", "Overall"],
    },
    "Grade 11-12": {
        "wpm": (120, 145),
        "sentence_words": 22,
        "paragraph_words": 105,
        "voice": "Use polished academic language without becoming too dense.",
        "connectors": ["A key consideration is", "Research indicates", "This strengthens the argument", "Ultimately"],
    },
    "University": {
        "wpm": (125, 155),
        "sentence_words": 26,
        "paragraph_words": 120,
        "voice": "Use sophisticated academic phrasing, careful claims, and source-based reasoning.",
        "connectors": ["The broader issue is", "The evidence points to", "This is significant because", "In synthesis"],
    },
}


@dataclass
class Source:
    title: str
    url: str
    snippet: str
    source_type: str
    year: int | None = None
    score: float = 0.0


def fetch_json(url: str, timeout: int = 10) -> dict | list | None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SuperSpeechAI/1.0 (student research app)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def clean_text(value: str) -> str:
    value = unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def topic_terms(topic: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "about",
        "why",
        "how",
        "what",
        "are",
        "is",
        "of",
        "to",
        "in",
        "a",
        "an",
        "on",
    }
    return {word.lower() for word in re.findall(r"[A-Za-z]{3,}", topic) if word.lower() not in stop}


def relevance_score(source: Source, topic: str) -> float:
    terms = topic_terms(topic)
    haystack = f"{source.title} {source.snippet}".lower()
    matches = sum(1 for term in terms if term in haystack)
    relevance = matches / max(len(terms), 1)
    credibility = {
        "Encyclopedia": 0.78,
        "Academic paper": 0.93,
        "OpenAlex research": 0.9,
    }.get(source.source_type, 0.65)
    recency = 0.5
    if source.year:
        recency = max(0.3, min(1.0, 1 - ((datetime.now().year - source.year) / 25)))
    usefulness = min(len(source.snippet) / 280, 1.0)
    return round((relevance * 45) + (credibility * 30) + (recency * 15) + (usefulness * 10), 1)


def search_wikipedia(topic: str, limit: int) -> list[Source]:
    query = urllib.parse.quote(topic)
    url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&generator=search&gsrsearch={query}&gsrlimit={limit}"
        "&prop=extracts|info&exintro=1&explaintext=1&inprop=url&format=json"
    )
    data = fetch_json(url)
    pages = (data or {}).get("query", {}).get("pages", {})
    sources = []
    for page in pages.values():
        title = clean_text(page.get("title", ""))
        snippet = clean_text(page.get("extract", ""))[:700]
        url = page.get("fullurl") or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
        if title and snippet:
            sources.append(Source(title, url, snippet, "Encyclopedia"))
    return sources


def search_crossref(topic: str, limit: int) -> list[Source]:
    query = urllib.parse.quote(topic)
    url = f"https://api.crossref.org/works?query={query}&rows={limit}&select=title,URL,abstract,published-print,published-online,issued,type"
    data = fetch_json(url)
    items = (data or {}).get("message", {}).get("items", [])
    sources = []
    for item in items:
        title_list = item.get("title") or []
        title = clean_text(title_list[0] if title_list else "")
        date_parts = (
            item.get("published-print", {}).get("date-parts")
            or item.get("published-online", {}).get("date-parts")
            or item.get("issued", {}).get("date-parts")
            or []
        )
        year = date_parts[0][0] if date_parts and date_parts[0] else None
        snippet = clean_text(item.get("abstract", ""))
        if not snippet:
            snippet = f"Academic source about {topic}."
        if title and item.get("URL"):
            sources.append(Source(title, item["URL"], snippet[:700], "Academic paper", year))
    return sources


def search_openalex(topic: str, limit: int) -> list[Source]:
    query = urllib.parse.quote(topic)
    url = f"https://api.openalex.org/works?search={query}&per-page={limit}"
    data = fetch_json(url)
    results = (data or {}).get("results", [])
    sources = []
    for item in results:
        title = clean_text(item.get("title", ""))
        abstract_index = item.get("abstract_inverted_index") or {}
        words = []
        for word, positions in abstract_index.items():
            for position in positions:
                words.append((position, word))
        abstract = " ".join(word for _, word in sorted(words)) if words else ""
        snippet = clean_text(abstract) or f"Research source connected to {topic}."
        url = item.get("primary_location", {}).get("landing_page_url") or item.get("doi") or item.get("id", "")
        year = item.get("publication_year")
        if title and url:
            sources.append(Source(title, url, snippet[:700], "OpenAlex research", year))
    return sources


def discover_sources(topic: str, wanted: int) -> list[Source]:
    raw_sources = []
    raw_sources.extend(search_wikipedia(topic, max(3, wanted)))
    raw_sources.extend(search_crossref(topic, max(4, wanted)))
    raw_sources.extend(search_openalex(topic, max(4, wanted)))

    unique = {}
    for source in raw_sources:
        key = source.url.lower().strip()
        if key not in unique:
            source.score = relevance_score(source, topic)
            unique[key] = source

    ranked = sorted(unique.values(), key=lambda item: item.score, reverse=True)
    return ranked[:wanted]


def target_words(length_mode: str, length_value: int, grade: str) -> int:
    if length_mode == "Words":
        return max(80, int(length_value))
    low, high = GRADE_SETTINGS[grade]["wpm"]
    return max(80, int(length_value * ((low + high) / 2)))


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def shorten_sentence(sentence: str, max_words: int) -> list[str]:
    words = sentence.split()
    if len(words) <= max_words + 5:
        return [sentence]
    chunks = []
    for start in range(0, len(words), max_words):
        chunk = " ".join(words[start : start + max_words]).strip(",;:")
        if chunk:
            chunks.append(chunk[0].upper() + chunk[1:] + ".")
    return chunks


def adapt_for_grade(text: str, grade: str) -> str:
    settings = GRADE_SETTINGS[grade]
    sentences = []
    for sentence in split_sentences(text):
        sentences.extend(shorten_sentence(sentence, settings["sentence_words"]))
    adapted = " ".join(sentences)

    if grade in {"Grade 3-4", "Grade 5-6"}:
        replacements = {
            "significant": "important",
            "therefore": "so",
            "demonstrates": "shows",
            "consequence": "result",
            "approximately": "about",
            "individuals": "people",
            "utilize": "use",
        }
        for hard, simple in replacements.items():
            adapted = re.sub(rf"\b{hard}\b", simple, adapted, flags=re.IGNORECASE)
    return adapted


def source_fact_blocks(sources: list[Source], max_blocks: int) -> list[str]:
    facts = []
    for index, source in enumerate(sources[:max_blocks], start=1):
        sentences = split_sentences(source.snippet)
        fact = sentences[0] if sentences else source.snippet
        facts.append(f"{fact} [{index}]")
    return facts


def expand_to_length(paragraphs: list[str], desired_words: int, sources: list[Source], grade: str) -> list[str]:
    current = len(" ".join(paragraphs).split())
    if current >= desired_words * 0.9:
        return paragraphs

    settings = GRADE_SETTINGS[grade]
    extra_facts = source_fact_blocks(sources, len(sources))
    additions = []
    while current < desired_words * 0.95 and len(additions) < 8:
        fact = extra_facts[len(additions) % max(len(extra_facts), 1)] if extra_facts else ""
        addition = (
            f"{settings['connectors'][len(additions) % len(settings['connectors'])]}, this point helps us understand the topic better. "
            f"{fact} "
            "This evidence gives the audience a stronger reason to care and to think about what should happen next."
        )
        addition = adapt_for_grade(addition, grade)
        additions.append(addition)
        current += len(addition.split())

    if additions:
        paragraphs.insert(-1, " ".join(additions))
    return paragraphs


def trim_to_length(text: str, desired_words: int) -> str:
    words = text.split()
    upper = int(desired_words * 1.12)
    if len(words) <= upper:
        return text
    clipped = " ".join(words[:upper])
    last_stop = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    if last_stop > len(clipped) * 0.75:
        clipped = clipped[: last_stop + 1]
    return clipped + "\n\n[Shortened to stay close to the requested length.]"


def make_speech(topic: str, audience: str, grade: str, speech_type: str, tone: str, desired_words: int, sources: list[Source]) -> str:
    settings = GRADE_SETTINGS[grade]
    facts = source_fact_blocks(sources, 5)
    audience_text = audience or "the audience"
    source_count = len(sources)

    if not topic.strip():
        topic = "this topic"

    opener = (
        f"Good day everyone. Today I am speaking about {topic}. "
        f"This topic matters to {audience_text} because it affects how people understand the world and make choices. "
        f"I used {source_count} selected source{'s' if source_count != 1 else ''} to build this speech."
    )

    if speech_type == "Persuasive":
        thesis = f"My main argument is that we should pay closer attention to {topic} and take thoughtful action."
    elif speech_type == "Debate":
        thesis = f"My position is that {topic} deserves strong support when we look carefully at the evidence."
    elif speech_type == "Academic":
        thesis = f"The main purpose of this speech is to explain what reliable sources show about {topic}."
    elif speech_type == "Storytelling":
        thesis = f"To understand {topic}, we can follow the story of how one idea leads to another."
    elif speech_type == "Ceremonial":
        thesis = f"This speech invites us to reflect on {topic} with respect, gratitude, and purpose."
    else:
        thesis = f"My goal is to explain the most important ideas about {topic} in a clear way."

    body = []
    connectors = settings["connectors"]
    for index, fact in enumerate(facts[:4]):
        if index == 0:
            point = f"{connectors[0]}, one important fact is this: {fact}"
        elif index == 1:
            point = f"{connectors[1]}, the evidence adds another useful idea: {fact}"
        elif index == 2:
            point = f"{connectors[2]}, this source gives us a helpful example: {fact}"
        else:
            point = f"{connectors[3]}, the sources also remind us that {fact}"
        body.append(point)

    if not body:
        body.append(
            "A good speech needs reliable evidence. Add a topic and click Find Sources so this section can include real source-based points."
        )

    topic_sentence = (
        f"When we connect these points, we can see that {topic} is not just a single fact. "
        f"It is an issue with causes, effects, and choices. "
        f"For {audience_text}, that means listening carefully, asking good questions, and using evidence before forming an opinion."
    )

    conclusion = (
        f"In conclusion, {topic} is worth understanding because it connects information with real decisions. "
        f"The selected sources help us move beyond guessing. "
        f"They give us evidence, examples, and a stronger reason to think carefully. "
        f"Thank you for listening."
    )

    paragraphs = [
        opener,
        thesis,
        " ".join(body[:2]),
        " ".join(body[2:]) if len(body) > 2 else topic_sentence,
        topic_sentence,
        conclusion,
    ]

    paragraphs = [adapt_for_grade(paragraph, grade) for paragraph in paragraphs if paragraph.strip()]
    paragraphs = expand_to_length(paragraphs, desired_words, sources, grade)
    speech = "\n\n".join(paragraphs)
    speech = trim_to_length(speech, desired_words)

    citations = ["", "Sources used:"]
    for index, source in enumerate(sources, start=1):
        year = f" ({source.year})" if source.year else ""
        citations.append(f"[{index}] {source.title}{year}. {source.url}")

    return speech + "\n\n" + "\n".join(citations)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def estimate_minutes(words: int, grade: str) -> float:
    low, high = GRADE_SETTINGS[grade]["wpm"]
    return words / ((low + high) / 2)


def analyze_speech(text: str, grade: str, desired_words: int, sources: list[Source]) -> list[tuple[str, str]]:
    suggestions = []
    words = word_count(text)
    if words < desired_words * 0.85:
        suggestions.append(("warn", f"The speech is short: {words} words. Add one more example or explanation."))
    elif words > desired_words * 1.15:
        suggestions.append(("warn", f"The speech is long: {words} words. Remove repeated ideas or shorten examples."))
    else:
        suggestions.append(("good", f"The length is close to the target at {words} words."))

    sentences = split_sentences(text)
    avg_sentence = words / max(len(sentences), 1)
    max_words = GRADE_SETTINGS[grade]["sentence_words"]
    if avg_sentence > max_words + 4:
        suggestions.append(("warn", f"Average sentence length is {avg_sentence:.1f} words. Shorten a few sentences for {grade}."))
    else:
        suggestions.append(("good", f"Sentence length fits the selected level: about {avg_sentence:.1f} words per sentence."))

    citation_hits = len(re.findall(r"\[\d+\]", text))
    if sources and citation_hits < min(2, len(sources)):
        suggestions.append(("alert", "Use more source citations inside the speech, such as [1] or [2], after evidence."))
    elif sources:
        suggestions.append(("good", "The speech includes source markers for evidence."))

    if not re.search(r"\bthank you\b|\bin conclusion\b|\bto conclude\b", text, re.IGNORECASE):
        suggestions.append(("warn", "Add a clear closing sentence so the ending feels complete."))

    return suggestions


def analyze_practice(transcript: str, speech: str, seconds: int, grade: str, speech_type: str) -> list[tuple[str, str]]:
    suggestions = []
    spoken_words = word_count(transcript)
    pace = spoken_words / max(seconds / 60, 0.1)
    low, high = GRADE_SETTINGS[grade]["wpm"]

    if spoken_words == 0:
        return [("warn", "No practice transcript yet. Record yourself or paste what you said, then analyze again.")]

    if pace < low:
        suggestions.append(("warn", f"You spoke at about {pace:.0f} words per minute. Try a little faster for this topic."))
    elif pace > high:
        suggestions.append(("warn", f"You spoke at about {pace:.0f} words per minute. Slow down so the audience can follow."))
    else:
        suggestions.append(("good", f"Your pace is strong at about {pace:.0f} words per minute."))

    filler_count = len(re.findall(r"\b(um|uh|like|you know|basically|actually)\b", transcript, re.IGNORECASE))
    if filler_count > max(2, spoken_words // 80):
        suggestions.append(("warn", f"You used {filler_count} filler words. Pause silently instead of filling the gap."))
    else:
        suggestions.append(("good", "Filler words are under control."))

    speech_terms = topic_terms(speech) | set(re.findall(r"\[\d+\]", speech))
    transcript_terms = set(word.lower() for word in re.findall(r"[A-Za-z]{3,}|\[\d+\]", transcript))
    coverage = len(speech_terms & transcript_terms) / max(len(speech_terms), 1)
    if coverage < 0.35:
        suggestions.append(("warn", "You may have skipped several key ideas. Practice with the main points visible."))
    else:
        suggestions.append(("good", "Your practice includes many of the important ideas from the speech."))

    if speech_type in {"Academic", "Debate"} and pace > high - 5:
        suggestions.append(("warn", "Because this is a more serious topic, leave tiny pauses after evidence and citations."))
    elif speech_type in {"Storytelling", "Ceremonial"} and pace < low + 5:
        suggestions.append(("warn", "This kind of speech can carry more energy. Lift your pace slightly in the middle."))

    return suggestions


def render_suggestions(items: list[tuple[str, str]]) -> None:
    for level, message in items:
        if level == "good":
            st.success(message)
        elif level == "alert":
            st.error(message)
        else:
            st.warning(message)


def initialize_state() -> None:
    defaults = {
        "sources": [],
        "speech": "",
        "practice_start": None,
        "practice_seconds": 180,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🎤", layout="wide")
    initialize_state()

    st.title(APP_TITLE)
    st.caption("Creates source-based speeches and helps you practice pace, clarity, and delivery.")

    with st.sidebar:
        st.header("Speech setup")
        topic = st.text_input("Topic", placeholder="Example: Should schools ban plastic bottles?")
        audience = st.text_input("Audience", placeholder="Example: classmates and teachers")
        grade = st.selectbox("Grammar level", list(GRADE_SETTINGS.keys()), index=2)
        speech_type = st.selectbox(
            "Speech type",
            ["Informative", "Persuasive", "Academic", "Storytelling", "Debate", "Ceremonial"],
        )
        tone = st.selectbox(
            "Tone",
            ["clear and confident", "warm and friendly", "serious and respectful", "energetic and inspiring"],
        )
        length_mode = st.radio("Length by", ["Minutes", "Words"], horizontal=True)
        length_value = st.number_input("Target length", min_value=1, max_value=3000, value=3 if length_mode == "Minutes" else 400)
        source_count = st.slider("Number of selected sources", min_value=3, max_value=8, value=5)

        st.info(GRADE_SETTINGS[grade]["voice"])

        find_sources = st.button("Find Good Sources", use_container_width=True)
        generate = st.button("Generate Speech", type="primary", use_container_width=True)

    desired_words = target_words(length_mode, int(length_value), grade)

    if find_sources or (generate and topic and not st.session_state.sources):
        if not topic.strip():
            st.warning("Add a topic first so the app can search for useful sources.")
        else:
            with st.spinner("Searching and ranking sources..."):
                st.session_state.sources = discover_sources(topic, source_count)
            if not st.session_state.sources:
                st.error("I could not find sources. Check your internet connection or try a more specific topic.")

    if generate:
        if not st.session_state.sources:
            st.warning("Find sources first, or try a clearer topic.")
        else:
            st.session_state.speech = make_speech(
                topic,
                audience,
                grade,
                speech_type,
                tone,
                desired_words,
                st.session_state.sources,
            )

    tab_speech, tab_sources, tab_practice = st.tabs(["Speech", "Selected sources", "Practice coach"])

    with tab_speech:
        words = word_count(st.session_state.speech)
        minutes = estimate_minutes(words, grade) if words else 0
        st.write(f"Target: about **{desired_words} words**. Current draft: **{words} words**, about **{minutes:.1f} minutes**.")
        st.session_state.speech = st.text_area("Speech draft", value=st.session_state.speech, height=520)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Download speech as text",
                st.session_state.speech,
                file_name="super_speech_ai_speech.txt",
                disabled=not bool(st.session_state.speech.strip()),
            )
        with col2:
            st.write("Speech suggestions")
            render_suggestions(analyze_speech(st.session_state.speech, grade, desired_words, st.session_state.sources))

    with tab_sources:
        if not st.session_state.sources:
            st.info("Click Find Good Sources to let the app select useful sources for the topic.")
        for index, source in enumerate(st.session_state.sources, start=1):
            with st.expander(f"[{index}] {source.title} - score {source.score}"):
                st.write(f"Type: **{source.source_type}**")
                if source.year:
                    st.write(f"Year: **{source.year}**")
                st.write(source.snippet)
                st.link_button("Open source", source.url)

    with tab_practice:
        st.write("Use a phone or stopwatch while speaking, then enter your time and transcript. Some online runners do not allow microphone recording.")
        low, high = GRADE_SETTINGS[grade]["wpm"]
        st.write(f"Pace goal for **{grade}**: **{low}-{high} words per minute**.")

        minutes_spoken = st.number_input("Practice minutes", min_value=0, max_value=60, value=2)
        seconds_spoken = st.number_input("Extra seconds", min_value=0, max_value=59, value=0)
        transcript = st.text_area("Practice transcript", height=260, placeholder="Paste what you said while practicing.")
        total_seconds = int(minutes_spoken * 60 + seconds_spoken)

        if st.button("Analyze Practice", type="primary"):
            render_suggestions(analyze_practice(transcript, st.session_state.speech, total_seconds, grade, speech_type))

        st.divider()
        st.subheader("Live pacing helper")
        st.write("This simple timer tells you whether your current word count is too fast or too slow for the topic.")
        live_words = st.number_input("Words spoken so far", min_value=0, max_value=10000, value=0)
        elapsed_seconds = st.number_input("Seconds spoken so far", min_value=1, max_value=7200, value=60)
        live_pace = live_words / (elapsed_seconds / 60)
        st.metric("Current pace", f"{live_pace:.0f} wpm")
        if live_pace < low:
            st.warning("Talk a little faster. The audience may feel the speech is dragging.")
        elif live_pace > high:
            st.warning("Slow down. This topic needs clearer pauses so people can understand it.")
        else:
            st.success("Your pace is in the right range for this topic and grade level.")


if __name__ == "__main__":
    main()
