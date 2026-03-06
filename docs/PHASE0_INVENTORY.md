# Phase 0: Design and Inventory

## Call Graph: interactive_menu -> workflows -> engine

```
run_interactive_menu()
  ├── _show_preprocessing_menu() -> run_wav_processing_workflow, run_preprocess_single_file, run_vtt_import_workflow, run_srt_import_workflow, run_deduplication_workflow, run_file_rename_workflow
  ├── _show_speaker_management_menu() -> run_speaker_identification_workflow, ...
  ├── _show_group_management_menu() -> group commands
  ├── _show_post_processing_menu() -> run_corrections_workflow, ...
  ├── run_single_analysis_workflow() -> _run_analysis_workflow_impl()
  │     └── select_analysis_target_interactive() [C]
  │     └── select_analysis_mode() [C]
  │     └── select_analysis_modules() [C]
  │     └── apply_analysis_mode_settings() [C]
  │     └── run_analysis_pipeline() [engine]
  ├── run_test_analysis_workflow()
  ├── run_prep_audio_workflow()
  ├── run_batch_analyze_workflow() -> run_batch_analysis_pipeline()
  ├── _show_interface_menu() -> _show_browser_menu() [Streamlit]
  ├── edit_config_interactive() [C]
  └── settings_menu_loop() [C]

run_analysis_non_interactive() [A - core logic, but has prints]
  └── apply_analysis_mode_settings_non_interactive() [A]
  └── run_analysis_pipeline(manifest=...) [engine]

run_speaker_identification_on_paths() [A - core logic, but has prints]
  └── _run_speaker_id_for_one_path() [A]
  └── build_speaker_map() [io]
  └── rename_transcript_after_speaker_mapping() [core]
  └── store_transcript_after_speaker_identification() [database]

run_batch_analyze_non_interactive() [A]
  └── run_batch_analysis_pipeline() [batch_workflows]
  └── discover_all_transcript_paths() [A]
```

## Function Classification

### (A) Pure reusable logic - extract to app/workflows or app/controllers

| File | Function | Notes |
|------|----------|-------|
| file_selection_utils.py | discover_all_transcript_paths | No prompts |
| file_selection_utils.py | _normalize_allowed_exts, _make_absolute_path, _format_allowed_exts | Helpers |
| file_selection_utils.py | _resolve_transcript_discovery_root, _is_excluded_transcript_path | Helpers |
| file_selection_utils.py | _collect_paths_from_entries, validate_wav_file, validate_audio_file | Validation |
| file_selection_utils.py | _format_transcript_file_with_analysis, _has_analysis_outputs | Metadata (split display from data) |
| file_selection_utils.py | _process_transcript_paths | VTT/SRT import logic |
| analysis_utils.py | _named_speaker_count_for_path | Speaker count |
| analysis_utils.py | resolve_modules_for_selection_kind | Module resolution |
| analysis_utils.py | apply_analysis_mode_settings_non_interactive | Mode application |
| analysis_utils.py | _module_display_name, format_modules_columns | Display only - keep in CLI |
| analysis_target_picker.py | hydrate_group_selection, TargetSelection.get_member_paths | Group resolution |
| analysis_workflow.py | run_analysis_non_interactive | Core - strip prints, add progress callback |
| speaker_workflow.py | _run_speaker_id_for_one_path | Core logic |
| speaker_workflow.py | run_speaker_identification_non_interactive | Strip prints |
| batch_analyze_workflow.py | run_batch_analyze_non_interactive | Already clean |
| profile_manager_ui.py | get_active_profile_name, get_current_config_dict, get_default_config_dict | Profile ops |
| config_editor.py | Config load/save/validate logic | Extract from menus |

### (B) Terminal rendering - keep in CLI only

| File | Function | Notes |
|------|----------|-------|
| display_utils.py | show_banner, show_current_config | Rich output |
| file_selection_utils.py | _print_invalid_entries | Terminal only |
| analysis_workflow.py | format_modules_columns usage, print statements | Rich/print |
| settings/ui.py | settings_menu_loop, create_*_editor | questionary wrappers |
| io_ui equivalents | All questionary/rich usage | CLI-only |

### (C) Prompt-driven control flow - deprecate, replace with controller calls

