"""
Test data generators for TranscriptX testing.

This module provides comprehensive test data generators for creating realistic
test transcripts, speaker maps, and other test data structures. Generators
support various scenarios including edge cases, large datasets, and special
character handling.
"""

import random
import string
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta


def generate_transcript(
    num_segments: int = 10,
    num_speakers: int = 2,
    min_text_length: int = 10,
    max_text_length: int = 100,
    include_timestamps: bool = True,
    include_words: bool = False,
    start_time: float = 0.0
) -> Dict[str, Any]:
    """
    Generate a realistic transcript for testing.
    
    Args:
        num_segments: Number of segments to generate
        num_speakers: Number of different speakers
        min_text_length: Minimum text length per segment
        max_text_length: Maximum text length per segment
        include_timestamps: Whether to include start/end timestamps
        include_words: Whether to include word-level timestamps
        start_time: Starting timestamp for first segment
        
    Returns:
        Dictionary containing transcript data with segments
    """
    segments = []
    # Use database-driven speaker identification
    speaker_names = ["Alice", "Bob", "Charlie", "Diana", "Eve"][:num_speakers]
    current_time = start_time
    
    sample_texts = [
        "I think we should consider this approach.",
        "That's a great idea, let's explore it further.",
        "What are your thoughts on this matter?",
        "I agree with that assessment completely.",
        "We need to discuss the timeline for this project.",
        "Can you provide more details about that?",
        "I'm not sure I understand the requirements.",
        "Let me clarify what we're trying to achieve.",
        "That makes sense, I see your point.",
        "We should schedule a follow-up meeting."
    ]
    
    for i in range(num_segments):
        speaker_idx = random.randint(0, num_speakers - 1)
        speaker_name = speaker_names[speaker_idx]
        speaker_db_id = speaker_idx + 1
        text = random.choice(sample_texts)
        
        # Ensure text length is within bounds
        if len(text) < min_text_length:
            text += " " + " ".join(random.choices(string.ascii_lowercase, k=min_text_length - len(text)))
        if len(text) > max_text_length:
            text = text[:max_text_length]
        
        segment: Dict[str, Any] = {
            "speaker": speaker_name,
            "speaker_db_id": speaker_db_id,
            "text": text
        }
        
        if include_timestamps:
            duration = random.uniform(2.0, 8.0)
            segment["start"] = current_time
            segment["end"] = current_time + duration
            current_time += duration + random.uniform(0.5, 2.0)  # Add pause between segments
        
        if include_words:
            words = text.split()
            word_segments = []
            word_start = segment.get("start", 0.0)
            word_duration = (segment.get("end", 0.0) - word_start) / len(words) if words else 0.0
            
            for word in words:
                word_segments.append({
                    "word": word,
                    "start": word_start,
                    "end": word_start + word_duration
                })
                word_start += word_duration
            
            segment["words"] = word_segments
        
        segments.append(segment)
    
    return {"segments": segments}


def generate_speaker_map(
    speakers: Optional[List[str]] = None,
    num_speakers: Optional[int] = None,
    use_real_names: bool = True
) -> Dict[str, str]:
    """
    Generate a speaker map for testing (DEPRECATED).
    
    This function is deprecated. Test fixtures should now use segments with
    speaker_db_id instead of speaker_map. This function returns an empty dict
    for backward compatibility.
    
    Args:
        speakers: List of speaker IDs to map (if None, generates IDs)
        num_speakers: Number of speakers to generate (if speakers not provided)
        use_real_names: Whether to use realistic names or generic ones
        
    Returns:
        Empty dictionary (deprecated - use speaker_db_id in segments instead)
    """
    import warnings
    warnings.warn(
        "generate_speaker_map() is deprecated. Use segments with speaker_db_id "
        "instead of speaker_map for testing.",
        DeprecationWarning,
        stacklevel=2
    )
    # Return empty dict for backward compatibility
    return {}


def generate_large_transcript(
    num_segments: int = 1000,
    num_speakers: int = 10
) -> Dict[str, Any]:
    """
    Generate a large transcript for performance testing.
    
    Args:
        num_segments: Number of segments to generate
        num_speakers: Number of different speakers
        
    Returns:
        Large transcript dictionary
    """
    return generate_transcript(
        num_segments=num_segments,
        num_speakers=num_speakers,
        min_text_length=20,
        max_text_length=200
    )


