"""
Vocabulary Storage Service for TranscriptX Database Integration.

This module provides a service class for storing TF-IDF vocabulary words
with speaker IDs, enabling queryable speaker identification based on
linguistic patterns.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.models import Speaker, SpeakerVocabularyWord

logger = get_logger()


class VocabularyStorageService:
    """
    Service for storing TF-IDF vocabulary words with speaker IDs.

    This service handles:
    - Computing TF-IDF for speaker text
    - Storing vocabulary words as snapshots (snapshot semantics)
    - Finding speakers by vocabulary similarity
    - Managing vocabulary provenance (vectorizer_params_hash, snapshot_version)
    """

    def __init__(self):
        """Initialize the vocabulary storage service."""
        self.session = get_session()

    def _compute_vectorizer_params_hash(self, params: Dict[str, Any]) -> str:
        """Compute hash of vectorizer parameters for provenance."""
        # Sort keys for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True)
        return hashlib.sha256(sorted_params.encode()).hexdigest()[:64]

    def _get_next_snapshot_version(
        self, speaker_id: int, transcript_file_id: Optional[int] = None
    ) -> int:
        """Get the next snapshot version for a speaker+transcript combination."""
        query = self.session.query(SpeakerVocabularyWord).filter(
            SpeakerVocabularyWord.speaker_id == speaker_id
        )

        if transcript_file_id:
            query = query.filter(
                SpeakerVocabularyWord.source_transcript_file_id == transcript_file_id
            )

        existing_versions = (
            query.with_entities(SpeakerVocabularyWord.snapshot_version).distinct().all()
        )

        if existing_versions:
            max_version = max(v[0] for v in existing_versions)
            return max_version + 1

        return 1

    def store_speaker_vocabulary_snapshot(
        self,
        speaker_id: int,
        texts: List[str],
        transcript_file_id: Optional[int] = None,
        source_window: Optional[str] = None,
        vectorizer_params: Optional[Dict[str, Any]] = None,
        analysis_run_id: Optional[str] = None,
        top_n: int = 100,
    ) -> List[SpeakerVocabularyWord]:
        """
        Compute TF-IDF for speaker's text and store vocabulary words as a snapshot.

        **Snapshot Semantics**: Each run produces a discrete vocabulary snapshot per speaker.
        This preserves historical context, enables language drift analysis, and ensures
        reproducibility of speaker identity resolution decisions.

        Uses TfidfVectorizer from sklearn with specified parameters.
        Creates new snapshot version for this speaker+transcript combination.
        Stores vectorizer_params_hash for provenance.

        Args:
            speaker_id: Speaker ID
            texts: List of text strings from speaker
            transcript_file_id: Optional transcript file ID
            source_window: Optional description of source window (e.g., "full_transcript", "last_10_segments")
            vectorizer_params: Optional TfidfVectorizer parameters (defaults to standard config)
            analysis_run_id: Optional UUID linking vocabulary to analysis run
            top_n: Number of top vocabulary words to store (default: 100)

        Returns:
            List of stored vocabulary words for this snapshot

        Raises:
            Exception: For database errors
        """
        try:
            if not texts:
                logger.warning(f"No texts provided for speaker {speaker_id}")
                return []

            # Default vectorizer parameters
            # Adjust min_df/max_df based on number of documents to avoid errors
            n_docs = len(texts)
            if n_docs == 1:
                # For single document, use absolute counts
                min_df = 1
                max_df = 1
            else:
                min_df = 1
                max_df = 0.95

            default_params = {
                "max_features": top_n * 2,  # Get more features than we'll store
                "stop_words": "english",
                "ngram_range": (1, 2),  # Unigrams and bigrams
                "min_df": min_df,
                "max_df": max_df,
            }

            params = vectorizer_params or default_params
            vectorizer_params_hash = self._compute_vectorizer_params_hash(params)

            # Get next snapshot version
            snapshot_version = self._get_next_snapshot_version(
                speaker_id, transcript_file_id
            )

            logger.info(
                f"🔧 Computing TF-IDF vocabulary for speaker {speaker_id} (snapshot version {snapshot_version})"
            )

            # Create vectorizer and compute TF-IDF
            vectorizer = TfidfVectorizer(**params)
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()

            # Get document frequencies from vectorizer
            df = vectorizer.idf_

            # Extract top features across all documents
            # Sum TF-IDF scores across all documents for each feature
            feature_scores = np.array(tfidf_matrix.sum(axis=0)).flatten()

            # Get top N features
            top_indices = np.argsort(feature_scores)[-top_n:][::-1]

            # Store vocabulary words
            vocabulary_words = []
            for idx in top_indices:
                word = feature_names[idx]
                tfidf_score = float(feature_scores[idx])

                # Determine ngram type
                ngram_type = "unigram" if " " not in word else "bigram"

                # Get term frequency (approximate from TF-IDF and IDF)
                # TF-IDF = TF * IDF, so TF = TF-IDF / IDF
                idf_value = df[idx]
                term_freq = int(tfidf_score / idf_value) if idf_value > 0 else 0

                # Document frequency (number of documents containing this term)
                doc_freq = int(np.sum(tfidf_matrix[:, idx] > 0))

                vocab_word = SpeakerVocabularyWord(
                    uuid=str(uuid4()),
                    speaker_id=speaker_id,
                    word=word,
                    tfidf_score=tfidf_score,
                    term_frequency=term_freq,
                    document_frequency=doc_freq,
                    ngram_type=ngram_type,
                    source_transcript_file_id=transcript_file_id,
                    vectorizer_params_hash=vectorizer_params_hash,
                    source_window=source_window,
                    snapshot_version=snapshot_version,
                    analysis_run_id=analysis_run_id,
                )

                vocabulary_words.append(vocab_word)

            # Bulk insert
            self.session.add_all(vocabulary_words)
            self.session.commit()

            logger.info(
                f"✅ Stored {len(vocabulary_words)} vocabulary words for speaker {speaker_id} (snapshot {snapshot_version})"
            )
            return vocabulary_words

        except Exception as e:
            logger.error(
                f"❌ Failed to store vocabulary snapshot for speaker {speaker_id}: {e}"
            )
            if self.session:
                self.session.rollback()
            raise

    def find_speakers_by_vocabulary(
        self,
        text: str,
        top_n: int = 5,
        min_confidence: float = 0.3,
        transcript_file_id: Optional[int] = None,
    ) -> List[Tuple[Speaker, float]]:
        """
        Identify speaker based on vocabulary similarity.

        Computes TF-IDF for input text and matches against stored speaker vocabularies.
        Returns ranked list of potential speakers with confidence scores.

        Args:
            text: Input text to match against speaker vocabularies
            top_n: Number of top matches to return
            min_confidence: Minimum confidence threshold
            transcript_file_id: Optional transcript file ID to limit search

        Returns:
            List of (speaker, confidence_score) tuples, sorted by confidence descending
        """
        try:
            if not text or not text.strip():
                return []

            # Get all vocabulary words (from most recent snapshots)
            query = self.session.query(SpeakerVocabularyWord).join(Speaker)

            if transcript_file_id:
                query = query.filter(
                    SpeakerVocabularyWord.source_transcript_file_id
                    == transcript_file_id
                )

            # Get most recent snapshot for each speaker
            # This is a simplified approach - in production, you might want to
            # explicitly select which snapshot version to use
            vocab_words = query.all()

            if not vocab_words:
                return []

            # Group vocabulary by speaker
            speaker_vocabs: Dict[int, Dict[str, float]] = {}
            for vocab in vocab_words:
                if vocab.speaker_id not in speaker_vocabs:
                    speaker_vocabs[vocab.speaker_id] = {}
                speaker_vocabs[vocab.speaker_id][vocab.word] = vocab.tfidf_score

            # Compute TF-IDF for input text using same parameters
            # For simplicity, use default parameters - in production, you'd want to
            # match the vectorizer_params_hash
            # For single document, adjust max_df
            vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words="english",
                ngram_range=(1, 2),
                min_df=1,
                max_df=1.0,  # Use 1.0 for single document to avoid errors
            )

            # Fit on input text
            input_tfidf = vectorizer.fit_transform([text])
            input_features = vectorizer.get_feature_names_out()
            input_scores = np.array(input_tfidf.toarray()[0])

            # Create feature dict for input
            input_vocab = {
                input_features[i]: input_scores[i] for i in range(len(input_features))
            }

            # Compute cosine similarity with each speaker's vocabulary
            similarities = []
            for speaker_id, speaker_vocab in speaker_vocabs.items():
                # Get common words
                common_words = set(input_vocab.keys()) & set(speaker_vocab.keys())

                if not common_words:
                    continue

                # Compute cosine similarity
                input_vec = np.array([input_vocab.get(w, 0) for w in common_words])
                speaker_vec = np.array([speaker_vocab.get(w, 0) for w in common_words])

                # Cosine similarity
                dot_product = np.dot(input_vec, speaker_vec)
                input_norm = np.linalg.norm(input_vec)
                speaker_norm = np.linalg.norm(speaker_vec)

                if input_norm > 0 and speaker_norm > 0:
                    similarity = dot_product / (input_norm * speaker_norm)
                    if similarity >= min_confidence:
                        speaker = (
                            self.session.query(Speaker)
                            .filter(Speaker.id == speaker_id)
                            .first()
                        )
                        if speaker:
                            similarities.append((speaker, float(similarity)))

            # Sort by confidence descending
            similarities.sort(key=lambda x: x[1], reverse=True)

            return similarities[:top_n]

        except Exception as e:
            logger.error(f"❌ Failed to find speakers by vocabulary: {e}")
            return []

    def close(self):
        """Close the database session."""
        if self.session:
            self.session.close()
