# src/purse/utils/constants.py
from typing import Dict
import logging

# Log Emojis (as per PRD 5.10, workplan specifies these)
LOG_EMOJI_INFO: str = "🟢"
LOG_EMOJI_WARNING: str = "🟡"
LOG_EMOJI_ERROR: str = "🛑"
LOG_EMOJI_DEBUG: str = "🐛" # Example for DEBUG, from workplan

LOG_EMOJI_MAP: Dict[int, str] = {
    logging.INFO: LOG_EMOJI_INFO,
    logging.WARNING: LOG_EMOJI_WARNING,
    logging.ERROR: LOG_EMOJI_ERROR,
    logging.CRITICAL: LOG_EMOJI_ERROR, # CRITICAL also uses error emoji
    logging.DEBUG: LOG_EMOJI_DEBUG,
}

# Article Statuses (as per PRD 5.2)
STATUS_UNREAD: str = "unread"
STATUS_IN_PROGRESS: str = "in-progress"
STATUS_READ: str = "read"
STATUS_ARCHIVED: str = "archived"

# Source Applications (as per PRD 5.2)
SOURCE_WEB_PARSER: str = "web_parser"
SOURCE_PDF_IMPORT: str = "pdf_import"
SOURCE_DOCX_IMPORT: str = "docx_import"
SOURCE_POCKET_MIGRATION: str = "pocket_migration"
SOURCE_BOOKMARK: str = "bookmark"

# Default settings if settings.yml is not found or incomplete (PRD 5.3, 5.9)
DEFAULT_FONT_FAMILY: str = "sans-serif" # Toga will resolve to platform default sans-serif
DEFAULT_FONT_SIZE: int = 14 # Adjusted from 12 in workplan to a more common default
DEFAULT_THEME: str = "light" # "light", "dark", "sepia"

# App constants for Toga (PRD 7, workplan)
APP_NAME: str = "Purse"
APP_AUTHOR: str = "Christopher Penn"
APP_ID: str = "com.christopherspenn.purse" # Bundle ID / Reverse domain

# Average words per minute for reading time estimation (PRD 5.2)
WORDS_PER_MINUTE: int = 200

# YAML Frontmatter Keys (PRD 5.2, to ensure consistency)
KEY_ID: str = "id"
KEY_POCKET_ID: str = "pocket_id"
KEY_ORIGINAL_URL: str = "original_url"
KEY_TITLE: str = "title"
KEY_AUTHOR: str = "author"
KEY_PUBLICATION_NAME: str = "publication_name"
KEY_PUBLICATION_DATE: str = "publication_date"
KEY_SAVED_DATE: str = "saved_date"
KEY_LAST_MODIFIED_DATE: str = "last_modified_date"
KEY_STATUS: str = "status"
KEY_FAVORITE: str = "favorite"
KEY_TAGS: str = "tags"
KEY_ESTIMATED_READ_TIME: str = "estimated_read_time_minutes"
KEY_WORD_COUNT: str = "word_count"
KEY_LANGUAGE: str = "language"
KEY_EXCERPT: str = "excerpt"
KEY_SOURCE_APPLICATION: str = "source_application"
KEY_ARCHIVED_FROM_FALLBACK: str = "archived_from_fallback"
KEY_THUMBNAIL_URL_LOCAL: str = "thumbnail_url_local"
# Optional: A potential source URL for a thumbnail, not for YAML, but for internal Article state
KEY_POTENTIAL_THUMBNAIL_SOURCE_URL: str = "potential_thumbnail_source_url"


# Markdown structure constants (PRD 5.2)
MARKDOWN_NOTES_HEADING: str = "## My Notes"
MARKDOWN_HIGHLIGHT_START_TAG: str = "=="
MARKDOWN_HIGHLIGHT_END_TAG: str = "=="

# Sync constants (PRD 5.7)
SYNC_CONFLICT_LOG_FILENAME: str = "sync_actions.log"

# Default User Agent for HTTP Client
DEFAULT_USER_AGENT: str = f"{APP_NAME}/{APP_ID} (github.com/cspenn/purse)" # Placeholder version

# Add other constants as they become necessary.
