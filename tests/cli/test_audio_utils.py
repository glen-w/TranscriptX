"""
Tests for audio utility functions.

This module tests audio playback, format checking, ffplay integration,
and audio conversion utilities.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

audio_utils = pytest.importorskip("transcriptx.cli.audio_utils")
check_ffmpeg_available = audio_utils.check_ffmpeg_available
check_ffplay_available = audio_utils.check_ffplay_available
get_audio_duration = audio_utils.get_audio_duration
convert_wav_to_mp3 = audio_utils.convert_wav_to_mp3
assess_audio_noise = audio_utils.assess_audio_noise
check_audio_compliance = audio_utils.check_audio_compliance
normalize_loudness = audio_utils.normalize_loudness
denoise_audio = audio_utils.denoise_audio
apply_preprocessing = audio_utils.apply_preprocessing
from transcriptx.core.utils.config import AudioPreprocessingConfig


class TestCheckFFmpegAvailable:
    """Tests for check_ffmpeg_available function."""
    
    @patch('transcriptx.cli.audio_utils._find_ffmpeg_path')
    @patch('transcriptx.cli.audio_utils.subprocess.run')
    def test_ffmpeg_available(self, mock_run, mock_find):
        """Test when ffmpeg is available."""
        mock_find.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0)
        
        available, error = check_ffmpeg_available()
        
        assert available is True
        assert error is None
    
    @patch('transcriptx.cli.audio_utils._find_ffmpeg_path')
    def test_ffmpeg_not_available(self, mock_find):
        """Test when ffmpeg is not available."""
        mock_find.return_value = None
        
        available, error = check_ffmpeg_available()
        
        assert available is False
        assert error is not None
    
    @patch('transcriptx.cli.audio_utils._find_ffmpeg_path')
    @patch('transcriptx.cli.audio_utils.subprocess.run')
    def test_ffmpeg_check_fails(self, mock_run, mock_find):
        """Test when ffmpeg check fails."""
        mock_find.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=1)
        
        available, error = check_ffmpeg_available()
        
        assert available is False
        assert error is not None


class TestCheckFFplayAvailable:
    """Tests for check_ffplay_available function."""
    
    @patch('transcriptx.cli.audio_utils.shutil.which')
    def test_ffplay_available(self, mock_which):
        """Test when ffplay is available."""
        mock_which.return_value = "/usr/bin/ffplay"
        
        available, error = check_ffplay_available()
        
        assert available is True
        assert error is None
    
    @patch('transcriptx.cli.audio_utils.shutil.which')
    def test_ffplay_not_available(self, mock_which):
        """Test when ffplay is not available."""
        mock_which.return_value = None
        
        available, error = check_ffplay_available()
        
        assert available is False
        assert error is not None


class TestGetAudioDuration:
    """Tests for get_audio_duration function."""
    
    @patch('transcriptx.cli.audio_utils.subprocess.run')
    def test_get_audio_duration_success(self, mock_run, tmp_path):
        """Test getting audio duration successfully."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Duration: 00:01:30.00"
        )
        
        duration = get_audio_duration(audio_file)
        
        # Should return duration in seconds
        assert duration is not None
        assert isinstance(duration, (int, float))
    
    @patch('transcriptx.cli.audio_utils.subprocess.run')
    def test_get_audio_duration_failure(self, mock_run, tmp_path):
        """Test when getting duration fails."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        mock_run.return_value = MagicMock(returncode=1)
        
        duration = get_audio_duration(audio_file)
        
        # Should return None on failure
        assert duration is None
    
    def test_get_audio_duration_file_not_found(self, tmp_path):
        """Test when audio file doesn't exist."""
        audio_file = tmp_path / "nonexistent.mp3"
        
        duration = get_audio_duration(audio_file)
        
        # Should return None
        assert duration is None


