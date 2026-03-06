"""
Session state key constants for TranscriptX Streamlit app.

Use these for UI state only. Persisted data (config, profiles, runs, transcripts)
lives in filesystem/DB per storage contract.
"""

# Selection state
SELECTED_TRANSCRIPT_PATH = "selected_transcript_path"
SELECTED_RUN_DIR = "selected_run_dir"
SELECTED_PROFILE_NAME = "selected_profile_name"

# Analysis form
PENDING_ANALYSIS_REQUEST = "pending_analysis_request"

# Execution state
ACTIVE_JOB_ID = "active_job_id"
JOB_LOGS = "job_logs"

# UI state
UI_FILTERS = "ui_filters"
SETTINGS_DRAFT = "settings_draft"
PAGE_FLASH_MESSAGE = "page_flash_message"
