"""
Streamlit-based web interface for TranscriptX.

This is a proof-of-concept demonstrating how Streamlit could replace
the Flask/Jinja2 web interface with much simpler code.

To run:
    streamlit run src/transcriptx/web/streamlit_app.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
import re

# Import existing utilities
try:
    from transcriptx.web.utils import (
        list_available_sessions,
        load_transcript_data,
        get_analysis_modules,
        load_analysis_data,
        get_all_sessions_statistics,
    )
    from transcriptx.web.db_utils import (
        get_all_speakers,
        get_speaker_by_id,
        get_speaker_statistics,
        get_speaker_conversations,
    )
    from transcriptx.core.pipeline.module_registry import (
        get_available_modules,
        get_module_info,
    )
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="TranscriptX",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .stat-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .speaker-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


def render_dashboard():
    """Main dashboard page."""
    st.markdown(
        '<div class="main-header">📊 TranscriptX Dashboard</div>',
        unsafe_allow_html=True,
    )

    try:
        # Get statistics
        stats = get_all_sessions_statistics()

        # Display key metrics
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Total Sessions", stats.get("total_sessions", 0))
        with col2:
            st.metric("Total Duration", f"{stats.get('total_duration_hours', 0):.1f}h")
        with col3:
            st.metric("Total Words", f"{stats.get('total_word_count', 0):,}")
        with col4:
            st.metric("Total Speakers", stats.get("total_speakers", 0))
        with col5:
            st.metric("Avg. Analysis", f"{stats.get('average_completion', 0):.0f}%")

        st.divider()

        # Sessions list
        sessions = list_available_sessions()

        if not sessions:
            st.info(
                "No transcript sessions found. Process some transcripts to see them here."
            )
            return

        # Create sessions dataframe
        sessions_df = pd.DataFrame(
            [
                {
                    "Session": s["name"],
                    "Duration (min)": s.get("duration_minutes", 0),
                    "Speakers": s.get("speaker_count", 0),
                    "Words": s.get("word_count", 0),
                    "Modules": s.get("module_count", 0),
                    "Completion": f"{s.get('analysis_completion', 0):.0f}%",
                }
                for s in sessions
            ]
        )

        st.subheader("📋 Available Sessions")

        # Search and filter
        search_term = st.text_input("🔍 Search sessions", key="session_search")
        if search_term:
            sessions_df = sessions_df[
                sessions_df["Session"].str.contains(search_term, case=False, na=False)
            ]

        # Display sessions table with clickable rows
        selected_session = st.selectbox(
            "Select a session to view",
            [""] + [s["name"] for s in sessions],
            key="session_selector",
        )

        if selected_session:
            st.session_state["selected_session"] = selected_session
            st.rerun()

        # Display table
        st.dataframe(sessions_df, width='stretch', hide_index=True)

    except Exception as e:
        st.error(f"Error loading dashboard: {e}")
        st.exception(e)


def render_transcript_viewer():
    """Transcript viewer page."""
    st.markdown(
        '<div class="main-header">📝 Transcript Viewer</div>', unsafe_allow_html=True
    )

    try:
        sessions = list_available_sessions()
        if not sessions:
            st.warning("No sessions available")
            return

        # Session selector
        session_names = [s["name"] for s in sessions]
        selected = st.selectbox(
            "Select Session", session_names, key="transcript_session_selector"
        )

        if not selected:
            return

        # Load transcript
        with st.spinner(f"Loading transcript for {selected}..."):
            transcript_data = load_transcript_data(selected)

        if not transcript_data:
            st.error(f"Transcript not found for session: {selected}")
            return

        # Resolve speaker names from database
        from transcriptx.web.utils import resolve_speaker_names_from_db

        segments = transcript_data.get("segments", [])
        if segments:
            segments = resolve_speaker_names_from_db(segments, selected)

        # Display metadata
        if "metadata" in transcript_data:
            metadata = transcript_data["metadata"]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Duration", f"{metadata.get('duration_seconds', 0) / 60:.1f} min"
                )
            with col2:
                st.metric("Speakers", metadata.get("speaker_count", 0))
            with col3:
                st.metric("Segments", len(transcript_data.get("segments", [])))
            with col4:
                st.metric("Language", metadata.get("language", "Unknown"))

        st.divider()

        if not segments:
            st.info("No segments found in transcript")
            return

        st.subheader(f"Transcript Segments ({len(segments)} total)")

        # Search in transcript
        search_text = st.text_input("🔍 Search in transcript", key="transcript_search")

        # Filter segments
        display_segments = segments
        if search_text:
            display_segments = [
                s for s in segments if search_text.lower() in s.get("text", "").lower()
            ]
            st.caption(f"Showing {len(display_segments)} of {len(segments)} segments")

        # Group segments by speaker changes
        speaker_groups = []
        current_speaker = None
        current_group = []

        for segment in display_segments:
            # Use speaker_display if available, otherwise fall back to speaker
            speaker = segment.get("speaker_display") or segment.get(
                "speaker", "Unknown"
            )

            if speaker != current_speaker:
                # New speaker - save previous group and start new one
                if current_group:
                    speaker_groups.append((current_speaker, current_group))
                current_speaker = speaker
                current_group = [segment]
            else:
                # Same speaker - add to current group
                current_group.append(segment)

        # Don't forget the last group
        if current_group:
            speaker_groups.append((current_speaker, current_group))

        # Display grouped segments by speaker
        for speaker_name, group_segments in speaker_groups:
            # Create expandable section for each speaker
            with st.expander(
                f"🎤 {speaker_name} ({len(group_segments)} segments)", expanded=True
            ):
                for segment in group_segments:
                    text = segment.get("text", "")
                    start = segment.get("start", 0)
                    end = segment.get("end", 0)

                    # Display segment with timestamp
                    st.markdown(f"**⏱️ {start:.1f}s - {end:.1f}s**")
                    st.write(text)

                    # Show additional metadata if available
                    if "sentiment" in segment:
                        sentiment = segment["sentiment"]
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.caption(f"Sentiment: {sentiment.get('compound', 0):.2f}")
                        with col2:
                            st.caption(f"Positive: {sentiment.get('pos', 0):.2f}")
                        with col3:
                            st.caption(f"Negative: {sentiment.get('neg', 0):.2f}")

                    if "emotion" in segment:
                        st.caption(f"Emotion: {segment['emotion']}")

                    st.divider()

        # Analysis modules
        modules = get_analysis_modules(selected)
        if modules:
            st.divider()
            st.subheader("📊 Analysis Modules")
            cols = st.columns(min(len(modules), 4))
            for idx, module in enumerate(modules):
                with cols[idx % 4]:
                    if st.button(module, key=f"module_{module}"):
                        st.session_state["analysis_module"] = module
                        st.session_state["analysis_session"] = selected
                        st.session_state["page"] = "Analysis"
                        st.rerun()

    except Exception as e:
        st.error(f"Error loading transcript: {e}")
        st.exception(e)


def render_analysis_viewer():
    """Analysis module viewer."""
    st.markdown(
        '<div class="main-header">📊 Analysis Viewer</div>', unsafe_allow_html=True
    )

    try:
        session = st.session_state.get("analysis_session")
        module = st.session_state.get("analysis_module")

        if not session or not module:
            st.warning("No analysis selected. Please select from transcript viewer.")
            return

        st.info(f"Viewing {module} analysis for session: **{session}**")

        # Load analysis data
        with st.spinner(f"Loading {module} analysis..."):
            analysis_data = load_analysis_data(session, module)

        if not analysis_data:
            st.error(f"Analysis data not found for {session}/{module}")
            return

        # Display analysis data
        st.json(analysis_data)

        # Back button
        if st.button("← Back to Transcript"):
            st.session_state["page"] = "Transcript"
            st.rerun()

    except Exception as e:
        st.error(f"Error loading analysis: {e}")
        st.exception(e)


def render_speakers_list():
    """Speakers list page."""
    st.markdown('<div class="main-header">👥 Speakers</div>', unsafe_allow_html=True)

    try:
        speakers = get_all_speakers()

        if not speakers:
            st.info("No speakers found in database")
            return

        st.metric("Total Speakers", len(speakers))

        # Create speakers dataframe
        speakers_df = pd.DataFrame(
            [
                {
                    "ID": s.get("id"),
                    "Name": s.get("name", "Unknown"),
                    "Display Name": s.get("display_name", ""),
                    "Email": s.get("email", ""),
                    "Organization": s.get("organization", ""),
                    "Verified": "✓" if s.get("is_verified") else "✗",
                }
                for s in speakers
            ]
        )

        # Search
        search_term = st.text_input("🔍 Search speakers", key="speaker_search")
        if search_term:
            speakers_df = speakers_df[
                speakers_df["Name"].str.contains(search_term, case=False, na=False)
                | speakers_df["Display Name"].str.contains(
                    search_term, case=False, na=False
                )
            ]

        # Display table
        st.dataframe(speakers_df, width='stretch', hide_index=True)

        # Speaker detail selector
        speaker_ids = [s.get("id") for s in speakers if s.get("id")]
        if speaker_ids:
            selected_id = st.selectbox(
                "View Speaker Details",
                [None] + speaker_ids,
                format_func=lambda x: f"Speaker {x}" if x else "Select...",
                key="speaker_detail_selector",
            )

            if selected_id:
                st.session_state["selected_speaker_id"] = selected_id
                st.session_state["page"] = "Speaker Detail"
                st.rerun()

    except Exception as e:
        st.error(f"Error loading speakers: {e}")
        st.exception(e)


def parse_module_markdown(doc_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a module markdown file and extract structured information.

    Args:
        doc_path: Path to the markdown file

    Returns:
        Dictionary with parsed module information or None if parsing fails
    """
    try:
        if not doc_path.exists():
            return None

        content = doc_path.read_text(encoding="utf-8")

        # Extract title (first # heading)
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else None

        # Extract description (content under ## Description)
        desc_match = re.search(
            r"##\s+Description\s*\n\n(.+?)(?=\n##|\Z)", content, re.DOTALL
        )
        description = desc_match.group(1).strip() if desc_match else None

        # Extract capabilities (list items under ## Capabilities)
        caps_match = re.search(
            r"##\s+Capabilities\s*\n\n((?:- .+\n?)+)", content, re.MULTILINE
        )
        capabilities = []
        if caps_match:
            capabilities = [
                line.strip()[2:]  # Remove "- " prefix
                for line in caps_match.group(1).strip().split("\n")
                if line.strip().startswith("-")
            ]

        # Extract category
        cat_match = re.search(
            r"##\s+Category\s*\n\n(.+?)(?=\n##|\Z)", content, re.DOTALL
        )
        category = cat_match.group(1).strip() if cat_match else None

        # Extract dependencies
        deps_match = re.search(
            r"##\s+Dependencies\s*\n\n(.+?)(?=\n##|\Z)", content, re.DOTALL
        )
        dependencies = []
        if deps_match:
            deps_text = deps_match.group(1).strip()
            if deps_text and deps_text.lower() != "none":
                # Extract module names from list or text
                deps_list = re.findall(r"`?(\w+)`?", deps_text)
                dependencies = [
                    d for d in deps_list if d not in ["required", "optional"]
                ]

        return {
            "title": title,
            "description": description,
            "capabilities": capabilities,
            "category": category,
            "dependencies": dependencies,
            "full_content": content,  # Keep full content for potential future use
        }
    except Exception as e:
        st.warning(f"Error parsing {doc_path}: {e}")
        return None