class TestConvertWAVToMP3:
    """Tests for convert_wav_to_mp3 function."""
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_convert_wav_to_mp3_success(self, mock_audio_segment, tmp_path):
        """Test successful WAV to MP3 conversion."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        mock_segment = MagicMock()
        mock_audio_segment.from_wav.return_value = mock_segment
        mock_segment.export.return_value = None
        
        result = convert_wav_to_mp3(wav_file, output_dir)
        
        # Should return output path
        assert result is not None
        assert result.suffix == ".mp3"
        mock_audio_segment.from_wav.assert_called_once()
        mock_segment.export.assert_called_once()
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', False)
    def test_convert_wav_to_mp3_pydub_not_available(self, tmp_path):
        """Test when pydub is not available."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        with pytest.raises((ImportError, RuntimeError)):
            convert_wav_to_mp3(wav_file, output_dir)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_convert_wav_to_mp3_decode_error(self, mock_audio_segment, tmp_path):
        """Test when WAV file cannot be decoded."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"invalid wav")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        from transcriptx.cli.audio_utils import CouldntDecodeError
        mock_audio_segment.from_wav.side_effect = CouldntDecodeError("Cannot decode")
        
        with pytest.raises(CouldntDecodeError):
            convert_wav_to_mp3(wav_file, output_dir)


class TestAssessAudioNoise:
    """Tests for assess_audio_noise function."""
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_assess_audio_noise_success(self, mock_audio_segment, tmp_path):
        """Test successful audio noise assessment."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")
        
        # Create mock audio segment
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        mock_segment.sample_width = 2
        mock_segment.get_array_of_samples.return_value = [1000, 2000, 3000, 4000]
        mock_audio_segment.from_file.return_value = mock_segment
        
        assessment = assess_audio_noise(audio_file)
        
        assert "noise_level" in assessment
        assert "suggested_steps" in assessment
        assert "confidence" in assessment
        assert "metrics" in assessment
        assert assessment["noise_level"] in ["low", "medium", "high"]
        assert isinstance(assessment["suggested_steps"], list)
        assert 0.0 <= assessment["confidence"] <= 1.0
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', False)
    def test_assess_audio_noise_pydub_not_available(self, tmp_path):
        """Test when pydub is not available."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")
        
        assessment = assess_audio_noise(audio_file)
        
        # Should return default assessment
        assert assessment["noise_level"] == "low"
        assert assessment["suggested_steps"] == []
        assert assessment["confidence"] == 0.0
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_assess_audio_noise_stereo(self, mock_audio_segment, tmp_path):
        """Test assessment with stereo audio."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")
        
        mock_segment = MagicMock()
        mock_segment.channels = 2
        mock_segment.frame_rate = 44100
        mock_segment.sample_width = 2
        mock_segment.get_array_of_samples.return_value = [1000, 2000, 3000, 4000]
        mock_audio_segment.from_file.return_value = mock_segment
        
        assessment = assess_audio_noise(audio_file)
        
        assert "mono" in assessment["suggested_steps"] or "resample" in assessment["suggested_steps"]
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_assess_audio_noise_error_handling(self, mock_audio_segment, tmp_path):
        """Test error handling in assessment."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")
        
        mock_audio_segment.from_file.side_effect = Exception("Decode error")
        
        assessment = assess_audio_noise(audio_file)
        
        # Should return default assessment on error
        assert assessment["noise_level"] == "low"
        assert assessment["confidence"] == 0.0


class TestCheckAudioCompliance:
    """Tests for check_audio_compliance function."""
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_check_audio_compliance_compliant(self, mock_audio_segment, tmp_path):
        """Test compliance check for compliant audio."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")
        
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        mock_segment.sample_width = 2
        mock_segment.get_array_of_samples.return_value = [1000, 2000, 3000, 4000]
        mock_audio_segment.from_file.return_value = mock_segment
        
        config = AudioPreprocessingConfig()
        compliance = check_audio_compliance(audio_file, config)
        
        assert "is_compliant" in compliance
        assert "details" in compliance
        assert "missing_requirements" in compliance
        assert isinstance(compliance["missing_requirements"], list)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_check_audio_compliance_not_mono(self, mock_audio_segment, tmp_path):
        """Test compliance check for stereo audio."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")
        
        mock_segment = MagicMock()
        mock_segment.channels = 2
        mock_segment.frame_rate = 16000
        mock_segment.sample_width = 2
        mock_segment.get_array_of_samples.return_value = [1000, 2000, 3000, 4000]
        mock_audio_segment.from_file.return_value = mock_segment
        
        config = AudioPreprocessingConfig()
        compliance = check_audio_compliance(audio_file, config)
        
        assert "mono" in compliance["missing_requirements"]
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_check_audio_compliance_wrong_sample_rate(self, mock_audio_segment, tmp_path):
        """Test compliance check for wrong sample rate."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")
        
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 44100
        mock_segment.sample_width = 2
        mock_segment.get_array_of_samples.return_value = [1000, 2000, 3000, 4000]
        mock_audio_segment.from_file.return_value = mock_segment
        
        config = AudioPreprocessingConfig()
        compliance = check_audio_compliance(audio_file, config)
        
        assert "16kHz" in compliance["missing_requirements"]
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', False)
    def test_check_audio_compliance_pydub_not_available(self, tmp_path):
        """Test when pydub is not available."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")
        
        compliance = check_audio_compliance(audio_file)
        
        assert compliance["is_compliant"] is False
        assert compliance["missing_requirements"] == []


class TestNormalizeLoudness:
    """Tests for normalize_loudness function."""
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.PYLoudnorm_AVAILABLE', False)
    @patch('transcriptx.cli.audio_utils.SOUNDFILE_AVAILABLE', False)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_normalize_loudness_fallback(self, mock_audio_segment):
        """Test loudness normalization with RMS fallback."""
        mock_segment = MagicMock()
        mock_segment.dBFS = -30.0
        mock_segment.apply_gain.return_value = mock_segment
        
        result = normalize_loudness(mock_segment, target_lufs=-18.0)
        
        # Should return processed audio (may use apply_gain or other methods)
        assert result is not None
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', False)
    def test_normalize_loudness_pydub_not_available(self):
        """Test when pydub is not available."""
        mock_audio = MagicMock()
        
        result = normalize_loudness(mock_audio)
        
        # Should return original audio unchanged
        assert result is mock_audio


class TestDenoiseAudio:
    """Tests for denoise_audio function."""
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.NOISEREDUCE_AVAILABLE', False)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_denoise_audio_fallback(self, mock_audio_segment):
        """Test denoising with spectral gating fallback."""
        mock_segment = MagicMock()
        mock_segment.frame_rate = 16000
        mock_segment.channels = 1
        mock_segment.get_array_of_samples.return_value = [1000, 2000, 3000, 4000]
        mock_segment._spawn.return_value = mock_segment
        
        result = denoise_audio(mock_segment, strength="medium")
        
        # Should return processed audio
        assert result is not None
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', False)
    def test_denoise_audio_pydub_not_available(self):
        """Test when pydub is not available."""
        mock_audio = MagicMock()
        
        result = denoise_audio(mock_audio)
        
        # Should return original audio unchanged
        assert result is mock_audio


class TestGetEffectiveMode:
    """Tests for _get_effective_mode helper function."""
    
    def test_effective_mode_selected(self):
        """Test that 'selected' mode uses per-step mode."""
        from transcriptx.cli.audio_utils import _get_effective_mode
        
        assert _get_effective_mode("selected", "auto") == "auto"
        assert _get_effective_mode("selected", "suggest") == "suggest"
        assert _get_effective_mode("selected", "off") == "off"
    
    def test_effective_mode_global_override(self):
        """Test that global modes override per-step modes."""
        from transcriptx.cli.audio_utils import _get_effective_mode
        
        # Global "auto" should override any per-step mode
        assert _get_effective_mode("auto", "off") == "auto"
        assert _get_effective_mode("auto", "suggest") == "auto"
        
        # Global "suggest" should override any per-step mode
        assert _get_effective_mode("suggest", "off") == "suggest"
        assert _get_effective_mode("suggest", "auto") == "suggest"
        
        # Global "off" should override any per-step mode
        assert _get_effective_mode("off", "auto") == "off"
        assert _get_effective_mode("off", "suggest") == "off"


class TestApplyPreprocessing:
    """Tests for apply_preprocessing function."""
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_mono_conversion(self, mock_audio_segment):
        """Test preprocessing with mono conversion in auto mode."""
        mock_segment = MagicMock()
        mock_segment.channels = 2
        mock_segment.frame_rate = 16000  # Already at target rate to avoid resampling
        mock_segment.set_channels.return_value = mock_segment
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            convert_to_mono="auto",
            downsample="off",
            normalize_mode="off"
        )
        
        result, steps = apply_preprocessing(mock_segment, config)
        
        assert "mono" in steps
        mock_segment.set_channels.assert_called_with(1)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_downsample(self, mock_audio_segment):
        """Test preprocessing with downsampling in auto mode."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 44100
        mock_segment.set_frame_rate.return_value = mock_segment
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            downsample="auto",
            target_sample_rate=16000,
            normalize_mode="off"
        )
        
        result, steps = apply_preprocessing(mock_segment, config)
        
        # Check for resample step (actual name is "resample_to_16000hz")
        assert any("resample" in step for step in steps)
        mock_segment.set_frame_rate.assert_called_with(16000)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_normalize(self, mock_audio_segment):
        """Test preprocessing with normalization in auto mode."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        mock_segment.dBFS = -30.0
        mock_segment.apply_gain.return_value = mock_segment
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            normalize_mode="auto",
            target_lufs=-18.0,
            limiter_enabled=True
        )
        
        with patch('transcriptx.cli.audio_utils.normalize_loudness', return_value=mock_segment):
            result, steps = apply_preprocessing(mock_segment, config)
            
            # Check for normalize step (actual name is "normalize_-18.0lufs")
            assert any("normalize" in step for step in steps)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_highpass(self, mock_audio_segment):
        """Test preprocessing with high-pass filter in auto mode."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        mock_segment.high_pass_filter.return_value = mock_segment
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            highpass_mode="auto",
            highpass_cutoff=80,
            normalize_mode="off"
        )
        
        result, steps = apply_preprocessing(mock_segment, config)
        
        # Check for highpass step (actual name is "highpass_80hz")
        assert any("highpass" in step for step in steps)
        mock_segment.high_pass_filter.assert_called_with(80)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_denoise(self, mock_audio_segment):
        """Test preprocessing with denoising in auto mode."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        mock_segment.get_array_of_samples.return_value = [1000, 2000, 3000, 4000]
        mock_segment._spawn.return_value = mock_segment
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            denoise_mode="auto",
            denoise_strength="medium",
            normalize_mode="off"
        )
        
        with patch('transcriptx.cli.audio_utils.denoise_audio', return_value=mock_segment):
            result, steps = apply_preprocessing(mock_segment, config)
            
            # Check for denoise step (actual name is "denoise_medium")
            assert any("denoise" in step for step in steps)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_suggest_mode_with_decisions(self, mock_audio_segment):
        """Test preprocessing in suggest mode with preprocessing_decisions."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        mock_segment.high_pass_filter.return_value = mock_segment
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            highpass_mode="suggest",
            highpass_cutoff=80,
            normalize_mode="off"
        )
        
        # Provide decisions for suggest mode
        preprocessing_decisions = {
            "highpass": True,  # User confirmed
            "denoise": False,  # User declined
        }
        
        result, steps = apply_preprocessing(mock_segment, config, None, preprocessing_decisions)
        
        # Should apply highpass because decision is True
        assert any("highpass" in step for step in steps)
        mock_segment.high_pass_filter.assert_called_with(80)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_suggest_mode_no_decisions(self, mock_audio_segment):
        """Test preprocessing in suggest mode without decisions (should skip)."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            highpass_mode="suggest",
            highpass_cutoff=80,
            normalize_mode="off"
        )
        
        # No decisions provided
        result, steps = apply_preprocessing(mock_segment, config, None, None)
        
        # Should skip highpass because no decision provided
        assert not any("highpass" in step for step in steps)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_off_mode(self, mock_audio_segment):
        """Test preprocessing in off mode (should skip)."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            highpass_mode="off",
            highpass_cutoff=80,
            normalize_mode="off"
        )
        
        result, steps = apply_preprocessing(mock_segment, config)
        
        # Should skip highpass because mode is "off"
        assert not any("highpass" in step for step in steps)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_global_mode_auto(self, mock_audio_segment):
        """Test that global mode="auto" overrides per-step settings."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        mock_segment.high_pass_filter.return_value = mock_segment
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="auto",  # Global override
            highpass_mode="off",  # Per-step setting (should be overridden)
            highpass_cutoff=80,
            normalize_mode="off"
        )
        
        result, steps = apply_preprocessing(mock_segment, config)
        
        # Should apply highpass because global mode="auto" overrides per-step "off"
        assert any("highpass" in step for step in steps)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_global_mode_off(self, mock_audio_segment):
        """Test that global mode="off" overrides per-step settings."""
        mock_segment = MagicMock()
        mock_segment.channels = 1
        mock_segment.frame_rate = 16000
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="off",  # Global override
            highpass_mode="auto",  # Per-step setting (should be overridden)
            highpass_cutoff=80,
            normalize_mode="auto"
        )
        
        result, steps = apply_preprocessing(mock_segment, config)
        
        # Should skip all preprocessing because global mode="off"
        assert not any("highpass" in step for step in steps)
        assert not any("normalize" in step for step in steps)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', True)
    @patch('transcriptx.cli.audio_utils.AudioSegment')
    def test_apply_preprocessing_auto_mode_checks_need(self, mock_audio_segment):
        """Test that auto mode only applies steps when needed."""
        mock_segment = MagicMock()
        mock_segment.channels = 1  # Already mono
        mock_segment.frame_rate = 16000  # Already at target rate
        mock_segment.set_channels.return_value = mock_segment
        mock_segment.set_frame_rate.return_value = mock_segment
        
        config = AudioPreprocessingConfig(
            preprocessing_mode="selected",
            convert_to_mono="auto",  # Should check if needed
            downsample="auto",  # Should check if needed
            normalize_mode="off"
        )
        
        result, steps = apply_preprocessing(mock_segment, config)
        
        # Should not apply mono or resample because already compliant
        assert "mono" not in steps
        assert not any("resample" in step for step in steps)
    
    @patch('transcriptx.cli.audio_utils.PYDUB_AVAILABLE', False)
    def test_apply_preprocessing_pydub_not_available(self):
        """Test when pydub is not available."""
        mock_audio = MagicMock()
        config = AudioPreprocessingConfig()
        
        result, steps = apply_preprocessing(mock_audio, config)
        
        # Should return original audio unchanged
        assert result is mock_audio
        assert steps == []
