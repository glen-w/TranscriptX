#!/usr/bin/env python3
"""
Audio Quality Comparison Script

Compares two audio files and provides detailed metrics for:
- Technical specifications (sample rate, bitrate, channels)
- Audio quality metrics (RMS, peak levels, dynamic range)
- Frequency analysis
- Noise characteristics
- File size and compression efficiency
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("Warning: pydub not available. Install with: pip install pydub")

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False


def get_ffprobe_info(audio_path: Path) -> Dict[str, Any]:
    """Get detailed audio information using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams",
                str(audio_path)
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error running ffprobe: {e}")
        return {}


def extract_audio_properties(ffprobe_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key audio properties from ffprobe output."""
    props = {
        "sample_rate": None,
        "channels": None,
        "bitrate": None,
        "codec": None,
        "duration": None,
        "file_size": None,
        "bit_depth": None,
    }
    
    # Get format info
    format_info = ffprobe_data.get("format", {})
    props["duration"] = float(format_info.get("duration", 0))
    props["file_size"] = int(format_info.get("size", 0))
    props["bitrate"] = int(format_info.get("bit_rate", 0))
    
    # Get stream info (audio stream)
    streams = ffprobe_data.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    
    if audio_stream:
        props["sample_rate"] = int(audio_stream.get("sample_rate", 0))
        props["channels"] = int(audio_stream.get("channels", 0))
        props["codec"] = audio_stream.get("codec_name", "unknown")
        props["bit_depth"] = audio_stream.get("bits_per_sample") or audio_stream.get("bits_per_raw_sample")
    
    return props


def analyze_audio_quality(audio_path: Path) -> Dict[str, Any]:
    """Analyze audio quality metrics using pydub and numpy."""
    metrics = {
        "rms_level": None,
        "peak_level": None,
        "dynamic_range": None,
        "zero_crossing_rate": None,
        "silence_percentage": None,
        "clipping_detected": False,
    }
    
    if not PYDUB_AVAILABLE:
        return metrics
    
    try:
        # Load audio
        audio = AudioSegment.from_file(str(audio_path))
        
        # Convert to numpy array for analysis
        samples = np.array(audio.get_array_of_samples())
        
        # Handle stereo/mono
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)  # Convert to mono for analysis
        
        # Normalize to -1.0 to 1.0 range
        if audio.sample_width == 1:
            samples = samples.astype(np.float32) / 128.0 - 1.0
        elif audio.sample_width == 2:
            samples = samples.astype(np.float32) / 32768.0
        elif audio.sample_width == 4:
            samples = samples.astype(np.float32) / 2147483648.0
        
        # Calculate RMS (Root Mean Square) - average energy level
        rms = np.sqrt(np.mean(samples**2))
        metrics["rms_level"] = float(rms)
        metrics["rms_db"] = float(20 * np.log10(rms + 1e-10))  # Avoid log(0)
        
        # Calculate peak level
        peak = np.max(np.abs(samples))
        metrics["peak_level"] = float(peak)
        metrics["peak_db"] = float(20 * np.log10(peak + 1e-10))
        
        # Dynamic range (difference between peak and RMS)
        metrics["dynamic_range"] = float(metrics["peak_db"] - metrics["rms_db"])
        
        # Zero crossing rate (indicator of noise/voice characteristics)
        zero_crossings = np.sum(np.diff(np.signbit(samples)))
        metrics["zero_crossing_rate"] = float(zero_crossings / len(samples))
        
        # Silence detection (samples below threshold)
        silence_threshold = 0.01  # 1% of max amplitude
        silence_samples = np.sum(np.abs(samples) < silence_threshold)
        metrics["silence_percentage"] = float(silence_samples / len(samples) * 100)
        
        # Clipping detection (samples at maximum)
        max_possible = 1.0 - (1.0 / (2 ** (audio.sample_width * 8 - 1)))
        clipped_samples = np.sum(np.abs(samples) >= max_possible * 0.99)
        metrics["clipping_detected"] = clipped_samples > (len(samples) * 0.001)  # >0.1% clipped
        metrics["clipping_percentage"] = float(clipped_samples / len(samples) * 100)
        
    except Exception as e:
        print(f"Error analyzing audio quality: {e}")
    
    return metrics


def analyze_frequency_content(audio_path: Path) -> Dict[str, Any]:
    """Analyze frequency content using soundfile and numpy FFT."""
    freq_analysis = {
        "dominant_frequencies": None,
        "frequency_centroid": None,
        "bandwidth": None,
    }
    
    if not SOUNDFILE_AVAILABLE:
        return freq_analysis
    
    try:
        # Load audio file
        data, sample_rate = sf.read(str(audio_path))
        
        # Convert to mono if stereo
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
        
        # Take a representative sample (middle 10 seconds or entire file if shorter)
        sample_duration = min(10.0, len(data) / sample_rate)
        start_sample = int((len(data) - sample_duration * sample_rate) / 2)
        end_sample = int(start_sample + sample_duration * sample_rate)
        sample = data[start_sample:end_sample]
        
        # Apply window function to reduce spectral leakage
        window = np.hanning(len(sample))
        windowed = sample * window
        
        # Compute FFT
        fft = np.fft.rfft(windowed)
        magnitude = np.abs(fft)
        frequencies = np.fft.rfftfreq(len(windowed), 1.0 / sample_rate)
        
        # Find dominant frequencies (peaks in spectrum)
        # Focus on speech range (80 Hz to 8 kHz)
        speech_mask = (frequencies >= 80) & (frequencies <= 8000)
        speech_freqs = frequencies[speech_mask]
        speech_mags = magnitude[speech_mask]
        
        if len(speech_freqs) > 0:
            # Find top 5 peaks
            peak_indices = np.argsort(speech_mags)[-5:][::-1]
            freq_analysis["dominant_frequencies"] = [
                float(f) for f in speech_freqs[peak_indices]
            ]
            
            # Frequency centroid (weighted average frequency)
            if np.sum(speech_mags) > 0:
                freq_analysis["frequency_centroid"] = float(
                    np.sum(speech_freqs * speech_mags) / np.sum(speech_mags)
                )
            
            # Bandwidth (spread of frequencies)
            if freq_analysis["frequency_centroid"]:
                variance = np.sum(
                    ((speech_freqs - freq_analysis["frequency_centroid"]) ** 2) * speech_mags
                ) / np.sum(speech_mags)
                freq_analysis["bandwidth"] = float(np.sqrt(variance))
        
    except Exception as e:
        print(f"Error analyzing frequency content: {e}")
    
    return freq_analysis


def calculate_compression_efficiency(file_size: int, duration: float, bitrate: int) -> Dict[str, Any]:
    """Calculate compression efficiency metrics."""
    if duration == 0:
        return {}
    
    # Theoretical uncompressed size (assuming 16-bit, 44.1kHz, mono)
    uncompressed_size = duration * 44100 * 2 * 1  # bytes
    compression_ratio = file_size / uncompressed_size if uncompressed_size > 0 else 0
    
    # Bitrate efficiency
    actual_bitrate = (file_size * 8) / duration if duration > 0 else 0
    bitrate_efficiency = (actual_bitrate / bitrate * 100) if bitrate > 0 else 0
    
    return {
        "compression_ratio": float(compression_ratio),
        "compression_percentage": float((1 - compression_ratio) * 100),
        "actual_bitrate_bps": float(actual_bitrate),
        "bitrate_efficiency": float(bitrate_efficiency),
    }


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def compare_audio_files(file1_path: Path, file2_path: Path) -> None:
    """Compare two audio files and print detailed report."""
    
    print("=" * 80)
    print("AUDIO QUALITY COMPARISON REPORT")
    print("=" * 80)
    print()
    
    files = [
        ("File 1 (Dictation Device)", file1_path),
        ("File 2 (Laptop Mic)", file2_path),
    ]
    
    all_results = []
    
    for label, file_path in files:
        print(f"\n{'=' * 80}")
        print(f"{label}: {file_path.name}")
        print(f"{'=' * 80}")
        
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            continue
        
        # Get file info
        print("\n📊 Technical Specifications:")
        print("-" * 80)
        ffprobe_data = get_ffprobe_info(file_path)
        props = extract_audio_properties(ffprobe_data)
        
        print(f"  Duration:        {format_duration(props['duration'])}")
        print(f"  File Size:       {format_file_size(props['file_size'])}")
        print(f"  Sample Rate:    {props['sample_rate']:,} Hz" if props['sample_rate'] else "  Sample Rate:    Unknown")
        print(f"  Channels:        {props['channels']}" if props['channels'] else "  Channels:        Unknown")
        print(f"  Codec:           {props['codec']}" if props['codec'] else "  Codec:           Unknown")
        print(f"  Bitrate:         {props['bitrate']:,} bps ({props['bitrate']/1000:.1f} kbps)" if props['bitrate'] else "  Bitrate:         Unknown")
        if props['bit_depth']:
            print(f"  Bit Depth:       {props['bit_depth']} bits")
        
        # Compression analysis
        if props['duration'] and props['bitrate']:
            compression = calculate_compression_efficiency(
                props['file_size'], props['duration'], props['bitrate']
            )
            print(f"\n  Compression Ratio: {compression['compression_ratio']:.3f}")
            print(f"  Compression:      {compression['compression_percentage']:.1f}%")
        
        # Audio quality metrics
        print("\n🎵 Audio Quality Metrics:")
        print("-" * 80)
        quality = analyze_audio_quality(file_path)
        
        if quality['rms_level'] is not None:
            print(f"  RMS Level:       {quality['rms_db']:.2f} dB")
            print(f"  Peak Level:      {quality['peak_db']:.2f} dB")
            print(f"  Dynamic Range:   {quality['dynamic_range']:.2f} dB")
            print(f"  Zero Crossing:   {quality['zero_crossing_rate']:.4f}")
            print(f"  Silence:         {quality['silence_percentage']:.1f}%")
            if quality['clipping_detected']:
                print(f"  ⚠️  Clipping:      {quality['clipping_percentage']:.2f}% (DETECTED)")
            else:
                print(f"  Clipping:         {quality['clipping_percentage']:.2f}% (none detected)")
        
        # Frequency analysis
        print("\n📈 Frequency Analysis:")
        print("-" * 80)
        freq = analyze_frequency_content(file_path)
        
        if freq['dominant_frequencies']:
            print(f"  Dominant Frequencies: {[f'{f:.1f} Hz' for f in freq['dominant_frequencies']]}")
        if freq['frequency_centroid']:
            print(f"  Frequency Centroid:   {freq['frequency_centroid']:.1f} Hz")
        if freq['bandwidth']:
            print(f"  Bandwidth:            {freq['bandwidth']:.1f} Hz")
        
        all_results.append({
            'label': label,
            'path': file_path,
            'props': props,
            'quality': quality,
            'frequency': freq,
        })
    
    # Comparative analysis
    if len(all_results) == 2:
        print("\n" + "=" * 80)
        print("COMPARATIVE ANALYSIS")
        print("=" * 80)
        
        r1, r2 = all_results[0], all_results[1]
        
        print("\n📊 Technical Comparison:")
        print("-" * 80)
        
        if r1['props']['sample_rate'] and r2['props']['sample_rate']:
            sr_diff = r1['props']['sample_rate'] - r2['props']['sample_rate']
            print(f"  Sample Rate Difference: {abs(sr_diff):,} Hz ({'+' if sr_diff > 0 else ''}{sr_diff:,} Hz)")
            if abs(sr_diff) > 8000:
                print("    ⚠️  Significant difference - may affect transcription quality")
        
        if r1['props']['duration'] and r2['props']['duration']:
            dur_diff = r1['props']['duration'] - r2['props']['duration']
            print(f"  Duration Difference: {abs(dur_diff):.1f}s ({'+' if dur_diff > 0 else ''}{dur_diff:.1f}s)")
        
        if r1['props']['file_size'] and r2['props']['file_size']:
            size_diff = r1['props']['file_size'] - r2['props']['file_size']
            size_diff_pct = (size_diff / r2['props']['file_size']) * 100
            print(f"  File Size Difference: {format_file_size(abs(size_diff))} ({'+' if size_diff > 0 else ''}{size_diff_pct:.1f}%)")
        
        print("\n🎵 Quality Comparison:")
        print("-" * 80)
        
        if r1['quality']['rms_db'] and r2['quality']['rms_db']:
            rms_diff = r1['quality']['rms_db'] - r2['quality']['rms_db']
            print(f"  RMS Level Difference: {abs(rms_diff):.2f} dB ({'+' if rms_diff > 0 else ''}{rms_diff:.2f} dB)")
            if abs(rms_diff) > 3:
                print("    ⚠️  Significant level difference - one file may be quieter")
        
        if r1['quality']['dynamic_range'] and r2['quality']['dynamic_range']:
            dr_diff = r1['quality']['dynamic_range'] - r2['quality']['dynamic_range']
            print(f"  Dynamic Range Difference: {abs(dr_diff):.2f} dB")
            if dr_diff > 5:
                print("    ℹ️  File 1 has more dynamic range (better for speech)")
            elif dr_diff < -5:
                print("    ℹ️  File 2 has more dynamic range (better for speech)")
        
        if r1['quality']['silence_percentage'] and r2['quality']['silence_percentage']:
            silence_diff = r1['quality']['silence_percentage'] - r2['quality']['silence_percentage']
            print(f"  Silence Difference: {abs(silence_diff):.1f}%")
        
        if r1['quality']['clipping_detected'] or r2['quality']['clipping_detected']:
            print("\n  ⚠️  CLIPPING DETECTED in one or both files!")
            print("     This can significantly degrade transcription quality.")
        
        print("\n📈 Frequency Comparison:")
        print("-" * 80)
        
        if r1['frequency']['frequency_centroid'] and r2['frequency']['frequency_centroid']:
            fc_diff = r1['frequency']['frequency_centroid'] - r2['frequency']['frequency_centroid']
            print(f"  Frequency Centroid Difference: {abs(fc_diff):.1f} Hz")
            # Speech typically has centroid around 1-2 kHz
            if 1000 <= r1['frequency']['frequency_centroid'] <= 2000:
                print("    ✓ File 1 frequency content is optimal for speech")
            if 1000 <= r2['frequency']['frequency_centroid'] <= 2000:
                print("    ✓ File 2 frequency content is optimal for speech")
        
        # Recommendations
        print("\n💡 Recommendations:")
        print("-" * 80)
        
        recommendations = []
        
        if r1['quality']['clipping_detected'] or r2['quality']['clipping_detected']:
            recommendations.append("⚠️  Reduce recording levels to prevent clipping")
        
        if r1['props']['sample_rate'] and r1['props']['sample_rate'] > 16000:
            recommendations.append("ℹ️  File 1 sample rate >16kHz - consider downsampling to 16kHz for transcription (saves space)")
        
        if r2['props']['sample_rate'] and r2['props']['sample_rate'] > 16000:
            recommendations.append("ℹ️  File 2 sample rate >16kHz - consider downsampling to 16kHz for transcription (saves space)")
        
        if abs(rms_diff) > 3 if (r1['quality']['rms_db'] and r2['quality']['rms_db']) else False:
            recommendations.append("ℹ️  Normalize audio levels for consistent transcription quality")
        
        if not recommendations:
            recommendations.append("✓ Both files appear suitable for transcription")
        
        for rec in recommendations:
            print(f"  {rec}")


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python compare_audio_quality.py <file1.mp3> <file2.mp3>")
        print("\nExample:")
        print("  python compare_audio_quality.py data/recordings/260108_CSE_pen.mp3 data/recordings/260108_CSE.mp3")
        sys.exit(1)
    
    file1 = Path(sys.argv[1])
    file2 = Path(sys.argv[2])
    
    if not file1.exists():
        print(f"Error: File not found: {file1}")
        sys.exit(1)
    
    if not file2.exists():
        print(f"Error: File not found: {file2}")
        sys.exit(1)
    
    compare_audio_files(file1, file2)


if __name__ == "__main__":
    main()
