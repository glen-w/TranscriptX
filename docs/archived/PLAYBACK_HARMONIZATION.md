# Playback Functions and Shortcuts Harmonization

## Current State

### 1. **File Selection Interface** (`file_selection_interface.py`)
**Use Case:** Full audio file playback in file browser
**Key Bindings:**
- `→` (right arrow) - Play current file
- `←` (left arrow) - Stop playback
- `,` or `<` - Skip backward 10 seconds
- `.` or `>` - Skip forward 10 seconds

**Implementation:** Uses `PlaybackController` class

### 2. **Audio Playback Handler** (`audio_playback_handler.py`)
**Use Case:** Reusable playback controller with key binding factory
**Key Bindings:** (Same as file selection)
- `→` (right arrow) - Play current file
- `←` (left arrow) - Stop playback
- `,` or `<` - Skip backward 10 seconds
- `.` or `>` - Skip forward 10 seconds

**Implementation:** Provides `create_playback_key_bindings()` factory function

### 3. **Speaker Mapping Interface** (`speaker_mapping/interactive.py`)
**Use Case:** Segment-based playback for transcript lines
**Key Bindings:**
- `→` (right arrow) - Play exact segment (no padding)
- `Shift+→` - Play segment with short context (0.8s padding)
- `Ctrl+→` - Play segment with long context (3.0s padding)
- `←` (left arrow) - Stop playback ✅ (recently added)
- **Missing:** Skip bindings (comma/period)

**Implementation:** Uses `SegmentPlayer` directly

## Inconsistencies

### ✅ Harmonized
- **Left arrow = Stop** - Now consistent across all interfaces
- **Right arrow = Play** - Consistent (though different play modes)

### ⚠️ Different by Design
- **Skip bindings** - Only in file selection (makes sense - segments don't need skip)
- **Context playback** - Only in speaker mapping (makes sense - for transcript segments)

### 📝 Minor Issues
1. **Outdated help text** in `utils.py` (`_playback_help_text`) - not used, can be removed
2. **No skip bindings** in speaker mapping - intentional (segments are short)

## Recommendations

### ✅ Already Fixed
- Left arrow stop binding added to speaker mapping
- Info messages changed to debug level (only errors shown)

### 💡 Optional Improvements
1. **Consider adding skip bindings to speaker mapping** if users want to skip within a segment
   - Low priority - segments are typically short
   - Could be useful for long segments

2. **Remove unused `_playback_help_text` function** from `utils.py`
   - Dead code, not referenced anywhere

3. **Document the different use cases** in code comments:
   - File selection = full file playback with seeking
   - Speaker mapping = segment playback with context padding

## Summary

The playback functions are **mostly harmonized** with intentional differences based on use case:
- **File playback** interfaces use skip bindings (comma/period)
- **Segment playback** interface uses context bindings (Shift/Ctrl+right)
- **Stop binding** (left arrow) is now consistent everywhere ✅

The main difference is that segment playback doesn't need skip functionality since segments are short and context padding is more useful.
