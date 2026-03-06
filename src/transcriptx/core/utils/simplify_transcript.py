import json
import re
from typing import Any


class TranscriptSimplifier:
    def __init__(self, tics_list: list[str] = None, agreements_list: list[str] = None):
        self.tics_list = tics_list or []
        self.agreements_list = agreements_list or []

    def clean_utterance(self, text: str) -> str:
        # Remove tics/hesitations
        pattern = r"\b(" + "|".join(map(re.escape, self.tics_list)) + r")\b"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        # Remove extra spaces
        text = re.sub(r"\s+", " ", text).strip()
        # Remove leading/trailing punctuation left by tic removal
        text = re.sub(r"^[,\s]+", "", text)
        text = re.sub(r"[\s,]+$", "", text)
        return text

    def is_agreement(self, text: str) -> bool:
        # Remove punctuation and lowercase
        def clean_phrase(s):
            return re.sub(r"[^\w\s]", "", s).strip().lower()

        text_clean = clean_phrase(text)
        words = text_clean.split()
        # Build set of all agreement words from all phrases
        agreement_words = set()
        for agr in self.agreements_list:
            agreement_words.update(clean_phrase(agr).split())
        return all(word in agreement_words for word in words) and words != []

    def simplify(
        self, transcript: list[dict[str, Any]], verbose: bool = False
    ) -> list[dict[str, Any]]:
        simplified = []
        prev_text = None
        for turn in transcript:
            speaker = turn.get("speaker", "")
            text = turn.get("text", "")
            cleaned = self.clean_utterance(text)
            # Remove all punctuation for agreement/empty check
            cleaned_no_punct = re.sub(r"[^\w\s]", "", cleaned).strip()
            if verbose:
                print(
                    f"ORIG: {text!r} | CLEAN: {cleaned!r} | NOPUNCT: {cleaned_no_punct!r}"
                )
            # Skip if empty or only punctuation after cleaning
            if not cleaned_no_punct or not re.search(r"\w", cleaned_no_punct):
                continue
            if self.is_agreement(cleaned):
                continue
            if prev_text and cleaned.lower() == prev_text.lower():
                continue  # Remove repetitions
            # Note: Future enhancement could add more advanced substance/decision detection
            simplified.append({"speaker": speaker, "text": cleaned})
            prev_text = cleaned
        return simplified


def main():
    # Example usage
    tics = ["um", "uh", "like", "you know", "I mean"]
    agreements = ["yeah", "right", "absolutely", "I agree", "sure"]
    transcript = [
        {"speaker": "Alice", "text": "Um, I think we should start."},
        {"speaker": "Bob", "text": "Yeah, I agree."},
        {"speaker": "Alice", "text": "Let's review the agenda."},
        {"speaker": "Bob", "text": "Let's review the agenda."},
        {"speaker": "Alice", "text": "You know, the main point is the launch."},
    ]
    simplifier = TranscriptSimplifier(tics, agreements)
    simplified = simplifier.simplify(transcript)
    print(json.dumps(simplified, indent=2))


if __name__ == "__main__":
    main()