def generate_edge_case_transcript(case: str = "empty") -> Dict[str, Any]:
    """
    Generate edge case transcripts for testing.
    
    Args:
        case: Type of edge case:
            - "empty": Empty segments list
            - "single_segment": Single segment
            - "single_speaker": All segments from one speaker
            - "missing_speaker": Some segments missing speaker field
            - "missing_text": Some segments missing text field
            - "unicode": Unicode and special characters
            - "very_long_text": Very long text segments
            - "overlapping_timestamps": Overlapping timestamps
            - "negative_timestamps": Negative timestamp values
            
    Returns:
        Edge case transcript dictionary
    """
    if case == "empty":
        return {"segments": []}
    
    elif case == "single_segment":
        return {
            "segments": [{
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Single segment transcript.",
                "start": 0.0,
                "end": 2.0
            }]
        }
    
    elif case == "single_speaker":
        return {
            "segments": [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": f"Segment {i}",
                    "start": float(i),
                    "end": float(i + 1)
                }
                for i in range(10)
            ]
        }
    
    elif case == "missing_speaker":
        return {
            "segments": [
                {
                    "speaker": "Alice" if i % 2 == 0 else None,
                    "speaker_db_id": 1 if i % 2 == 0 else None,
                    "text": f"Segment {i}",
                    "start": float(i),
                    "end": float(i + 1)
                }
                for i in range(5)
            ]
        }
    
    elif case == "missing_text":
        return {
            "segments": [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": f"Segment {i}" if i % 2 == 0 else "",
                    "start": float(i),
                    "end": float(i + 1)
                }
                for i in range(5)
            ]
        }
    
    elif case == "unicode":
        return {
            "segments": [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": "Hello 世界! 😊 مرحبا",
                    "start": 0.0,
                    "end": 2.0
                },
                {
                    "speaker": "Bob",
                    "speaker_db_id": 2,
                    "text": "Bonjour! 你好 Здравствуй",
                    "start": 2.0,
                    "end": 4.0
                }
            ]
        }
    
    elif case == "very_long_text":
        long_text = " ".join(["word"] * 1000)  # 1000 words
        return {
            "segments": [{
                "speaker": "SPEAKER_00",
                "text": long_text,
                "start": 0.0,
                "end": 100.0
            }]
        }
    
    elif case == "overlapping_timestamps":
        return {
            "segments": [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": "Overlapping segment 1",
                    "start": 0.0,
                    "end": 5.0
                },
                {
                    "speaker": "Bob",
                    "speaker_db_id": 2,
                    "text": "Overlapping segment 2",
                    "start": 3.0,  # Overlaps with previous
                    "end": 8.0
                }
            ]
        }
    
    elif case == "negative_timestamps":
        return {
            "segments": [{
                "speaker": "SPEAKER_00",
                "text": "Negative timestamp",
                "start": -1.0,
                "end": 1.0
            }]
        }
    
    else:
        raise ValueError(f"Unknown edge case: {case}")


def generate_speaker_profile_data(
    speaker_id: str = "Alice",
    conversation_id: str = "test_conversation_1"
) -> Dict[str, Any]:
    """
    Generate speaker profile data for testing.
    
    Args:
        speaker_id: Speaker identifier
        conversation_id: Conversation identifier
        
    Returns:
        Dictionary containing speaker profile data
    """
    return {
        "speaker_id": speaker_id,
        "conversation_id": conversation_id,
        "behavioral_data": {
            "avg_sentiment": random.uniform(-1.0, 1.0),
            "avg_emotion": random.choice(["joy", "sadness", "anger", "fear", "neutral"]),
            "speaking_rate": random.uniform(100.0, 200.0),
            "interruption_rate": random.uniform(0.0, 0.5),
            "avg_sentence_length": random.uniform(10.0, 30.0),
            "vocabulary_diversity": random.uniform(0.5, 1.0)
        },
        "confidence_score": random.uniform(0.5, 1.0),
        "metadata": {
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "total_segments": random.randint(10, 100)
        }
    }


def generate_analysis_result_data(
    module_name: str = "sentiment",
    conversation_id: str = "test_conversation_1"
) -> Dict[str, Any]:
    """
    Generate analysis result data for testing.
    
    Args:
        module_name: Name of the analysis module
        conversation_id: Conversation identifier
        
    Returns:
        Dictionary containing analysis result data
    """
    result_templates = {
        "sentiment": {
            "overall_sentiment": random.choice(["positive", "negative", "neutral"]),
            "score": random.uniform(-1.0, 1.0),
            "per_speaker": {
                "Alice": {"sentiment": "positive", "score": 0.7},
                "Bob": {"sentiment": "neutral", "score": 0.1}
            }
        },
        "emotion": {
            "dominant_emotion": random.choice(["joy", "sadness", "anger", "fear", "neutral"]),
            "emotion_distribution": {
                "joy": random.uniform(0.0, 1.0),
                "sadness": random.uniform(0.0, 1.0),
                "anger": random.uniform(0.0, 1.0),
                "fear": random.uniform(0.0, 1.0),
                "neutral": random.uniform(0.0, 1.0)
            }
        },
        "ner": {
            "entities": [
                {"text": "New York", "type": "GPE", "start": 10, "end": 18},
                {"text": "John Doe", "type": "PERSON", "start": 25, "end": 33}
            ],
            "entity_counts": {"PERSON": 5, "ORG": 3, "GPE": 2}
        }
    }
    
    return {
        "conversation_id": conversation_id,
        "module_name": module_name,
        "result_data": result_templates.get(module_name, {"data": "test"}),
        "status": "completed",
        "timestamp": datetime.now().isoformat()
    }


def generate_malformed_transcript(variant: str = "missing_segments") -> Dict[str, Any]:
    """
    Generate malformed transcripts for error testing.
    
    Args:
        variant: Type of malformation:
            - "missing_segments": No segments key
            - "invalid_segments": Segments is not a list
            - "invalid_segment": Segment is not a dict
            - "missing_required_fields": Missing required fields
            
    Returns:
        Malformed transcript dictionary
    """
    if variant == "missing_segments":
        return {"metadata": {"duration": 100.0}}
    
    elif variant == "invalid_segments":
        return {"segments": "not a list"}
    
    elif variant == "invalid_segment":
        return {"segments": ["not a dict"]}
    
    elif variant == "missing_required_fields":
        return {
            "segments": [
                {
                    "text": "Missing speaker field"
                }
            ]
        }
    
    else:
        raise ValueError(f"Unknown malformation variant: {variant}")