| File | Function | Notes |
|------|----------|-------|
| interactive_menu.py | run_interactive_menu, _show_*_menu | Full menu loops |
| interactive_menu.py | _check_and_install_streamlit, _check_and_install_librosa | questionary.confirm |
| analysis_target_picker.py | select_analysis_target_interactive | questionary.select |
| file_selection_utils.py | select_*_interactive, prompt_for_file_path, reorder_files_interactive | All questionary |
| analysis_utils.py | select_analysis_modules, select_analysis_mode, apply_analysis_mode_settings | questionary |
| profile_manager_ui.py | manage_profiles_interactive, switch_profile_interactive, create_profile_interactive, etc. | questionary |
| wav_processing_workflow/menu.py | _run_wav_processing_workflow_impl | questionary.select |
| analysis_workflow.py | _run_analysis_workflow_impl | Full interactive flow |
| speaker_workflow.py | _run_speaker_identification_workflow_impl | Full interactive flow |

## Controller Interface Sketches

### AnalysisController
```python
def validate_readiness(self, request: AnalysisRequest) -> ValidationResult
def run_analysis(self, request: AnalysisRequest, progress: ProgressCallback) -> AnalysisResult
def get_available_modules(self) -> list[ModuleInfo]
def get_default_modules(self, transcript_paths: list[str]) -> list[str]
def resolve_modules(self, mode: str, profile: str | None, custom_ids: list[str] | None) -> ResolvedModules
```

### LibraryController
```python
def list_transcripts(self, root: Path | None = None) -> list[TranscriptMetadata]
def get_transcript_metadata(self, path: Path) -> TranscriptMetadata
def list_audio_files(self, root: Path) -> list[Path]
```

### RunController
```python
def list_recent_runs(self, limit: int = 20) -> list[RunSummary]
def get_run_manifest(self, run_dir: Path) -> dict
def list_artifacts(self, run_dir: Path) -> list[ArtifactInfo]
```

### SpeakerController
```python
def identify_speakers(self, request: SpeakerIdentificationRequest, progress: ProgressCallback) -> SpeakerIdentificationResult
def get_speaker_map(self, path: Path) -> dict
def update_speaker_map(self, path: Path, mapping: dict) -> None
```

### ProfileController (read-only initially)
```python
def list_profiles(self, module: str) -> list[str]
def get_active_profile(self, module: str) -> str
def load_profile(self, module: str, name: str) -> dict
```

### SettingsController (read-only initially)
```python
def get_effective_config(self) -> dict
def get_storage_roots(self) -> dict[str, Path]
```

## Request/Result Type Inventory

### AnalysisRequest
- transcript_path: Path
- mode: str ("quick" | "full")
- modules: list[str] | None
- profile: str | None
- skip_speaker_mapping: bool
- output_dir: Path | None
- run_label: str | None
- persist: bool

### AnalysisResult
- success: bool
- run_dir: Path
- manifest_path: Path
- modules_executed: list[str]
- warnings: list[str]
- errors: list[str]
- duration_seconds: float | None
- status: str ("completed" | "failed" | "partial" | "cancelled")

### SpeakerIdentificationRequest
- transcript_paths: list[Path]
- overwrite: bool
- skip_rename: bool

### SpeakerIdentificationResult
- success: bool
- updated_paths: list[Path]
- speakers_identified: int
- errors: list[str]

### PreprocessRequest / PreprocessResult
- (TBD in Phase 5)

### BatchAnalysisRequest / BatchAnalysisResult
- folder: Path
- analysis_mode: str
- selected_modules: list[str] | None
- skip_speaker_gate: bool
- persist: bool
- -> status, transcript_count, errors

### RunSummary
- run_dir: Path
- transcript_path: Path
- run_id: str
- created_at: datetime
- selected_modules: list[str]
- profile_name: str | None
- manifest_path: Path
- status: str
- duration_seconds: float | None
- warnings_count: int | None

### TranscriptMetadata
- path: Path
- base_name: str
- duration_seconds: float | None
- speaker_count: int | None
- named_speaker_count: int | None
- has_analysis_outputs: bool
- has_speaker_map: bool
- linked_run_dirs: list[Path]
