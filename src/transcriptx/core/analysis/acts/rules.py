from __future__ import annotations

import re
from typing import Any

from transcriptx.core.analysis.acts.config import get_all_act_types
from transcriptx.core.analysis.acts.confidence import (
    adjust_confidence_for_context,
    calculate_act_confidence,
)

ACT_TYPES = get_all_act_types()

CUE_PHRASES = {
    "question": [
        # Direct questions with question marks
        (
            r"\b(what|why|how|when|where|who|which|is|are|do|does|did|can|could|should|would|will|have|has|had|may|might|must)\b.*\?",
            0.95,
        ),
        # Indirect questions and polite requests
        (
            r"\b(any idea|do you know|could you tell me|would you mind|is there|are there|can you help|wondering if|just checking if|mind if|care to)\b",
            0.85,
        ),
        # Confirmation questions
        (
            r"^\s*(really|seriously|true|right|okay|alright|fine|sure|honestly|actually)\s*\?$",
            0.9,
        ),
        # Tag questions and clarifications
        (
            r"\b(you sure|you mean|that right|is that so|aren't you|don't you|won't you|can't you)\b",
            0.8,
        ),
        # Rhetorical questions
        (r"\b(how else|what else|why else|where else|who else|when else)\b", 0.75),
        # Question words without question marks
        (r"^\s*(what|why|how|when|where|who|which)\b", 0.7),
    ],
    "suggestion": [
        # Direct suggestions
        (
            r"\b(let's|we should|i suggest|why don't we|how about we|perhaps we could|may we|shall we|we could|you could|consider this)\b",
            0.9,
        ),
        # Conditional suggestions
        (
            r"\b(i think we could|what if we|we could try|maybe we can|how about trying|let me suggest|suppose we|imagine if)\b",
            0.8,
        ),
        # Advice and recommendations
        (
            r"\b(try to|you should|we ought to|i recommend|my advice|suggest you|consider doing|think about)\b",
            0.75,
        ),
        # Collaborative suggestions
        (r"\b(we might|we could|we can|together we|as a team|collectively)\b", 0.7),
        # Soft suggestions
        (r"\b(maybe|perhaps|possibly|potentially|ideally|hopefully)\b", 0.6),
    ],
    "agreement": [
        # Strong agreement
        (
            r"\b(yes|absolutely|exactly|i agree|definitely|true|that's right|yep|for sure|i totally agree|spot on|you got it|no doubt)\b",
            0.95,
        ),
        # Moderate agreement
        (
            r"\b(you're right|that makes sense|agreed|sounds good|okay|alright|i suppose so|fair enough|i concur|my thoughts exactly)\b",
            0.8,
        ),
        # Simple agreement
        (r"^\s*(yes|yep|yeah|yup|sure|correct|right|ok|okay)\s*$", 0.9),
        # Conditional agreement
        (
            r"\b(i guess so|probably|likely|seems right|looks good|works for me|fine by me)\b",
            0.7,
        ),
        # Agreement with enthusiasm
        (
            r"\b(hell yes|absolutely|without a doubt|you bet|certainly|indeed|most definitely)\b",
            0.95,
        ),
    ],
    "disagreement": [
        # Strong disagreement
        (
            r"\b(no|i don't think so|i'm not sure|not really|i disagree|nah|that's not right|i don't agree|no way|absolutely not)\b",
            0.95,
        ),
        # Polite disagreement
        (
            r"\b(i beg to differ|i'm afraid not|not quite|i see it differently|hmm, not sure|i'm not convinced)\b",
            0.85,
        ),
        # Simple disagreement
        (r"^\s*(no|nope|nah|not really|not quite)\s*$", 0.9),
        # Conditional disagreement
        (
            r"\b(i'm not so sure|i have doubts|i'm skeptical|not necessarily|not exactly|sort of|kind of)\b",
            0.7,
        ),
        # Stronger disagreement
        (
            r"\b(hell no|absolutely not|no way|not a chance|forget it|that's wrong|that's incorrect)\b",
            0.95,
        ),
    ],
    "clarification": [
        # Direct clarification requests
        (
            r"\b(what do you mean|so you mean|in other words|just to clarify|to be clear|can you explain|could you elaborate|what's that mean)\b",
            0.95,
        ),
        # Repetition requests
        (
            r"\b(can you repeat|say that again|pardon|excuse me|what was that|didn't catch that)\b",
            0.9,
        ),
        # Specific clarification
        (
            r"\b(you mean|are you saying|so basically|in other words|to clarify|let me understand)\b",
            0.85,
        ),
        # Confusion expressions
        (
            r"\b(i'm confused|i don't understand|not following|lost me|what|huh|sorry)\b",
            0.8,
        ),
    ],
    "feedback": [
        # Positive feedback
        (
            r"\b(that's interesting|nice work|good point|i like that|well done|thanks for that|that's a good idea|excellent|great job|i appreciate that)\b",
            0.9,
        ),
        # Acknowledgment
        (
            r"\b(i see what you mean|understood|noted|duly noted|hmm, interesting|got it|makes sense)\b",
            0.7,
        ),
        # Constructive feedback
        (
            r"\b(that's helpful|useful information|good insight|valuable point|worth considering|food for thought)\b",
            0.8,
        ),
        # Neutral feedback
        (r"\b(interesting|noted|okay|alright|sure|right|got it)\b", 0.6),
    ],
    "response": [
        # Simple responses
        (
            r"^(ok|okay|sure|yeah|no|i see|got it|right|alright|uh-huh|uhuh|yep|yup|mhmm|hmm|fine|alrighty)\b",
            0.85,
        ),
        # Acknowledgment responses
        (r"^(yes|no|maybe|probably|possibly|definitely|absolutely|certainly)\b", 0.8),
        # Non-verbal responses
        (r"^(nod|shaking head|thumbs up|thumbs down|shrug)\s*$", 0.7),
    ],
    "greeting": [
        # Standard greetings
        (
            r"\b(hi|hello|hey|good morning|good afternoon|good evening|greetings|howdy|nice to see you)\b",
            0.95,
        ),
        # Informal greetings
        (
            r"\b(yo|sup|what's up|how's it going|how are you|nice to meet you|pleasure)\b",
            0.85,
        ),
        # Time-based greetings
        (r"\b(good morning|good afternoon|good evening|good night|good day)\b", 0.95),
    ],
    "farewell": [
        # Standard farewells
        (
            r"\b(bye|goodbye|see you|later|talk to you soon|farewell|cheers|catch you later|have a good one)\b",
            0.95,
        ),
        # Informal farewells
        (
            r"\b(see ya|take care|take it easy|peace out|later|cya|talk to you|until next time)\b",
            0.85,
        ),
        # Time-based farewells
        (
            r"\b(good night|have a good day|have a good evening|sleep well|rest well)\b",
            0.9,
        ),
    ],
    "acknowledgement": [
        # Verbal acknowledgments
        (r"^(uh-huh|uhuh|mhm|mm-hmm|yeah|okay|right|i see|got it)\s*$", 0.8),
        # Non-verbal acknowledgments
        (r"^\s*(nod|shaking head|thumbs up|thumbs down|shrug|smile|frown)\s*$", 0.7),
        # Minimal responses
        (r"^(mhm|uh-huh|yeah|okay|right|sure|fine)\s*$", 0.75),
    ],
    "command": [
        # Direct commands
        (
            r"\b(do this|go there|tell me|explain to me|send me|give me|let me know|please|could you please)\b",
            0.9,
        ),
        # Imperative statements
        (r"^\s*(stop|wait|listen|look|come|go|move|run|walk|sit|stand)\s*$", 0.95),
        # Polite commands
        (r"\b(would you mind|could you|can you|please|kindly|if you could)\b", 0.8),
        # Instructions
        (r"\b(follow|obey|complete|finish|start|begin|continue|proceed)\b", 0.85),
    ],
    "apology": [
        # Direct apologies
        (
            r"\b(i'm sorry|my apologies|apologies|excuse me|pardon me|i made a mistake|i was wrong)\b",
            0.95,
        ),
        # Conditional apologies
        (
            r"\b(sorry about that|my bad|my fault|i apologize|forgive me|i regret)\b",
            0.9,
        ),
        # Polite interruptions
        (r"\b(excuse me|pardon|sorry to interrupt|if i may|let me interject)\b", 0.8),
    ],
    "gratitude": [
        # Direct thanks
        (
            r"\b(thanks|thank you|appreciate it|grateful|thankful|owe you one|much obliged)\b",
            0.95,
        ),
        # Specific gratitude
        (
            r"\b(thanks for|thank you for|appreciate you|grateful for|thankful for)\b",
            0.9,
        ),
        # Informal thanks
        (r"\b(thx|tnx|ty|thanks a lot|thanks so much|really appreciate)\b", 0.85),
    ],
    "statement": [
        # Informative statements
        (
            r"\b(i think|i believe|in my opinion|from my perspective|as far as i know|to my knowledge)\b",
            0.8,
        ),
        # Factual statements
        (
            r"\b(the fact is|actually|in fact|indeed|certainly|definitely|obviously)\b",
            0.75,
        ),
        # Personal statements
        (r"\b(i feel|i think|i believe|i know|i understand|i see|i get)\b", 0.7),
    ],
    "interruption": [
        # Direct interruptions
        (r"^\s*(wait|stop|hold on|excuse me|sorry|pardon|let me|but|however)\b", 0.9),
        # Overlapping speech indicators
        (r"\b(interrupting|overlapping|simultaneous|at the same time)\b", 0.8),
    ],
    "hesitation": [
        # Filler words
        (r"\b(um|uh|er|ah|hmm|well|like|you know|i mean|sort of|kind of)\b", 0.8),
        # Pauses and breaks
        (r"\b(pause|silence|break|moment|second|wait)\b", 0.7),
    ],
    "emphasis": [
        # Emphasis markers
        (
            r"\b(really|very|extremely|absolutely|completely|totally|entirely|especially|particularly)\b",
            0.7,
        ),
        # Repetition for emphasis
        (r"\b(very very|really really|so so|much much)\b", 0.8),
    ],
    "uncertainty": [
        # Uncertainty markers
        (
            r"\b(maybe|perhaps|possibly|potentially|might|could|would|should|not sure|uncertain)\b",
            0.8,
        ),
        # Hedging
        (
            r"\b(i think|i guess|i suppose|sort of|kind of|more or less|roughly|approximately)\b",
            0.7,
        ),
    ],
}