def load_module_docs(module_name: str) -> Optional[Dict[str, Any]]:
    """
    Load module documentation from shared markdown source.

    Args:
        module_name: Name of the module

    Returns:
        Dictionary with module documentation or None if not found
    """
    # Try to find the markdown file relative to the project root
    # Look in multiple possible locations
    possible_paths = [
        Path("docs/source/modules") / f"{module_name}.md",
        Path("../docs/source/modules") / f"{module_name}.md",
        Path("../../docs/source/modules") / f"{module_name}.md",
    ]

    # Also try relative to the script location
    script_dir = Path(__file__).parent.parent.parent.parent
    possible_paths.append(
        script_dir / "docs" / "source" / "modules" / f"{module_name}.md"
    )

    for doc_path in possible_paths:
        if doc_path.exists():
            return parse_module_markdown(doc_path)

    return None


def render_speaker_detail():
    """Speaker detail page."""
    st.markdown(
        '<div class="main-header">👤 Speaker Details</div>', unsafe_allow_html=True
    )

    try:
        speaker_id = st.session_state.get("selected_speaker_id")
        if not speaker_id:
            st.warning("No speaker selected")
            return

        # Load speaker data
        speaker = get_speaker_by_id(speaker_id)
        if not speaker:
            st.error(f"Speaker {speaker_id} not found")
            return

        # Display speaker info
        col1, col2 = st.columns([1, 3])

        with col1:
            st.subheader(speaker.get("name", "Unknown"))
            if speaker.get("display_name"):
                st.caption(speaker.get("display_name"))
            if speaker.get("email"):
                st.write(f"📧 {speaker.get('email')}")
            if speaker.get("organization"):
                st.write(f"🏢 {speaker.get('organization')}")
            if speaker.get("role"):
                st.write(f"💼 {speaker.get('role')}")

        with col2:
            # Statistics
            try:
                stats = get_speaker_statistics(speaker_id)
                if stats:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Total Words", f"{stats.get('total_word_count', 0):,}"
                        )
                    with col2:
                        st.metric("Segments", stats.get("total_segment_count", 0))
                    with col3:
                        st.metric(
                            "Speaking Time",
                            f"{stats.get('total_speaking_time', 0) / 60:.1f} min",
                        )
                    with col4:
                        st.metric(
                            "Avg Rate",
                            f"{stats.get('average_speaking_rate', 0):.1f} wpm",
                        )
            except Exception as e:
                st.warning(f"Could not load statistics: {e}")

        # Conversations
        try:
            conversations = get_speaker_conversations(speaker_id)
            if conversations:
                st.subheader("💬 Conversations")
                for conv in conversations:
                    with st.expander(f"Session: {conv.get('session_name', 'Unknown')}"):
                        st.write(f"Words: {conv.get('word_count', 0):,}")
                        st.write(
                            f"Duration: {conv.get('speaking_time', 0) / 60:.1f} min"
                        )
        except Exception as e:
            st.warning(f"Could not load conversations: {e}")

        # Back button
        if st.button("← Back to Speakers"):
            st.session_state["page"] = "Speakers"
            st.rerun()

    except Exception as e:
        st.error(f"Error loading speaker details: {e}")
        st.exception(e)


