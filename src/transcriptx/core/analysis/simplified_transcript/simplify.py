import json
import re
from dataclasses import dataclass
from typing import Any


def _normalize_for_match(s: str) -> str:
    """
    Normalizes text for matching:
    - lowercase
    - remove punctuation (keep whitespace)
    - collapse spaces
    """
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)  # punctuation -> space
    s = re.sub(r"\s+", " ", s).strip()  # collapse whitespace
    return s


def _collapse_whitespace_and_punct(s: str) -> str:
    """
    Cleans up spacing/punctuation artifacts after removals.
    """
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    # remove spaces before punctuation
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)

    # collapse repeated punctuation like ", ," or "..."
    s = re.sub(r"([,.;:!?])\1+", r"\1", s)

    # remove leading/trailing punctuation
    s = re.sub(r"^[\s,.;:!?-]+", "", s)
    s = re.sub(r"[\s,.;:!?-]+$", "", s)

    # final whitespace pass
    s = re.sub(r"\s+", " ", s).strip()
    return s


@dataclass(frozen=True)
class SimplifierConfig:
    drop_agreements: bool = True
    drop_duplicates: bool = True
    duplicates_consecutive_only: bool = True  # if False, keep a set of all seen
    duplicates_per_speaker: bool = True  # if True, compare within speaker
    min_word_count: int = 1  # drop ultra-short after cleaning
    merge_consecutive_same_speaker: bool = False


class TranscriptSimplifier:
    def __init__(
        self,
        tics_list: list[str] | None = None,
        agreements_list: list[str] | None = None,
        config: SimplifierConfig | None = None,
    ):
        self.tics_list = [t.strip() for t in (tics_list or []) if t and t.strip()]
        self.agreements_list = [
            a.strip() for a in (agreements_list or []) if a and a.strip()
        ]
        self.config = config or SimplifierConfig()

        # --- Precompute compiled regex for tics ---
        # Sort by length desc so multi-word / longer tics match first.
        # Use "word-ish" boundaries that work better across punctuation/spaces.
        self._tic_re = None
        if self.tics_list:
            escaped = sorted(
                (re.escape(t) for t in self.tics_list), key=len, reverse=True
            )

            # Boundary idea:
            # - left boundary: start OR whitespace OR punctuation
            # - right boundary: end OR whitespace OR punctuation
            # This avoids \b weirdness with multiword phrases and punctuation.
            pattern = r"(?i)(^|[\s\W])(" + "|".join(escaped) + r")(?=$|[\s\W])"
            self._tic_re = re.compile(pattern)

        # --- Precompute normalized agreement phrases ---
        self._agreement_phrases = {
            _normalize_for_match(a)
            for a in self.agreements_list
            if _normalize_for_match(a)
        }

        # Optional: common acknowledgements you may want to treat as agreements
        # even if not listed (you can remove these if you want fully
        # user-controlled behavior)
        self._default_ack = {
            "yeah",
            "yep",
            "yup",
            "ok",
            "okay",
            "right",
            "sure",
            "mm",
            "mhmm",
            "uh huh",
            "uh-huh",
        }

    def clean_utterance(self, text: str) -> str:
        if not text:
            return ""

        s = text

        # Remove tics/hesitations (if any configured)
        if self._tic_re is not None:
            # Replace tic with the left boundary group to avoid eating
            # spaces/punct entirely
            s = self._tic_re.sub(r"\1", s)

        # Clean punctuation/spacing artifacts
        s = _collapse_whitespace_and_punct(s)
        return s

    def is_agreement(self, text: str) -> bool:
        """
        Agreement = normalized text equals one of the agreement phrases
        OR (optionally) equals one of a small default ack set.
        """
        norm = _normalize_for_match(text)
        if not norm:
            return False

        if norm in self._agreement_phrases:
            return True

        # Heuristic: treat short acknowledgements as agreement
        # Only if drop_agreements is enabled (else irrelevant)
        if self.config.drop_agreements and norm in self._default_ack:
            return True

        return False

    def _is_too_short(self, text: str) -> bool:
        # Count "words" after normalization
        norm = _normalize_for_match(text)
        if not norm:
            return True
        return len(norm.split()) < self.config.min_word_count

    def simplify(
        self,
        transcript: list[dict[str, Any]],
        verbose: bool = False,
    ) -> list[dict[str, Any]]:
        simplified: list[dict[str, Any]] = []

        prev_by_key: dict[str, str] = {}  # key -> last normalized text
        seen_by_key: dict[str, set[str]] = {}

        def key_for_turn(speaker: str) -> str:
            return speaker if self.config.duplicates_per_speaker else "__all__"

        for turn in transcript:
            speaker = (turn.get("speaker") or "").strip()
            text = turn.get("text") or ""

            cleaned = self.clean_utterance(text)
            norm = _normalize_for_match(cleaned)

            if verbose:
                print(f"ORIG: {text!r} | CLEAN: {cleaned!r} | NORM: {norm!r}")

            # Drop empty / too short
            if not norm or self._is_too_short(cleaned):
                continue

            # Drop agreements
            if self.config.drop_agreements and self.is_agreement(cleaned):
                continue

            # Drop duplicates (configurable)
            if self.config.drop_duplicates:
                k = key_for_turn(speaker)
                if self.config.duplicates_consecutive_only:
                    if prev_by_key.get(k) == norm:
                        continue
                    prev_by_key[k] = norm
                else:
                    seen = seen_by_key.setdefault(k, set())
                    if norm in seen:
                        continue
                    seen.add(norm)

            # Merge consecutive same speaker (optional)
            if (
                self.config.merge_consecutive_same_speaker
                and simplified
                and simplified[-1]["speaker"] == speaker
            ):
                # Combine with a separator that preserves readability.
                simplified[-1]["text"] = _collapse_whitespace_and_punct(
                    simplified[-1]["text"] + " " + cleaned
                )
            else:
                simplified.append({"speaker": speaker, "text": cleaned})

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