def rules_classify_utterance(
    text: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Rule-based classification with enhanced patterns and confidence scoring.

    Args:
        text: The utterance text to classify
        context: Optional context dictionary

    Returns:
        Dictionary with classification results
    """
    text_lower = text.lower().strip()

    # Try rules-based classification with confidence scoring
    best_act = "statement"  # Default fallback
    best_confidence = 0.0
    probabilities = dict.fromkeys(ACT_TYPES, 0.0)

    for act_type, patterns in CUE_PHRASES.items():
        for pattern, confidence in patterns:
            if re.search(pattern, text_lower):
                # Boost confidence for exact matches
                if re.match(pattern, text_lower):
                    confidence += 0.1

                # Context-based confidence adjustments
                if context:
                    confidence = adjust_confidence_for_context(
                        act_type, confidence, context
                    )

                probabilities[act_type] = max(probabilities[act_type], confidence)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_act = act_type

    # If we have a high-confidence match, use it
    if best_confidence >= 0.7:
        return {
            "act_type": best_act,
            "confidence": best_confidence,
            "method": "rules",
            "probabilities": probabilities,
        }

    # Enhanced fallback logic with better heuristics
    fallback_act = enhanced_fallback_classification(text_lower, context)
    fallback_confidence = calculate_act_confidence(text, fallback_act, context)

    probabilities[fallback_act] = fallback_confidence

    return {
        "act_type": fallback_act,
        "confidence": fallback_confidence,
        "method": "rules_fallback",
        "probabilities": probabilities,
    }


def enhanced_fallback_classification(
    text: str, context: dict[str, Any] | None = None
) -> str:
    """
    Enhanced fallback classification using multiple heuristics.

    Args:
        text: Lowercase text to classify
        context: Optional context dictionary

    Returns:
        Classified act type
    """
    # Question detection (improved)
    if text.endswith("?"):
        return "question"

    # Check for question words at the beginning
    question_words = ["what", "why", "how", "when", "where", "who", "which"]
    if any(text.startswith(word) for word in question_words):
        return "question"

    # Suggestion detection
    suggestion_indicators = [
        "let's",
        "we should",
        "i propose",
        "how about",
        "maybe we",
        "consider",
    ]
    if any(indicator in text for indicator in suggestion_indicators):
        return "suggestion"

    # Agreement detection
    agreement_indicators = [
        "yes",
        "okay",
        "sure",
        "sounds good",
        "i agree",
        "absolutely",
        "exactly",
    ]
    if any(indicator in text for indicator in agreement_indicators):
        return "agreement"

    # Disagreement detection
    disagreement_indicators = [
        "no",
        "i disagree",
        "but",
        "however",
        "not really",
        "i don't think",
    ]
    if any(indicator in text for indicator in disagreement_indicators):
        return "disagreement"

    # Gratitude detection
    gratitude_indicators = ["thanks", "thank you", "appreciate", "grateful"]
    if any(indicator in text for indicator in gratitude_indicators):
        return "gratitude"

    # Command detection
    command_indicators = [
        "do this",
        "go there",
        "tell me",
        "explain",
        "send me",
        "give me",
    ]
    if any(indicator in text for indicator in command_indicators):
        return "command"

    # Apology detection
    apology_indicators = ["sorry", "apologize", "excuse me", "pardon"]
    if any(indicator in text for indicator in apology_indicators):
        return "apology"

    # Interruption detection
    interruption_indicators = ["wait", "stop", "hold on", "excuse me"]
    if any(indicator in text for indicator in interruption_indicators):
        return "interruption"

    # Hesitation detection
    hesitation_indicators = ["um", "uh", "er", "ah", "hmm", "well", "like", "you know"]
    if any(indicator in text for indicator in hesitation_indicators):
        return "hesitation"

    # Emphasis detection
    emphasis_indicators = ["really", "very", "extremely", "absolutely", "completely"]
    if any(indicator in text for indicator in emphasis_indicators):
        return "emphasis"

    # Uncertainty detection
    uncertainty_indicators = [
        "maybe",
        "perhaps",
        "possibly",
        "might",
        "could",
        "not sure",
    ]
    if any(indicator in text for indicator in uncertainty_indicators):
        return "uncertainty"

    # Simple acknowledgment detection
    acknowledgment_indicators = ["okay", "right", "sure", "yeah", "uh-huh", "mhm"]
    if any(indicator in text for indicator in acknowledgment_indicators):
        return "acknowledgement"

    # Context-based classification
    if context and context.get("previous_utterances"):
        last_utterance = context["previous_utterances"][-1].lower()

        # If previous utterance was a question, this might be a response
        if "?" in last_utterance:
            return "response"

        # If previous utterance was a statement, this might be feedback
        if len(last_utterance.split()) > 5:
            return "feedback"

    # Default to statement for longer utterances, acknowledgment for shorter ones
    if len(text.split()) > 3:
        return "statement"
    return "acknowledgement"