def render_documentation():
    """Documentation page explaining analysis modules."""
    st.markdown(
        '<div class="main-header">📚 Analysis Modules Documentation</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    This page provides detailed information about each analysis module available in TranscriptX.
    Each module performs specialized analysis on transcript data to extract insights and patterns.
    """
    )

    # Add link to full Sphinx documentation
    st.info(
        "📚 For comprehensive documentation including API reference, configuration guides, and advanced topics, see the [full Sphinx documentation](https://transcriptx.readthedocs.io/) or build locally with `make -C docs html`"
    )

    try:
        # Get all available modules
        modules = get_available_modules()

        if not modules:
            st.warning("No analysis modules found.")
            return

        st.metric("Total Modules", len(modules))
        st.divider()

        # Load module descriptions from markdown files
        module_descriptions = {}
        for module_name in modules:
            doc_info = load_module_docs(module_name)
            if doc_info:
                module_descriptions[module_name] = doc_info

        # Fallback: if markdown files not found, use module registry info
        if not module_descriptions:
            st.warning(
                "⚠️ Module documentation files not found. Using basic module information."
            )
            for module_name in modules:
                module_info = get_module_info(module_name)
                if module_info:
                    module_descriptions[module_name] = {
                        "title": module_info.description,
                        "description": module_info.description,
                        "capabilities": [],
                        "category": module_info.category,
                        "dependencies": module_info.dependencies,
                    }

        # Legacy hardcoded descriptions as ultimate fallback (should not be needed)
        legacy_descriptions = {
            "acts": {
                "title": "Dialogue Act Classification (ACTS)",
                "description": "Classifies speech acts in conversations, identifying questions, statements, commands, agreements, and disagreements. Tracks action items and commitments, and analyzes conversation flow patterns.",
                "capabilities": [
                    "Classifies speech acts (questions, statements, commands)",
                    "Identifies agreement/disagreement patterns",
                    "Tracks action items and commitments",
                    "Analyzes conversation flow and structure",
                ],
            },
            "conversation_loops": {
                "title": "Conversation Loop Detection",
                "description": "Detects repetitive conversation patterns and loops where similar topics or discussions recur throughout the session.",
                "capabilities": [
                    "Identifies repetitive conversation patterns",
                    "Detects conversation loops",
                    "Tracks recurring topics",
                ],
            },
            "contagion": {
                "title": "Emotional Contagion Detection",
                "description": "Analyzes how emotions spread between speakers during conversations, detecting emotional contagion patterns.",
                "capabilities": [
                    "Detects emotional contagion between speakers",
                    "Tracks emotion propagation patterns",
                    "Requires emotion analysis to run first",
                ],
                "dependencies": ["emotion"],
            },
            "emotion": {
                "title": "Emotion Analysis",
                "description": "Detects specific emotions in speech such as joy, sadness, anger, fear, and surprise. Provides emotion intensity scores and tracks emotional changes over time.",
                "capabilities": [
                    "Detects specific emotions (joy, sadness, anger, fear, etc.)",
                    "Provides emotion intensity scores",
                    "Tracks emotional changes over time",
                    "Speaker-specific emotion patterns",
                ],
            },
            "entity_sentiment": {
                "title": "Entity-based Sentiment Analysis",
                "description": "Combines named entity recognition with sentiment analysis to determine sentiment associated with specific entities (people, organizations, places).",
                "capabilities": [
                    "Entity-focused sentiment analysis",
                    "Sentiment attribution to specific entities",
                    "Tracks entity-sentiment relationships",
                ],
                "dependencies": ["ner", "sentiment"],
            },
            "interactions": {
                "title": "Speaker Interaction Analysis",
                "description": "Analyzes speaker interactions including interruptions, turn-taking patterns, and speaker networks.",
                "capabilities": [
                    "Analyzes speaker interruptions",
                    "Tracks turn-taking patterns",
                    "Maps speaker interaction networks",
                    "Identifies interaction dynamics",
                ],
            },
            "ner": {
                "title": "Named Entity Recognition (NER)",
                "description": "Identifies and extracts named entities such as people, places, organizations, dates, and other important entities from the transcript.",
                "capabilities": [
                    "Identifies people, places, organizations, dates",
                    "Provides entity frequency analysis",
                    "Geocoding support for locations",
                    "Tracks entity relationships",
                ],
            },
            "semantic_similarity": {
                "title": "Semantic Similarity Analysis",
                "description": "Measures similarity between utterances using semantic embeddings. Identifies repetitive content and tracks concept evolution.",
                "capabilities": [
                    "Measures similarity between utterances",
                    "Identifies repetitive content",
                    "Tracks concept evolution",
                    "Provides similarity matrices",
                ],
            },
            "semantic_similarity_advanced": {
                "title": "Advanced Semantic Similarity",
                "description": "Enhanced semantic similarity analysis with integration of other analysis modules for more sophisticated similarity detection.",
                "capabilities": [
                    "Advanced similarity detection",
                    "Integration with other analysis modules",
                    "More sophisticated repetition detection",
                ],
            },
            "sentiment": {
                "title": "Sentiment Analysis",
                "description": "Analyzes the emotional tone of speech using VADER sentiment analysis. Provides sentiment scores (positive, negative, neutral) and tracks sentiment changes over time.",
                "capabilities": [
                    "Analyzes emotional tone of speech",
                    "Provides sentiment scores (positive, negative, neutral)",
                    "Tracks sentiment changes over time",
                    "Speaker-specific sentiment analysis",
                ],
            },
            "stats": {
                "title": "Statistical Analysis",
                "description": "Provides comprehensive summary statistics and metrics about the transcript including word counts, speaking time, and other quantitative measures.",
                "capabilities": [
                    "Summary statistics and metrics",
                    "Word counts and speaking time",
                    "Quantitative transcript analysis",
                ],
            },
            "topic_modeling": {
                "title": "Topic Modeling",
                "description": "Identifies main topics in the conversation using LDA and NMF algorithms. Extracts keywords for each topic and shows topic evolution throughout the session.",
                "capabilities": [
                    "Identifies main topics in conversation",
                    "Extracts keywords for each topic",
                    "Shows topic evolution throughout session",
                    "Provides topic-sentence mapping",
                ],
            },
            "transcript_output": {
                "title": "Transcript Output Generation",
                "description": "Generates human-readable transcript output with formatting and structure.",
                "capabilities": [
                    "Generates formatted transcript output",
                    "Human-readable transcript generation",
                ],
            },
            "understandability": {
                "title": "Understandability Analysis",
                "description": "Analyzes the understandability and readability of the transcript, measuring text quality and clarity.",
                "capabilities": [
                    "Measures text understandability",
                    "Readability analysis",
                    "Text quality assessment",
                ],
            },
            "wordclouds": {
                "title": "Word Cloud Generation",
                "description": "Generates word clouds from transcript text using various approaches to visualize frequently used words.",
                "capabilities": [
                    "Generates word clouds",
                    "Visualizes frequently used words",
                    "Multiple generation approaches",
                ],
            },
            "tics": {
                "title": "Verbal Tics Analysis",
                "description": "Detects verbal tics, filler words, and repetitive speech patterns in the transcript.",
                "capabilities": [
                    "Detects verbal tics and filler words",
                    "Identifies repetitive speech patterns",
                    "Analyzes speech habits",
                ],
            },
            "temporal_dynamics": {
                "title": "Temporal Dynamics Analysis",
                "description": "Analyzes how conversation patterns, topics, and dynamics change over time throughout the session.",
                "capabilities": [
                    "Tracks temporal changes in conversation",
                    "Analyzes dynamics over time",
                    "Pattern evolution analysis",
                ],
            },
            "qa_analysis": {
                "title": "Question-Answer Pairing and Response Quality",
                "description": "Identifies question-answer pairs in conversations and analyzes the quality of responses.",
                "capabilities": [
                    "Identifies question-answer pairs",
                    "Analyzes response quality",
                    "Tracks Q&A patterns",
                ],
                "dependencies": ["acts"],
            },
        }

        # Merge legacy descriptions if markdown loading failed for specific modules
        for module_name in modules:
            if (
                module_name not in module_descriptions
                and module_name in legacy_descriptions
            ):
                module_descriptions[module_name] = legacy_descriptions[module_name]

        # Group modules by category
        categories = {"light": [], "medium": [], "heavy": []}

        for module_name in sorted(modules):
            module_info = get_module_info(module_name)
            if module_info:
                category = module_info.category
                categories[category].append(module_name)

        # Display modules by category
        category_labels = {
            "light": "⚡ Light (Fast Processing)",
            "medium": "⚖️ Medium (Moderate Processing)",
            "heavy": "🔥 Heavy (Intensive Processing)",
        }

        for category in ["light", "medium", "heavy"]:
            if categories[category]:
                st.subheader(category_labels[category])

                for module_name in categories[category]:
                    module_info = get_module_info(module_name)
                    desc_info = module_descriptions.get(module_name, {})

                    # Get title, preferring markdown title, then module description
                    title = desc_info.get("title") or (
                        module_info.description if module_info else module_name
                    )

                    with st.expander(f"**{title}**", expanded=False):
                        st.markdown(f"**Module Name:** `{module_name}`")
                        st.markdown(f"**Category:** {category.capitalize()}")

                        # Description
                        description = desc_info.get("description")
                        if description:
                            st.markdown(f"**Description:** {description}")
                        elif module_info:
                            st.markdown(f"**Description:** {module_info.description}")

                        # Capabilities
                        capabilities = desc_info.get("capabilities", [])
                        if capabilities:
                            st.markdown("**Capabilities:**")
                            for capability in capabilities:
                                st.markdown(f"- {capability}")

                        # Dependencies - use from module_info (source of truth) but show from docs if available
                        dependencies = module_info.dependencies if module_info else []
                        if dependencies:
                            deps = ", ".join([f"`{dep}`" for dep in dependencies])
                            st.markdown(f"**Dependencies:** {deps}")
                            st.info(
                                f"⚠️ This module requires the following modules to run first: {', '.join(dependencies)}"
                            )
                        else:
                            st.markdown("**Dependencies:** None")

                        # Link to full documentation
                        st.markdown(
                            f"📖 [View full documentation for {module_name}](https://transcriptx.readthedocs.io/en/latest/user-guide/analysis-modules.html)"
                        )

                st.divider()

        # Additional information section
        st.subheader("📖 Additional Information")

        with st.expander("Module Categories Explained"):
            st.markdown(
                """
            **Light Modules:**
            - Fast processing with minimal computational requirements
            - Typically use rule-based or simple statistical methods
            - Recommended for quick analysis
            
            **Medium Modules:**
            - Moderate processing time and computational requirements
            - May use machine learning models or more complex algorithms
            - Balance between speed and depth of analysis
            
            **Heavy Modules:**
            - Intensive processing with higher computational requirements
            - Often use transformer models or complex ML algorithms
            - Provide deeper insights but require more time and resources
            """
            )

        with st.expander("Module Dependencies"):
            st.markdown(
                """
            Some modules depend on the output of other modules. For example:
            - **contagion** requires **emotion** to run first
            - **entity_sentiment** requires both **ner** and **sentiment**
            - **qa_analysis** requires **acts**
            
            The analysis pipeline automatically handles these dependencies and runs modules in the correct order.
            """
            )

        with st.expander("Using Modules"):
            st.markdown(
                """
            To use these modules:
            1. Process a transcript using the CLI or API
            2. Select which modules to run (or use all modules)
            3. View the results in the Transcript Viewer or Analysis pages
            
            Modules can be configured in the configuration file to customize their behavior.
            
            For detailed configuration options, usage examples, and output formats, see the [full Sphinx documentation](https://transcriptx.readthedocs.io/).
            """
            )

    except Exception as e:
        st.error(f"Error loading documentation: {e}")
        st.exception(e)


# Main app
def main():
    """Main application entry point."""

    # Initialize session state
    if "page" not in st.session_state:
        st.session_state["page"] = "Dashboard"

    # Sidebar navigation
    with st.sidebar:
        st.title("🎙️ TranscriptX")
        st.divider()

        page = st.radio(
            "Navigation",
            ["Dashboard", "Transcript", "Speakers", "Documentation"],
            index=(
                ["Dashboard", "Transcript", "Speakers", "Documentation"].index(
                    st.session_state["page"]
                )
                if st.session_state["page"]
                in ["Dashboard", "Transcript", "Speakers", "Documentation"]
                else 0
            ),
            key="nav_radio",
        )

        st.session_state["page"] = page

    # Route to appropriate page
    if page == "Dashboard":
        render_dashboard()
    elif page == "Transcript":
        render_transcript_viewer()
    elif page == "Analysis":
        render_analysis_viewer()
    elif page == "Speakers":
        render_speakers_list()
    elif page == "Speaker Detail":
        render_speaker_detail()
    elif page == "Documentation":
        render_documentation()


if __name__ == "__main__":
    main()
