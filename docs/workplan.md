## Purse Application Development Workplan

**Project Name:** Purse
**Python Version:** 3.11+
**Primary GUI Framework:** Toga
**Configuration:** YAML files (`config.yml` for local, `settings.yml` for synced user preferences)
**Logging:** Custom setup with emojis, console, and timestamped files.

---

### Phase 1: Project Setup & Core Utilities

#### 1. `pyproject.toml`
*   **File Path**: `purse/pyproject.toml`
*   **Intent**: Defines project metadata, dependencies, and build system configuration (using Poetry or PDM).
*   **Upstream Dependencies**: None.
*   **Downstream Dependencies**: Entire project build and dependency management.
*   **Changes Needed**:
    *   Initialize project using Poetry: `poetry init` (or PDM equivalent).
    *   Set Python version constraint: `python = "^3.11"`
    *   Add core dependencies as per PRD (7. Development Guidelines & Stack) and initial needs:
        *   `toga`
        *   `httpx[http2]` (for async HTTP requests)
        *   `PyYAML` (for YAML configuration)
        *   `trafilatura` (for web content parsing)
        *   `PyMuPDF` (for PDF text extraction)
        *   `python-docx` (for DOCX text extraction)
        *   `whoosh` (for search indexing)
        *   `tqdm` (for progress monitoring in console/logs)
        *   `keyring` (for storing OAuth tokens securely)
        *   Official Python SDKs for:
            *   `dropbox`
            *   `google-api-python-client google-auth-httplib2 google-auth-oauthlib`
            *   `msal` (for Microsoft OneDrive/Graph API)
    *   Add development dependencies:
        *   `pytest`
        *   `pytest-asyncio`
        *   `mypy`
        *   `ruff` (for linting and formatting, replaces black, pylint, isort if configured)
        *   `pre-commit`
    *   Configure Ruff (or Black/Pylint/isort separately) for formatting and linting according to PEP 8.
    *   Define project metadata: name, version, description, authors (Christopher Penn), license (MIT - to be confirmed).
    *   Example `[tool.poetry.dependencies]` section:
        ```toml
        [tool.poetry.dependencies]
        python = "^3.11"
        toga = "*" # Specify version as appropriate
        httpx = {extras = ["http2"], version = "*"}
        PyYAML = "*"
        trafilatura = "*"
        PyMuPDF = "*"
        python-docx = "*"
        whoosh = "*"
        tqdm = "*"
        keyring = "*"
        # Cloud SDKs - pin versions after checking latest stable
        dropbox = "*"
        google-api-python-client = "*"
        google-auth-httplib2 = "*"
        google-auth-oauthlib = "*"
        msal = "*"

        [tool.poetry.group.dev.dependencies]
        pytest = "*"
        pytest-asyncio = "*"
        mypy = "*"
        ruff = "*" # Configure ruff to handle formatting and extensive linting
        pre-commit = "*"
        ```
    *   Set up `[tool.ruff]` configuration for linting rules and formatting (line length, etc.).

---

#### 2. `.gitignore`
*   **File Path**: `purse/.gitignore`
*   **Intent**: Specifies intentionally untracked files that Git should ignore.
*   **Upstream Dependencies**: None.
*   **Downstream Dependencies**: Git version control.
*   **Changes Needed**:
    *   Create the file.
    *   Add standard Python ignores (e.g., `__pycache__/`, `*.pyc`, `.env`, `venv/`, `dist/`, `build/`, `*.egg-info/`).
    *   Add OS-specific ignores (e.g., `.DS_Store`, `Thumbs.db`).
    *   Add IDE-specific ignores (e.g., `.vscode/`, `.idea/`).
    *   Add project-specific ignores:
        *   `logs/*.log` (but not the `logs/` directory itself if empty)
        *   `local_user_data/` (any local, non-synced user data cache or temp files)
        *   `*.test_results`
        *   `coverage.xml`
        *   `local_settings.yml` (if a purely local, non-versioned settings override is ever needed)
        *   `config.yml` (This is crucial: `config.yml` holds initial local config, not to be committed if it contains sensitive paths or will be user-generated on first run. PRD: "Never use environment variables - always use config.yml for portability" implies it should be *part* of the repo as a template, or generated. Let's assume a `config.example.yml` is versioned, and `config.yml` is generated/copied by the user and thus ignored). **Decision**: Version `config.yml` with sensible defaults, and instruct users to customize if needed. *Do not add `config.yml` to `.gitignore` for now, as it's stated as the primary config method.*
        *   `*.sqlite` (or other local database files if Whoosh index is stored directly) - Whoosh index directory should be ignored.
        *   The root sync folder specified by the user (e.g., `/Apps/Purse/`) and its contents should not be part of the git repo, but managed by the app.
        *   `.purse_config/settings.yml` will be created by the app in the cloud sync dir, so not directly in the repo.

---

#### 3. `LICENSE`
*   **File Path**: `purse/LICENSE`
*   **Intent**: Defines the legal license under which the software is provided.
*   **Upstream Dependencies**: None.
*   **Downstream Dependencies**: Legal compliance.
*   **Changes Needed**:
    *   Create the file.
    *   Add the full text of the MIT License (or other chosen permissive FOSS license, as per PRD section 7). Replace `[year]` and `[fullname]` placeholders with "2025 Christopher Penn" (or current year/author).

---

#### 4. `README.md`
*   **File Path**: `purse/README.md`
*   **Intent**: Provides an overview of the project, setup instructions, and other relevant information.
*   **Upstream Dependencies**: None.
*   **Downstream Dependencies**: User/developer understanding.
*   **Changes Needed**:
    *   Create the file.
    *   Add initial content:
        *   Project Title: Purse
        *   Brief description from PRD 1.1.
        *   Link to GitHub Repository: `https://github.com/cspenn/purse`
        *   Placeholder sections for:
            *   Features (from PRD Goals/Objectives)
            *   Installation
            *   Configuration
            *   Usage
            *   Contributing
            *   License

---

#### 5. `config.yml`
*   **File Path**: `purse/config.yml`
*   **Intent**: Provides base application configuration that is not user-specific or synced. This file *is* version controlled and provides defaults.
*   **Upstream Dependencies**: None.
*   **Downstream Dependencies**: `src/purse/config_manager.py`, `src/purse/logger_setup.py`.
*   **Changes Needed**:
    *   Create the file.
    *   Add initial YAML structure and default values:
        ```yaml
        # Purse Application Configuration (config.yml)
        # This file contains local, non-synced application settings.

        logging:
          log_level: "DEBUG"  # Default log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
          logs_dir: "logs"    # Relative to project root or app data dir
          max_log_files: 10   # Number of old log files to keep
          log_format_console: "%(asctime)s %(emoji_level)s %(name)s:%(lineno)d - %(message)s"
          log_format_file: "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
          date_format: "%Y-%m-%d %H:%M:%S"

        paths:
          # Path to the local directory for storing article data before/during cloud sync setup.
          # This will be superseded by the cloud path once configured.
          # For Toga, this should ideally resolve to an OS-idiomatic user data directory.
          # Placeholder, actual resolution logic will be in file_system_manager.py
          local_data_dir: "user_data/purse_library" # Relative to app user data directory
          local_search_index_dir: "user_data/search_index" # Relative to app user data directory
          # .purse_config will be inside the main sync folder in the cloud.
          # This defines the name of that config subdir.
          synced_config_dir_name: ".purse_config"
          synced_settings_filename: "settings.yml"

        # Default developer notification URL (can be overridden in synced settings.yml)
        developer_notifications_url: "https://www.christopherspenn.com/purse/notifications"

        # Retry mechanism defaults
        retry:
          max_attempts: 5
          initial_delay_seconds: 1
          max_delay_seconds: 60

        # archive.is or similar service (can be overridden in synced settings.yml)
        fallback_archive_service_url_template: "https://archive.is/{url}" # {url} will be replaced

        # Pocket Importer settings
        pocket_importer:
          reparse_pocket_html: true # Whether to re-parse HTML content from Pocket export
        ```

---

#### 6. `src/purse/utils/constants.py`
*   **File Path**: `src/purse/utils/constants.py`
*   **Intent**: Defines global constants used throughout the application.
*   **Upstream Dependencies**: None (standard library only).
*   **Downstream Dependencies**: `logger_setup.py`, various modules.
*   **Changes Needed**:
    *   Create `src/purse/utils/__init__.py` (empty).
    *   Create `src/purse/utils/constants.py`.
    *   Add necessary imports: `import logging` (only for `logging.LEVEL`).
    *   Define constants:
        ```python
        # src/purse/utils/constants.py
        from typing import Dict
        import logging

        # Log Emojis
        LOG_EMOJI_INFO: str = "🟢"
        LOG_EMOJI_WARNING: str = "🟡"
        LOG_EMOJI_ERROR: str = "🛑"
        LOG_EMOJI_DEBUG: str = "🐛" # Example for DEBUG

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

        # Default settings if settings.yml is not found or incomplete
        DEFAULT_FONT_FAMILY: str = "sans-serif"
        DEFAULT_FONT_SIZE: int = 12
        DEFAULT_THEME: str = "light" # "light", "dark", "sepia"

        # Other constants
        APP_NAME: str = "Purse"
        APP_AUTHOR: str = "Christopher Penn" # For Toga app definition
        APP_ID: str = "com.christopherspenn.purse" # For Toga app definition

        # Average words per minute for reading time estimation
        WORDS_PER_MINUTE: int = 200

        # YAML Frontmatter Keys (to ensure consistency)
        # (Self-documenting and helps avoid typos)
        KEY_ID: str = "id"
        KEY_POCKET_ID: str = "pocket_id"
        KEY_ORIGINAL_URL: str = "original_url"
        KEY_TITLE: str = "title"
        # ... (add all keys from PRD 5.2 YAML Frontmatter)
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

        MARKDOWN_NOTES_HEADING: str = "## My Notes"
        MARKDOWN_HIGHLIGHT_START_TAG: str = "=="
        MARKDOWN_HIGHLIGHT_END_TAG: str = "=="

        # Sync constants
        SYNC_CONFLICT_LOG_FILENAME: str = "sync_actions.log"
        ```

---

#### 7. `src/purse/config_manager.py`
*   **File Path**: `src/purse/config_manager.py`
*   **Intent**: Loads and provides access to configuration from `config.yml` (local defaults) and `settings.yml` (user-specific, potentially synced).
*   **Upstream Dependencies**: `PyYAML`, `os`, `pathlib`, `typing`.
*   **Downstream Dependencies**: `logger_setup.py`, almost all other modules.
*   **Changes Needed**:
    *   Create `src/purse/__init__.py` (empty).
    *   Create `src/purse/config_manager.py`.
    *   Add imports:
        ```python
        import yaml
        import os
        from pathlib import Path
        from typing import Any, Dict, Optional, Union
        import logging # For internal logging of config loading issues
        ```
    *   Define a class `ConfigManager`:
        ```python
        class ConfigManager:
            def __init__(self, base_config_path: Union[str, Path] = 'config.yml'):
                self.logger = logging.getLogger(__name__) # Basic logger for now
                self.base_config_path = Path(base_config_path)
                self.config: Dict[str, Any] = self._load_yaml(self.base_config_path)
                if not self.config:
                    self.logger.critical(f"🛑 Base configuration '{self.base_config_path}' not found or empty. Application cannot start.")
                    raise FileNotFoundError(f"Base configuration '{self.base_config_path}' not found.")

                self.settings: Dict[str, Any] = {} # To be loaded later
                self.settings_path: Optional[Path] = None

            def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return yaml.safe_load(f) or {}
                except FileNotFoundError:
                    self.logger.warning(f"🟡 Configuration file not found: {file_path}")
                    return {}
                except yaml.YAMLError as e:
                    self.logger.error(f"🛑 Error parsing YAML file {file_path}: {e}")
                    return {} # Or raise an error

            def get(self, key_path: str, default: Optional[Any] = None) -> Any:
                """
                Get a configuration value.
                Searches settings first, then base config.
                Key_path uses dot notation, e.g., 'logging.log_level'.
                """
                # Try settings first
                value = self._get_value_from_dict(self.settings, key_path)
                if value is not None:
                    return value

                # Try base config
                value = self._get_value_from_dict(self.config, key_path)
                if value is not None:
                    return value

                return default

            def _get_value_from_dict(self, config_dict: Dict[str, Any], key_path: str) -> Optional[Any]:
                keys = key_path.split('.')
                value = config_dict
                try:
                    for key in keys:
                        if isinstance(value, dict):
                            value = value[key]
                        else: # handle list index access if needed, e.g. key[index]
                            return None
                    return value
                except (KeyError, TypeError):
                    return None

            def load_settings(self, settings_file_path: Path) -> None:
                """Loads user-specific settings from settings.yml."""
                self.settings_path = settings_file_path
                self.settings = self._load_yaml(settings_file_path)
                if not self.settings:
                    self.logger.info(f"🟢 User settings file '{settings_file_path}' not found or empty. Using defaults.")
                else:
                    self.logger.info(f"🟢 User settings loaded from '{settings_file_path}'.")

            def save_settings(self) -> None:
                """Saves current settings to settings.yml."""
                if not self.settings_path:
                    self.logger.warning("🟡 Cannot save settings, path not set. Call load_settings first (even with a non-existent path).")
                    return

                try:
                    self.settings_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.settings_path, 'w', encoding='utf-8') as f:
                        yaml.dump(self.settings, f, sort_keys=False, indent=2)
                    self.logger.info(f"🟢 Settings saved to '{self.settings_path}'.")
                except Exception as e:
                    self.logger.error(f"🛑 Failed to save settings to '{self.settings_path}': {e}")

            def update_setting(self, key_path: str, value: Any) -> None:
                """Updates a setting in the self.settings dictionary and optionally saves."""
                keys = key_path.split('.')
                current_level = self.settings
                for i, key in enumerate(keys[:-1]):
                    if key not in current_level or not isinstance(current_level[key], dict):
                        current_level[key] = {}
                    current_level = current_level[key]
                current_level[keys[-1]] = value
                self.logger.debug(f"Updated setting '{key_path}' to '{value}'.")
                # Consider if auto-save is desired or should be explicit call
                # self.save_settings()

        # Instantiate a global config manager (can be imported)
        # This should be initialized after logger is set up, or logger setup should
        # use a temporary basicConfig for this module's internal logging.
        # For now, assume basicConfig is enough for ConfigManager internal logs.
        # The main app will create and pass this.
        # config_manager = ConfigManager()
        ```
    *   Ensure `ConfigManager` can gracefully handle missing keys or files, returning defaults or logging warnings/errors.
    *   The actual instantiation and loading of `settings.yml` will be handled in `main.py` or the Toga app setup, as the path to `settings.yml` depends on the synced cloud folder.

---

#### 8. `src/purse/logger_setup.py`
*   **File Path**: `src/purse/logger_setup.py`
*   **Intent**: Configures the application-wide logging system.
*   **Upstream Dependencies**: `logging`, `datetime`, `pathlib`, `src/purse/utils/constants.py`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: Almost all other modules.
*   **Changes Needed**:
    *   Create the file.
    *   Add imports:
        ```python
        import logging
        import logging.handlers
        from datetime import datetime
        from pathlib import Path
        from typing import TYPE_CHECKING

        from purse.utils import constants

        if TYPE_CHECKING:
            from purse.config_manager import ConfigManager
        ```
    *   Create an `EmojiFormatter` class:
        ```python
        class EmojiFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                record.emoji_level = constants.LOG_EMOJI_MAP.get(record.levelno, "")
                return super().format(record)
        ```
    *   Define `setup_logging` function:
        ```python
        def setup_logging(config_manager: 'ConfigManager') -> None:
            log_level_str = config_manager.get('logging.log_level', 'INFO').upper()
            log_level = getattr(logging, log_level_str, logging.INFO)

            logs_dir_str = config_manager.get('logging.logs_dir', 'logs')
            # For Toga, app_paths.data / logs_dir_str might be better.
            # This needs to be resolved carefully. For now, relative to execution.
            logs_dir = Path(logs_dir_str)
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Generate timestamped log file name
            log_file_name = f"log-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log"
            log_file_path = logs_dir / log_file_name

            # Get format strings from config
            console_format = config_manager.get('logging.log_format_console', "%(asctime)s %(emoji_level)s %(name)s - %(message)s")
            file_format = config_manager.get('logging.log_format_file', "%(asctime)s [%(levelname)s] %(name)s - %(message)s")
            date_format = config_manager.get('logging.date_format', "%Y-%m-%d %H:%M:%S")

            # Root logger configuration
            root_logger = logging.getLogger()
            root_logger.setLevel(log_level)

            # Remove any existing handlers to avoid duplication if called multiple times
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
                handler.close()

            # Console Handler with EmojiFormatter
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_formatter = EmojiFormatter(fmt=console_format, datefmt=date_format)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

            # File Handler
            file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter(fmt=file_format, datefmt=date_format)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

            # Clean up old log files (optional)
            max_log_files = config_manager.get('logging.max_log_files', 10)
            existing_logs = sorted(logs_dir.glob('log-*.log'), key=os.path.getmtime, reverse=True)
            for old_log in existing_logs[max_log_files:]:
                try:
                    old_log.unlink()
                except OSError as e:
                    root_logger.warning(f"🟡 Could not delete old log file {old_log}: {e}")

            root_logger.info(f"🟢 Logging initialized. Level: {log_level_str}. Log file: {log_file_path}")

        # Example of how to get a logger in other modules:
        # import logging
        # logger = logging.getLogger(__name__)
        # logger.info("This is an info message")
        ```
    *   The `setup_logging` function will be called early in `main.py`.

---

#### 9. `src/purse/utils/common.py`
*   **File Path**: `src/purse/utils/common.py`
*   **Intent**: Contains common utility functions and decorators.
*   **Upstream Dependencies**: `uuid`, `datetime`, `time`, `functools`, `asyncio`, `logging`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: Various service modules.
*   **Changes Needed**:
    *   Create the file.
    *   Add imports:
        ```python
        import uuid
        from datetime import datetime, timezone, timedelta
        import time
        import functools
        import asyncio
        import logging
        import random
        from typing import Callable, Any, TypeVar, Coroutine
        from purse.config_manager import ConfigManager # Or pass config values directly

        logger = logging.getLogger(__name__)
        R = TypeVar('R') # Return type for decorator
        ```
    *   `generate_uuid()` function:
        ```python
        def generate_uuid() -> str:
            return str(uuid.uuid4())
        ```
    *   `get_current_timestamp_iso()` function:
        ```python
        def get_current_timestamp_iso() -> str:
            return datetime.now(timezone.utc).isoformat()
        ```
    *   `parse_iso_timestamp()` function:
        ```python
        def parse_iso_timestamp(timestamp_str: str) -> datetime:
            return datetime.fromisoformat(timestamp_str)
        ```
    *   `exponential_backoff_retry` decorator (sync and async versions):
        ```python
        def exponential_backoff_retry(
            max_attempts: int = 5, # Default, can be overridden by config
            initial_delay: float = 1.0,
            max_delay: float = 60.0,
            jitter: bool = True
        ) -> Callable[..., Callable[..., R | Coroutine[Any, Any, R]]]: # Complex type hint for decorator
            """
            Decorator for retrying a function with exponential backoff.
            Works for both synchronous and asynchronous functions.
            Uses config for defaults if available, otherwise uses decorator args.
            """
            # In a real app, you might fetch these from ConfigManager instance
            # For simplicity, this example assumes they are passed or default.

            def decorator(func: Callable[..., R | Coroutine[Any, Any, R]]) -> Callable[..., R | Coroutine[Any, Any, R]]:
                @functools.wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> R:
                    attempt = 0
                    current_delay = initial_delay
                    while attempt < max_attempts:
                        attempt += 1
                        try:
                            return await func(*args, **kwargs)
                        except Exception as e:
                            logger.warning(f"🟡 Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}")
                            if attempt == max_attempts:
                                logger.error(f"🛑 All {max_attempts} attempts failed for {func.__name__}.")
                                raise
                            
                            delay_with_jitter = current_delay
                            if jitter:
                                delay_with_jitter += random.uniform(0, current_delay * 0.1) # up to 10% jitter
                            
                            logger.info(f"Retrying {func.__name__} in {delay_with_jitter:.2f} seconds...")
                            await asyncio.sleep(delay_with_jitter)
                            current_delay = min(current_delay * 2, max_delay)
                    # This part should not be reached if max_attempts > 0, due to raise in loop
                    raise RuntimeError(f"Retry logic completed without success or error for {func.__name__}")


                @functools.wraps(func)
                def sync_wrapper(*args: Any, **kwargs: Any) -> R:
                    attempt = 0
                    current_delay = initial_delay
                    while attempt < max_attempts:
                        attempt += 1
                        try:
                            # Type assertion for sync function's return type
                            result: R = func(*args, **kwargs) # type: ignore
                            return result
                        except Exception as e:
                            logger.warning(f"🟡 Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}")
                            if attempt == max_attempts:
                                logger.error(f"🛑 All {max_attempts} attempts failed for {func.__name__}.")
                                raise
                            
                            delay_with_jitter = current_delay
                            if jitter:
                                delay_with_jitter += random.uniform(0, current_delay * 0.1) # up to 10% jitter

                            logger.info(f"Retrying {func.__name__} in {delay_with_jitter:.2f} seconds...")
                            time.sleep(delay_with_jitter)
                            current_delay = min(current_delay * 2, max_delay)
                    # This part should not be reached
                    raise RuntimeError(f"Retry logic completed without success or error for {func.__name__}")

                if asyncio.iscoroutinefunction(func):
                    return async_wrapper # type: ignore
                else:
                    return sync_wrapper # type: ignore
            return decorator

        def get_retry_config(config_manager: 'ConfigManager') -> Dict[str, Any]:
            return {
                "max_attempts": config_manager.get('retry.max_attempts', 5),
                "initial_delay": config_manager.get('retry.initial_delay_seconds', 1.0),
                "max_delay": config_manager.get('retry.max_delay_seconds', 60.0)
            }
        ```
    *   `calculate_estimated_read_time(word_count: int) -> int`:
        ```python
        from purse.utils.constants import WORDS_PER_MINUTE
        def calculate_estimated_read_time(word_count: int) -> int:
            if word_count <= 0:
                return 0
            return max(1, round(word_count / WORDS_PER_MINUTE)) # Ensure at least 1 minute for very short texts
        ```
    *   `sanitize_filename(filename: str) -> str`:
        ```python
        import re
        def sanitize_filename(filename: str) -> str:
            """Sanitizes a string to be a valid filename."""
            # Remove invalid characters
            filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
            # Remove leading/trailing whitespace and periods
            filename = filename.strip(' .')
            # Limit length (optional, but good practice)
            max_len = 200 # Max length for filename part
            if len(filename) > max_len:
                name, ext = os.path.splitext(filename)
                name = name[:max_len - len(ext) -1] # -1 for the dot
                filename = name + ext
            if not filename: # if it becomes empty
                filename = "untitled"
            return filename
        ```

---

#### 10. `src/purse/models/article.py`
*   **File Path**: `src/purse/models/article.py`
*   **Intent**: Defines the data structure for an article.
*   **Upstream Dependencies**: `dataclasses`, `typing`, `datetime`, `src/purse/utils/constants.py`, `src/purse/utils/common.py`.
*   **Downstream Dependencies**: `markdown_handler.py`, `content_parser.py`, service modules, UI.
*   **Changes Needed**:
    *   Create `src/purse/models/__init__.py` (empty).
    *   Create `src/purse/models/article.py`.
    *   Add imports:
        ```python
        from dataclasses import dataclass, field
        from typing import List, Optional, Dict, Any
        from datetime import datetime

        from purse.utils import constants
        from purse.utils.common import generate_uuid, get_current_timestamp_iso
        ```
    *   Define `Article` dataclass with `slots=True`:
        ```python
        @dataclass(slots=True)
        class Article:
            # Core metadata from PRD 5.2
            id: str = field(default_factory=generate_uuid)
            original_url: str
            title: str
            pocket_id: Optional[str] = None
            author: Optional[List[str]] = field(default_factory=list) # Allow multiple authors
            publication_name: Optional[str] = None
            publication_date: Optional[str] = None # ISO 8601 string
            saved_date: str = field(default_factory=get_current_timestamp_iso) # ISO 8601 string
            last_modified_date: str = field(default_factory=get_current_timestamp_iso) # ISO 8601 string
            status: str = constants.STATUS_UNREAD
            favorite: bool = False
            tags: List[str] = field(default_factory=list)
            estimated_read_time_minutes: Optional[int] = None
            word_count: Optional[int] = None
            language: Optional[str] = None
            excerpt: Optional[str] = None
            source_application: str = constants.SOURCE_WEB_PARSER # Default source
            archived_from_fallback: bool = False
            thumbnail_url_local: Optional[str] = None # Relative path to local thumbnail

            # Content
            markdown_content: str = "" # Main article body in Markdown
            # Highlights are embedded in markdown_content as ==highlighted text==
            # Notes are appended to markdown_content under "## My Notes"

            # Local state, not necessarily in YAML frontmatter, but useful for app logic
            local_path: Optional[str] = None # Path to the .md file on local disk

            def __post_init__(self):
                # Ensure list types are actually lists if loaded from somewhere else
                if self.author is None: self.author = []
                if self.tags is None: self.tags = []
                # Update last_modified_date on any significant change (handled by services)

            def to_dict(self) -> Dict[str, Any]:
                """Converts Article to a dictionary suitable for YAML frontmatter."""
                data = {
                    constants.KEY_ID: self.id,
                    constants.KEY_ORIGINAL_URL: self.original_url,
                    constants.KEY_TITLE: self.title,
                    constants.KEY_POCKET_ID: self.pocket_id,
                    constants.KEY_AUTHOR: self.author,
                    constants.KEY_PUBLICATION_NAME: self.publication_name,
                    constants.KEY_PUBLICATION_DATE: self.publication_date,
                    constants.KEY_SAVED_DATE: self.saved_date,
                    constants.KEY_LAST_MODIFIED_DATE: self.last_modified_date,
                    constants.KEY_STATUS: self.status,
                    constants.KEY_FAVORITE: self.favorite,
                    constants.KEY_TAGS: self.tags,
                    constants.KEY_ESTIMATED_READ_TIME: self.estimated_read_time_minutes,
                    constants.KEY_WORD_COUNT: self.word_count,
                    constants.KEY_LANGUAGE: self.language,
                    constants.KEY_EXCERPT: self.excerpt,
                    constants.KEY_SOURCE_APPLICATION: self.source_application,
                    constants.KEY_ARCHIVED_FROM_FALLBACK: self.archived_from_fallback,
                    constants.KEY_THUMBNAIL_URL_LOCAL: self.thumbnail_url_local,
                }
                # Remove None values for cleaner YAML, except for those explicitly allowed to be null
                return {k: v for k, v in data.items() if v is not None or k in [
                    constants.KEY_POCKET_ID, constants.KEY_AUTHOR, constants.KEY_PUBLICATION_NAME,
                    constants.KEY_PUBLICATION_DATE, constants.KEY_ESTIMATED_READ_TIME,
                    constants.KEY_WORD_COUNT, constants.KEY_LANGUAGE, constants.KEY_EXCERPT,
                    constants.KEY_THUMBNAIL_URL_LOCAL
                ]} # Pocket_id can be null, author can be empty list (becomes null in YAML if empty)

            @classmethod
            def from_dict(cls, data: Dict[str, Any], markdown_content: str = "", local_path: Optional[str] = None) -> 'Article':
                """Creates an Article instance from a dictionary (YAML frontmatter) and content."""
                # Handle potential missing keys with defaults or None
                return cls(
                    id=data.get(constants.KEY_ID, generate_uuid()),
                    original_url=data.get(constants.KEY_ORIGINAL_URL, ""), # original_url is mandatory
                    title=data.get(constants.KEY_TITLE, "Untitled"), # title is mandatory
                    pocket_id=data.get(constants.KEY_POCKET_ID),
                    author=data.get(constants.KEY_AUTHOR, []),
                    publication_name=data.get(constants.KEY_PUBLICATION_NAME),
                    publication_date=data.get(constants.KEY_PUBLICATION_DATE),
                    saved_date=data.get(constants.KEY_SAVED_DATE, get_current_timestamp_iso()),
                    last_modified_date=data.get(constants.KEY_LAST_MODIFIED_DATE, get_current_timestamp_iso()),
                    status=data.get(constants.KEY_STATUS, constants.STATUS_UNREAD),
                    favorite=data.get(constants.KEY_FAVORITE, False),
                    tags=data.get(constants.KEY_TAGS, []),
                    estimated_read_time_minutes=data.get(constants.KEY_ESTIMATED_READ_TIME),
                    word_count=data.get(constants.KEY_WORD_COUNT),
                    language=data.get(constants.KEY_LANGUAGE),
                    excerpt=data.get(constants.KEY_EXCERPT),
                    source_application=data.get(constants.KEY_SOURCE_APPLICATION, constants.SOURCE_WEB_PARSER),
                    archived_from_fallback=data.get(constants.KEY_ARCHIVED_FROM_FALLBACK, False),
                    thumbnail_url_local=data.get(constants.KEY_THUMBNAIL_URL_LOCAL),
                    markdown_content=markdown_content,
                    local_path=local_path
                )

            def get_notes(self) -> str:
                """Extracts notes from the markdown_content."""
                parts = self.markdown_content.split(f"\n{constants.MARKDOWN_NOTES_HEADING}\n", 1)
                return parts[1] if len(parts) > 1 else ""

            def set_notes(self, notes_content: str) -> None:
                """Sets or updates notes in the markdown_content."""
                base_content = self.markdown_content.split(f"\n{constants.MARKDOWN_NOTES_HEADING}\n", 1)[0]
                if notes_content.strip():
                    self.markdown_content = f"{base_content.strip()}\n\n{constants.MARKDOWN_NOTES_HEADING}\n{notes_content.strip()}"
                else: # Remove notes section if content is empty
                    self.markdown_content = base_content.strip()
                self.last_modified_date = get_current_timestamp_iso()

            def get_content_without_notes(self) -> str:
                """Returns markdown content excluding the notes section."""
                return self.markdown_content.split(f"\n{constants.MARKDOWN_NOTES_HEADING}\n", 1)[0].strip()

            # Methods for highlights could be added if direct manipulation is needed,
            # but PRD implies they are just embedded markup `==text==`.
        ```

---

### Phase 2: Core Service Implementation

#### 11. `src/purse/services/http_client.py`
*   **File Path**: `src/purse/services/http_client.py`
*   **Intent**: Provides a standardized and robust asynchronous HTTP client for fetching web content.
*   **Upstream Dependencies**: `httpx`, `asyncio`, `logging`, `src/purse/utils/common.py`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: `content_parser.py`, `notification_service.py`, cloud storage SDKs (if not using their built-in clients).
*   **Changes Needed**:
    *   Create `src/purse/services/__init__.py` (empty).
    *   Create `src/purse/services/http_client.py`.
    *   Add imports:
        ```python
        import httpx
        import asyncio
        import logging
        from typing import Optional, Dict, Any, TYPE_CHECKING

        from purse.utils.common import exponential_backoff_retry, get_retry_config

        if TYPE_CHECKING:
            from purse.config_manager import ConfigManager

        logger = logging.getLogger(__name__)
        ```
    *   Define `HttpClient` class:
        ```python
        class HttpClient:
            def __init__(self, config_manager: 'ConfigManager'):
                self.config_manager = config_manager
                self.client = httpx.AsyncClient(
                    http2=True, # Enable HTTP/2 if server supports
                    timeout=30.0, # Default timeout
                    follow_redirects=True,
                    headers={"User-Agent": "Purse Read-It-Later App/1.0"} # Basic User-Agent
                )
                self.retry_config = get_retry_config(self.config_manager)

            @exponential_backoff_retry # Uses defaults or args passed here
            async def get_url(
                self,
                url: str,
                headers: Optional[Dict[str, str]] = None,
                params: Optional[Dict[str, Any]] = None,
                timeout: Optional[float] = None
            ) -> httpx.Response:
                """Fetches content from a URL with retry logic."""
                # Decorator needs access to config, or pass config values to it.
                # The decorator defined in common.py can be made to accept config_manager or specific retry params.
                # For now, using decorator with its own defaults or passed args if modified.
                # Let's assume the decorator `exponential_backoff_retry` is configured via `get_retry_config` or its arguments.

                # To use config from self.retry_config:
                # Create a local decorator instance or directly implement retry logic here.
                # This example will assume the global decorator is sufficient or it's adapted.

                effective_headers = self.client.headers.copy()
                if headers:
                    effective_headers.update(headers)

                logger.debug(f"Fetching URL: {url} with params: {params}")
                try:
                    response = await self.client.get(
                        url,
                        headers=effective_headers,
                        params=params,
                        timeout=timeout if timeout is not None else self.client.timeout.read # type: ignore
                    )
                    response.raise_for_status() # Raise HTTPStatusError for 4xx/5xx responses
                    logger.info(f"🟢 Successfully fetched {url}, status: {response.status_code}")
                    return response
                except httpx.HTTPStatusError as e:
                    logger.error(f"🛑 HTTP error {e.response.status_code} for {url}: {e.response.text[:200]}")
                    raise
                except httpx.RequestError as e:
                    logger.error(f"🛑 Request error for {url}: {e}")
                    raise
                except Exception as e:
                    logger.error(f"🛑 Unexpected error fetching {url}: {e}")
                    raise

            async def close(self) -> None:
                await self.client.aclose()

        # Example usage (in another service):
        # async with HttpClient(config_manager) as http_client:
        #     response = await http_client.get_url("https://example.com")
        #     content = response.text
        ```
    *   Ensure the `exponential_backoff_retry` decorator is properly applied and configured using values from `config_manager`. The decorator in `common.py` needs to be flexible enough or `HttpClient` needs to instantiate it with config.
    *   The `@exponential_backoff_retry` should ideally take `config_manager` or the retry params directly, or be a method within `HttpClient` itself.
        Revisiting `exponential_backoff_retry`:
        It might be better to pass retry params directly to the decorator instance.
        ```python
        # In HttpClient's __init__
        self.retry_decorator = exponential_backoff_retry(
            max_attempts=self.retry_config['max_attempts'],
            initial_delay=self.retry_config['initial_delay'],
            max_delay=self.retry_config['max_delay']
        )

        # In HttpClient's get_url
        # @self.retry_decorator
        # async def get_url(...):
        # Note: This makes the method definition dynamic, which can be tricky.
        # A simpler way is to call a helper that is decorated, or implement the loop directly in get_url.
        # For simplicity, let's assume the decorator is applied as shown and the decorator implementation
        # can access config or is passed params. The current `common.py` decorator takes args.
        ```
        The simplest approach for now is to call the decorator factory:
        ```python
        # In HttpClient:
        async def get_url(self, url: str, ...) -> httpx.Response:
            retry_params = get_retry_config(self.config_manager)
            
            @exponential_backoff_retry(
                max_attempts=retry_params['max_attempts'],
                initial_delay=retry_params['initial_delay'],
                max_delay=retry_params['max_delay']
            )
            async def _fetch():
                # ... actual fetch logic ... (as in the original get_url body)
                effective_headers = self.client.headers.copy()
                if headers: effective_headers.update(headers)
                logger.debug(f"Fetching URL: {url} with params: {params}")
                response = await self.client.get(url, headers=effective_headers, params=params, timeout=timeout if timeout is not None else self.client.timeout.read) # type: ignore
                response.raise_for_status()
                logger.info(f"🟢 Successfully fetched {url}, status: {response.status_code}")
                return response
            
            try:
                return await _fetch()
            except httpx.HTTPStatusError as e:
                # Already logged by decorator, re-raise or handle
                raise
            except httpx.RequestError as e:
                raise
            except Exception as e: # Catch-all from decorator's final failure
                logger.error(f"🛑 Unexpected error fetching {url} after retries: {e}")
                raise
        ```

---

#### 12. `src/purse/services/markdown_handler.py`
*   **File Path**: `src/purse/services/markdown_handler.py`
*   **Intent**: Handles creation, parsing, and manipulation of Markdown files with YAML frontmatter for articles.
*   **Upstream Dependencies**: `PyYAML`, `pathlib`, `logging`, `src/purse/models/article.py`, `src/purse/utils/constants.py`, `src/purse/utils/common.py`.
*   **Downstream Dependencies**: `file_system_manager.py`, `content_parser.py`, `sync_manager.py`, `pocket_importer.py`.
*   **Changes Needed**:
    *   Create the file.
    *   Add imports:
        ```python
        import yaml
        from pathlib import Path
        import logging
        from typing import Tuple, Optional

        from purse.models.article import Article
        from purse.utils import constants, common

        logger = logging.getLogger(__name__)
        ```
    *   Define `MarkdownHandler` class:
        ```python
        class MarkdownHandler:
            @staticmethod
            def parse_markdown_file(file_path: Path) -> Optional[Article]:
                """Parses a Markdown file into an Article object."""
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except FileNotFoundError:
                    logger.error(f"🛑 Markdown file not found: {file_path}")
                    return None
                except Exception as e:
                    logger.error(f"🛑 Error reading Markdown file {file_path}: {e}")
                    return None

                try:
                    # Split frontmatter and content
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) < 3:
                             logger.warning(f"🟡 Malformed YAML frontmatter in {file_path}. Treating as no frontmatter.")
                             frontmatter_str = ""
                             body_content = content.strip()
                        else:
                            frontmatter_str = parts[1]
                            body_content = parts[2].strip()
                        
                        frontmatter = yaml.safe_load(frontmatter_str) if frontmatter_str.strip() else {}
                    else:
                        frontmatter = {}
                        body_content = content.strip()
                    
                    # Ensure essential keys if building from scratch file with no frontmatter
                    if not frontmatter.get(constants.KEY_ORIGINAL_URL) and not frontmatter.get(constants.KEY_TITLE):
                        # This might be a file not managed by Purse, or severely corrupted.
                        # Decide policy: create a basic Article, or return None.
                        # For now, if it's from a path, it should ideally have some data.
                        logger.warning(f"🟡 File {file_path} lacks essential metadata (URL/Title). Attempting to create basic Article.")
                        # Could try to infer title from filename if desired.
                        # title_from_filename = file_path.stem
                        # frontmatter[constants.KEY_TITLE] = title_from_filename

                    # If original_url is missing, it's problematic.
                    if not frontmatter.get(constants.KEY_ORIGINAL_URL):
                        logger.warning(f"🟡 Missing original_url in {file_path}. Article may not be fully functional.")
                        # Handle this based on how strict the app needs to be.

                    article = Article.from_dict(frontmatter, body_content, local_path=str(file_path))
                    return article

                except yaml.YAMLError as e:
                    logger.error(f"🛑 YAML parsing error in {file_path}: {e}")
                    return None
                except Exception as e:
                    logger.error(f"🛑 Error processing Markdown file {file_path}: {e}")
                    return None

            @staticmethod
            def article_to_markdown_text(article: Article) -> str:
                """Converts an Article object to its Markdown string representation (frontmatter + content)."""
                frontmatter_dict = article.to_dict()
                # Remove keys that are not part of frontmatter or are derived (like local_path)
                # to_dict should already handle this.

                try:
                    # Ensure authors and tags are lists for YAML dump
                    if 'author' in frontmatter_dict and frontmatter_dict['author'] is None:
                        frontmatter_dict['author'] = []
                    if 'tags' in frontmatter_dict and frontmatter_dict['tags'] is None:
                        frontmatter_dict['tags'] = []

                    frontmatter_str = yaml.dump(
                        frontmatter_dict,
                        sort_keys=False,
                        allow_unicode=True,
                        default_flow_style=False,
                        width=80 # For readability
                    )
                except Exception as e:
                    logger.error(f"🛑 Error serializing frontmatter for article {article.id}: {e}")
                    frontmatter_str = "# Error in frontmatter serialization\n"

                # Ensure notes are correctly formatted
                content_without_notes = article.get_content_without_notes()
                notes = article.get_notes()

                full_markdown_content = content_without_notes
                if notes:
                    full_markdown_content += f"\n\n{constants.MARKDOWN_NOTES_HEADING}\n{notes}"

                return f"---\n{frontmatter_str}---\n\n{full_markdown_content.strip()}"

            @staticmethod
            def save_article_to_file(article: Article, file_path: Path) -> bool:
                """Saves an Article object to a Markdown file."""
                markdown_text = MarkdownHandler.article_to_markdown_text(article)
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_text)
                    article.local_path = str(file_path) # Update local path on successful save
                    logger.info(f"🟢 Article '{article.title}' saved to {file_path}")
                    return True
                except Exception as e:
                    logger.error(f"🛑 Error saving article '{article.title}' to {file_path}: {e}")
                    return False

            @staticmethod
            def extract_highlights(markdown_content: str) -> List[str]:
                """Extracts highlighted text (==text==) from markdown."""
                import re # Local import for this specific method
                # A more robust regex might be needed for nested or complex cases
                # This regex finds text between == and ==, non-greedily.
                return re.findall(r'{0}(.*?){1}'.format(
                    re.escape(constants.MARKDOWN_HIGHLIGHT_START_TAG),
                    re.escape(constants.MARKDOWN_HIGHLIGHT_END_TAG)
                ), markdown_content)
        ```

#### 13. `src/purse/services/content_parser.py`
*   **File Path**: `src/purse/services/content_parser.py`
*   **Intent**: Responsible for fetching web content, parsing articles from HTML, extracting text from PDF/DOCX files, and creating `Article` objects.
*   **Upstream Dependencies**: `trafilatura`, `PyMuPDF`, `python-docx`, `logging`, `io`, `datetime`, `langdetect` (optional, for language detection if `trafilatura` doesn't provide it well enough), `src/purse/models/article.py`, `src/purse/services/http_client.py`, `src/purse/utils/common.py`, `src/purse/utils/constants.py`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: `file_system_manager.py` (indirectly, by providing `Article` objects to be saved), `pocket_importer.py`, UI actions for adding new articles.
*   **Changes Needed**:
    *   Create the file.
    *   Add imports:
        ```python
        import trafilatura
        import fitz # PyMuPDF
        import docx # python-docx
        import logging
        import io
        from datetime import datetime, timezone
        from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING, List
        from urllib.parse import urlparse

        from purse.models.article import Article
        from purse.services.http_client import HttpClient
        from purse.utils import common, constants
        # from langdetect import detect as detect_language # Optional, if needed

        if TYPE_CHECKING:
            from purse.config_manager import ConfigManager

        logger = logging.getLogger(__name__)
        ```
    *   Define `ContentParserService` class:
        ```python
        class ContentParserService:
            def __init__(self, http_client: HttpClient, config_manager: 'ConfigManager'):
                self.http_client = http_client
                self.config_manager = config_manager
                self.retry_config = common.get_retry_config(self.config_manager)

            def _extract_metadata_from_trafilatura(self, result: Optional[str], url: str) -> Tuple[str, Dict[str, Any]]:
                """Helper to extract metadata if trafilatura provides it (often in comments or via options)."""
                # Trafilatura primarily gives main content. Metadata extraction might be basic.
                # For more advanced metadata (author, pub date), Trafilatura might not be enough alone.
                # Consider using `newspaper3k` for metadata if trafilatura is insufficient,
                # or focus on what trafilatura provides directly.
                # For now, assume basic metadata extraction.
                parsed_url = urlparse(url)
                metadata = {
                    constants.KEY_AUTHOR: None,
                    constants.KEY_PUBLICATION_NAME: parsed_url.netloc, # Default to domain
                    constants.KEY_PUBLICATION_DATE: None,
                    constants.KEY_TITLE: "Untitled Article", # Placeholder
                    constants.KEY_LANGUAGE: None,
                    constants.KEY_EXCERPT: None,
                }
                cleaned_content = result if result else ""

                # Try to get title from Trafilatura (if it has an option or if it's in the output)
                # Trafilatura's extract function can return a dict with metadata if include_metadata=True
                # For simplicity, let's assume we call `trafilatura.extract` with metadata flags where possible.
                # If `result` is just text, we might need to parse it for title if it's embedded.
                # The PRD says "Trafilatura ... converting it to clean Markdown".
                # Trafilatura can output Markdown.

                # Example: if trafilatura was called with include_metadata=True and returned a dict:
                # if isinstance(result, dict): # This is a hypothetical structure for trafilatura's output
                #     cleaned_content = result.get("text", "")
                #     metadata[constants.KEY_TITLE] = result.get("title", "Untitled Article")
                #     metadata[constants.KEY_AUTHOR] = result.get("author") # Might be a string or list
                #     metadata[constants.KEY_PUBLICATION_DATE] = result.get("date")
                #     metadata[constants.KEY_PUBLICATION_NAME] = result.get("sitename", parsed_url.netloc)
                #     metadata[constants.KEY_EXCERPT] = result.get("excerpt")
                # else: # result is just string content
                #     # Fallback for title: Try to find H1 in the beginning of cleaned_content (if HTML output)
                #     # If Markdown output, title might be `# Title`
                #     pass

                # For this plan, we assume `trafilatura.extract` is used with `output_format='markdown'`
                # and `include_metadata=True` if available, or we parse separately.
                # Let's simplify: we get markdown, and a separate metadata dict.
                # Trafilatura's `extract` can take `include_formatting=True` for markdown like output.
                # `include_comments=False` to remove metadata usually in comments.
                # Let's refine this with a more direct use of trafilatura's known capabilities.

                # For now, this helper is a placeholder for how metadata is gathered.
                # The main parsing methods will populate it more directly.

                return cleaned_content, metadata

            async def parse_url(self, url: str, use_fallback: bool = True) -> Optional[Article]:
                """
                Fetches and parses content from a web URL.
                Uses Trafilatura primarily. Can use archive.is as fallback.
                """
                logger.info(f"🟢 Attempting to parse URL: {url}")
                is_archived = False
                content_html: Optional[str] = None

                try:
                    # Decorate the actual fetch, not the whole method
                    @common.exponential_backoff_retry(
                        max_attempts=self.retry_config['max_attempts'],
                        initial_delay=self.retry_config['initial_delay'],
                        max_delay=self.retry_config['max_delay']
                    )
                    async def _fetch_direct(target_url: str) -> str:
                        response = await self.http_client.get_url(target_url)
                        return response.text

                    content_html = await _fetch_direct(url)

                except Exception as e:
                    logger.warning(f"🟡 Failed to fetch directly from {url}: {e}")
                    if not use_fallback:
                        logger.error(f"🛑 Fallback disabled, parsing failed for {url}.")
                        return None
                    
                    # Fallback mechanism
                    archive_template = self.config_manager.get('fallback_archive_service_url_template')
                    if archive_template:
                        archive_url = archive_template.format(url=url)
                        logger.info(f"Attempting fallback fetch from: {archive_url}")
                        try:
                            # No retry decorator on the fallback itself, or a more limited one
                            response = await self.http_client.get_url(archive_url, timeout=60.0) # Longer timeout for archive
                            content_html = response.text
                            is_archived = True
                            logger.info(f"🟢 Successfully fetched from fallback: {archive_url}")
                        except Exception as arc_e:
                            logger.error(f"🛑 Fallback fetch also failed for {url} from {archive_url}: {arc_e}")
                            return None
                    else:
                        logger.error(f"🛑 Fallback service URL template not configured. Cannot use fallback for {url}.")
                        return None

                if not content_html:
                    logger.error(f"🛑 No HTML content fetched for {url}.")
                    return None

                # Parse with Trafilatura
                # PRD: "extracting main article content ... and converting it to clean Markdown"
                # output_format='markdown' is key. include_links=True is good.
                # include_formatting=True gives more markdown-like output for formatting.
                # include_metadata=True is important.
                try:
                    # Using `extract` which can return dict with metadata.
                    # However, the PRD asks for clean Markdown.
                    # Let's use `bare_extraction` and get metadata separately if needed,
                    # or rely on `extract` and then reformat its structured output.
                    # The simplest is to get Markdown and a title.
                    
                    # Option 1: Get Markdown and some metadata separately
                    # markdown_content = trafilatura.extract(content_html,
                    #                                       output_format='markdown',
                    #                                       include_links=True,
                    #                                       include_formatting=True, # for bold, italics etc.
                    #                                       include_images=True, # if we want image links
                    #                                       favor_recall=True) # Tries to get more content
                    # extracted_metadata = trafilatura.extract_metadata(content_html) # May be limited

                    # Option 2: Use `bare_extraction` and get metadata (potentially more robust)
                    # This returns a dictionary with 'text', 'title', 'author', 'date', 'sitename', 'tags', etc.
                    extracted_data = trafilatura.bare_extraction(
                        content_html,
                        include_links=True,
                        include_formatting=True, # for markdown-like structures within text
                        include_images=True, # if we want image links in markdown
                        output_format='markdown', # Ensures 'text' field is markdown
                        deduplicate=True
                    )

                    if not extracted_data or not extracted_data.get('text'):
                        logger.warning(f"🟡 Trafilatura extracted no main content from {url}. Might be non-article page.")
                        # Create a bookmark instead as per PRD 5.1
                        page_title = trafilatura.extract_metadata(content_html, default="Bookmark")
                        if page_title and hasattr(page_title, 'title'): page_title = page_title.title # type: ignore
                        elif not isinstance(page_title, str): page_title = url

                        return Article(
                            original_url=url,
                            title=str(page_title if page_title else "Bookmark: " + url),
                            markdown_content=f"# Bookmark\n\nOriginal URL: [{url}]({url})",
                            source_application=constants.SOURCE_BOOKMARK,
                            archived_from_fallback=is_archived,
                            # word_count and estimated_read_time_minutes will be 0 or None
                        )

                    markdown_content = extracted_data.get('text', "")
                    article_title = extracted_data.get('title') or "Untitled Article"
                    
                    # Extract other metadata from `extracted_data`
                    authors_str = extracted_data.get('author')
                    authors_list = [a.strip() for a in authors_str.split(',')] if authors_str else []
                    
                    publication_name = extracted_data.get('sitename')
                    publication_date_str = extracted_data.get('date') # Expects YYYY-MM-DD

                    # Language detection (Trafilatura might do this, or use langdetect)
                    language = extracted_data.get('language') # Check if Trafilatura provides this
                    # if not language and markdown_content:
                    #     try: language = detect_language(markdown_content[:500])
                    #     except: language = None


                    word_count = len(markdown_content.split())
                    estimated_read_time = common.calculate_estimated_read_time(word_count)

                    article = Article(
                        original_url=url,
                        title=article_title,
                        author=authors_list,
                        publication_name=publication_name,
                        publication_date=publication_date_str, # Ensure ISO 8601 if converting
                        markdown_content=markdown_content.strip(),
                        word_count=word_count,
                        estimated_read_time_minutes=estimated_read_time,
                        language=language,
                        excerpt=extracted_data.get('excerpt'), # trafilatura might provide this
                        source_application=constants.SOURCE_WEB_PARSER,
                        archived_from_fallback=is_archived
                    )
                    logger.info(f"🟢 Successfully parsed article: '{article.title}' from {url}")
                    return article

                except Exception as e:
                    logger.error(f"🛑 Trafilatura parsing failed for {url}: {e}")
                    # Fallback to creating a bookmark if parsing fails catastrophically after fetch
                    try:
                        metadata = trafilatura.extract_metadata(content_html)
                        title = getattr(metadata, 'title', url) if metadata else url
                    except:
                        title = url # Failsafe title
                    
                    return Article(
                        original_url=url,
                        title=f"Bookmark (Parsing Failed): {title}",
                        markdown_content=f"# Bookmark (Content Parsing Failed)\n\nOriginal URL: [{url}]({url})\n\nError during parsing: {str(e)}",
                        source_application=constants.SOURCE_BOOKMARK,
                        archived_from_fallback=is_archived
                    )


            def parse_pdf_from_bytes(self, pdf_bytes: bytes, original_url: str = "local.pdf") -> Optional[Article]:
                """Extracts text from PDF bytes and creates an Article object."""
                logger.info(f"🟢 Attempting to parse PDF: {original_url}")
                try:
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    text_content = ""
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        text_content += page.get_text("text") + "\n\n" # Add space between pages
                    doc.close()

                    if not text_content.strip():
                        logger.warning(f"🟡 No text extracted from PDF: {original_url}")
                        # Create a bookmark-like entry for empty PDFs
                        return Article(
                            original_url=original_url,
                            title=f"PDF (No Text Content): {Path(original_url).name}",
                            markdown_content=f"# PDF Document\n\nOriginal source: {original_url}\n\nNo text content could be extracted.",
                            source_application=constants.SOURCE_PDF_IMPORT
                        )

                    # Use filename as title if no other title is available
                    title_from_url = Path(original_url).stem.replace('_', ' ').replace('-', ' ')

                    word_count = len(text_content.split())
                    estimated_read_time = common.calculate_estimated_read_time(word_count)

                    article = Article(
                        original_url=original_url,
                        title=title_from_url,
                        markdown_content=text_content.strip(),
                        word_count=word_count,
                        estimated_read_time_minutes=estimated_read_time,
                        source_application=constants.SOURCE_PDF_IMPORT
                        # Other metadata like author, pub_date might be hard to get from PDF raw text
                    )
                    logger.info(f"🟢 Successfully parsed PDF: {original_url}")
                    return article
                except Exception as e:
                    logger.error(f"🛑 PDF parsing failed for {original_url}: {e}")
                    return None

            def parse_docx_from_bytes(self, docx_bytes: bytes, original_url: str = "local.docx") -> Optional[Article]:
                """Extracts text from DOCX bytes and creates an Article object."""
                logger.info(f"🟢 Attempting to parse DOCX: {original_url}")
                try:
                    document = docx.Document(io.BytesIO(docx_bytes))
                    text_content = "\n\n".join([para.text for para in document.paragraphs])

                    if not text_content.strip():
                        logger.warning(f"🟡 No text extracted from DOCX: {original_url}")
                        return Article(
                            original_url=original_url,
                            title=f"DOCX (No Text Content): {Path(original_url).name}",
                            markdown_content=f"# DOCX Document\n\nOriginal source: {original_url}\n\nNo text content could be extracted.",
                            source_application=constants.SOURCE_DOCX_IMPORT
                        )

                    title_from_url = Path(original_url).stem.replace('_', ' ').replace('-', ' ')

                    word_count = len(text_content.split())
                    estimated_read_time = common.calculate_estimated_read_time(word_count)

                    article = Article(
                        original_url=original_url,
                        title=title_from_url,
                        markdown_content=text_content.strip(),
                        word_count=word_count,
                        estimated_read_time_minutes=estimated_read_time,
                        source_application=constants.SOURCE_DOCX_IMPORT
                    )
                    logger.info(f"🟢 Successfully parsed DOCX: {original_url}")
                    return article
                except Exception as e:
                    logger.error(f"🛑 DOCX parsing failed for {original_url}: {e}")
                    return None

            def create_bookmark_article(self, url: str, title: Optional[str] = None, tags: Optional[List[str]] = None, notes: Optional[str] = None) -> Article:
                """Creates an Article object for a non-textual bookmark."""
                logger.info(f"🟢 Creating bookmark for URL: {url}")
                article_title = title if title else "Bookmark: " + url
                
                markdown_body = f"# Bookmark\n\nOriginal URL: [{url}]({url})"
                if notes: # Notes are added to the main body before the "My Notes" section in Article model
                    markdown_body += f"\n\n{notes}"

                article = Article(
                    original_url=url,
                    title=article_title,
                    tags=tags if tags else [],
                    markdown_content=markdown_body,
                    source_application=constants.SOURCE_BOOKMARK,
                    # word_count and estimated_read_time_minutes will be 0 or None
                )
                # If `notes` were provided for the main content part of the bookmark,
                # and the user also wants to use the ## My Notes section, that's handled by article.set_notes() later.
                return article

        ```
    *   Add `from pathlib import Path` to imports.
    *   Ensure the retry logic for fetching is robust. The `exponential_backoff_retry` decorator should be applied to the fetching part *within* `parse_url`.
    *   Handle cases where `trafilatura` returns None or minimal content (PRD 5.1: create bookmark).
    *   Ensure metadata extraction from `trafilatura` (title, author, pub_date, etc.) is as comprehensive as possible, or note limitations. The `bare_extraction` with `output_format='markdown'` might be best.
    *   For PDF and DOCX, use the filename (derived from `original_url`) as a default title.

---

#### 14. `src/purse/services/file_system_manager.py`
*   **File Path**: `src/purse/services/file_system_manager.py`
*   **Intent**: Manages all local file system operations: storing/retrieving articles, managing thumbnails, paths for search index, logs, and configurations. Ensures "Offline-First Principle" by managing local data.
*   **Upstream Dependencies**: `pathlib`, `os`, `shutil`, `logging`, `src/purse/models/article.py`, `src/purse/services/markdown_handler.py`, `src/purse/config_manager.py`, `src/purse/utils/common.py`.
*   **Downstream Dependencies**: `sync_manager.py`, `search_manager.py`, `pocket_importer.py`, UI components (for file dialogs, accessing local data).
*   **Changes Needed**:
    *   Create the file.
    *   Add imports:
        ```python
        import os
        import shutil
        from pathlib import Path
        import logging
        from typing import Optional, List, TYPE_CHECKING, Tuple

        from purse.models.article import Article
        from purse.services.markdown_handler import MarkdownHandler
        from purse.utils import common

        if TYPE_CHECKING:
            from purse.config_manager import ConfigManager
            from toga import App # For app paths

        logger = logging.getLogger(__name__)
        ```
    *   Define `FileSystemManager` class:
        ```python
        class FileSystemManager:
            def __init__(self, config_manager: 'ConfigManager', toga_app: Optional['App'] = None):
                self.config_manager = config_manager
                self.toga_app = toga_app # Needed for OS-idiomatic paths

                # Base data directory for Purse application (OS-idiomatic)
                if self.toga_app:
                    self.app_data_dir: Path = Path(self.toga_app.paths.data)
                else:
                    # Fallback for non-Toga contexts (e.g., CLI tools, tests)
                    # This should ideally not be used for the main app.
                    self.app_data_dir: Path = Path.home() / ".Purse"
                self.app_data_dir.mkdir(parents=True, exist_ok=True)

                # Local article storage (before cloud sync or as primary if cloud not used)
                # This path is INSIDE the app_data_dir, not the user-selected cloud sync root.
                # This is for the app's own local cache/storage.
                # The actual "library" of .md files will be in the user's chosen cloud sync root.
                # This needs clarification based on PRD:
                # PRD 4. Domain Req: "Offline-First Principle ... content ... must be stored locally on each device."
                # PRD 5.2 Data Storage: "Storage Location: User-specified folder within their chosen cloud storage provider"
                # This implies the primary store IS the cloud folder, which is synced locally.
                # So, `local_articles_dir` should point to the local copy of that cloud folder.

                self._local_sync_root: Optional[Path] = None # Set after user configures cloud sync

                # Path for Whoosh index (within app_data_dir)
                self.search_index_dir: Path = self.app_data_dir / self.config_manager.get(
                    'paths.local_search_index_dir', 'search_index'
                )
                self.search_index_dir.mkdir(parents=True, exist_ok=True)

                # Logs directory (within app_data_dir)
                self.logs_dir: Path = self.app_data_dir / self.config_manager.get('logging.logs_dir', 'logs')
                self.logs_dir.mkdir(parents=True, exist_ok=True)

                # Local, non-synced settings (e.g., window size)
                self.local_device_settings_path: Path = self.app_data_dir / "device_settings.yml"

                # Synced settings path (within the cloud sync root)
                # This path is relative to the sync root.
                self.synced_config_dir_name: str = self.config_manager.get(
                    'paths.synced_config_dir_name', '.purse_config'
                )
                self.synced_settings_filename: str = self.config_manager.get(
                    'paths.synced_settings_filename', 'settings.yml'
                )

            def set_local_sync_root(self, path: Union[str, Path]) -> None:
                """Sets the root directory for the local copy of synced articles."""
                self._local_sync_root = Path(path)
                self._local_sync_root.mkdir(parents=True, exist_ok=True)
                logger.info(f"🟢 Local sync root set to: {self._local_sync_root}")

            def get_local_sync_root(self) -> Optional[Path]:
                if not self._local_sync_root:
                    logger.warning("🟡 Local sync root not yet configured.")
                return self._local_sync_root
            
            def get_synced_settings_path(self) -> Optional[Path]:
                """Path to settings.yml within the sync root."""
                root = self.get_local_sync_root()
                if not root: return None
                return root / self.synced_config_dir_name / self.synced_settings_filename

            def get_article_filepath(self, article: Article, ensure_exists: bool = False) -> Optional[Path]:
                """
                Generates a filepath for an article within the local sync root.
                Filename is based on sanitized title and article ID.
                Example: <sync_root>/My Article Title_abcdef12.md
                """
                sync_root = self.get_local_sync_root()
                if not sync_root:
                    logger.error("🛑 Cannot get article filepath, sync root not set.")
                    return None

                # Sanitize title for filename
                sanitized_title = common.sanitize_filename(article.title)
                # Use first part of UUID for uniqueness but keep it shorter
                short_id = article.id.split('-')[0]
                filename = f"{sanitized_title}_{short_id}.md"
                
                # Articles could be organized into subfolders, e.g., by year/month of save_date
                # For now, flat structure in sync_root.
                article_path = sync_root / filename

                if ensure_exists:
                    article_path.parent.mkdir(parents=True, exist_ok=True)
                return article_path

            def save_article(self, article: Article) -> Optional[Path]:
                """Saves an article to the local sync folder."""
                filepath = self.get_article_filepath(article, ensure_exists=True)
                if not filepath: return None

                if MarkdownHandler.save_article_to_file(article, filepath):
                    article.local_path = str(filepath) # Ensure article object has path
                    return filepath
                return None

            def load_article(self, filepath: Path) -> Optional[Article]:
                """Loads an article from a given filepath."""
                article = MarkdownHandler.parse_markdown_file(filepath)
                if article:
                    article.local_path = str(filepath)
                return article

            def delete_article_file(self, article_or_filepath: Union[Article, Path]) -> bool:
                """Deletes the markdown file for an article."""
                if isinstance(article_or_filepath, Article):
                    filepath_str = article_or_filepath.local_path
                    if not filepath_str:
                        # Try to construct it if not set
                        temp_path = self.get_article_filepath(article_or_filepath)
                        if temp_path: filepath_str = str(temp_path)
                        else:
                            logger.error(f"🛑 Cannot delete article '{article_or_filepath.title}', local path unknown.")
                            return False
                    filepath = Path(filepath_str)
                else:
                    filepath = Path(article_or_filepath)

                if filepath.exists():
                    try:
                        filepath.unlink()
                        logger.info(f"🟢 Deleted article file: {filepath}")
                        return True
                    except Exception as e:
                        logger.error(f"🛑 Error deleting article file {filepath}: {e}")
                        return False
                else:
                    logger.warning(f"🟡 Article file not found for deletion: {filepath}")
                    return False # Or True if "not found" means "already deleted"

            def get_all_article_filepaths(self) -> List[Path]:
                """Returns a list of all .md file paths in the local sync root."""
                sync_root = self.get_local_sync_root()
                if not sync_root: return []
                return list(sync_root.glob("*.md")) # Assuming flat structure for now

            # --- Thumbnail Management (PRD 5.3) ---
            def get_thumbnail_path(self, article: Article, create_subdirs: bool = True) -> Optional[Path]:
                """
                Generates a path for a thumbnail image, relative to the article's .md file
                or in a central thumbnail cache.
                PRD 5.2: thumbnail_url_local: Path to a locally stored thumbnail image relative to the article file.
                Example: <sync_root>/article_filename_thumbnail.jpg
                         <sync_root>/thumbnails/<article_id>.jpg (centralized, easier to manage)

                Let's go with relative to the article file, as per PRD.
                <article_name>_thumb.jpg
                """
                article_md_path_str = article.local_path
                if not article_md_path_str:
                    # If article not saved yet, try to get prospective path
                    temp_article_path = self.get_article_filepath(article)
                    if not temp_article_path:
                        logger.warning(f"🟡 Cannot determine thumbnail path for unsaved article: {article.title}")
                        return None
                    article_md_path = temp_article_path
                else:
                    article_md_path = Path(article_md_path_str)

                # Filename: article_stem + "_thumb" + original_thumb_extension
                # For simplicity, always use .jpg for thumbnails for now.
                thumb_filename = f"{article_md_path.stem}_thumb.jpg"
                # Thumbnails are stored alongside the .md file.
                thumb_path = article_md_path.parent / thumb_filename

                if create_subdirs: # Not strictly needed if same dir as article
                    thumb_path.parent.mkdir(parents=True, exist_ok=True)
                return thumb_path

            def save_thumbnail(self, article: Article, image_bytes: bytes) -> Optional[str]:
                """Saves thumbnail image_bytes and updates article.thumbnail_url_local."""
                thumb_path = self.get_thumbnail_path(article)
                if not thumb_path:
                    return None
                try:
                    with open(thumb_path, 'wb') as f:
                        f.write(image_bytes)
                    # Store path relative to the sync root for portability in YAML.
                    sync_root = self.get_local_sync_root()
                    if sync_root:
                        relative_thumb_path = str(thumb_path.relative_to(sync_root))
                        article.thumbnail_url_local = relative_thumb_path
                        logger.info(f"🟢 Thumbnail saved for '{article.title}' at {thumb_path} (relative: {relative_thumb_path})")
                        return relative_thumb_path
                    else:
                        logger.error("🛑 Cannot determine relative thumbnail path, sync root not set.")
                        return None
                except Exception as e:
                    logger.error(f"🛑 Error saving thumbnail for '{article.title}': {e}")
                    return None

            def get_thumbnail_bytes(self, article: Article) -> Optional[bytes]:
                """Loads thumbnail image bytes."""
                sync_root = self.get_local_sync_root()
                if not sync_root or not article.thumbnail_url_local:
                    return None

                # thumbnail_url_local is relative to sync_root
                thumb_path = sync_root / article.thumbnail_url_local
                if thumb_path.exists():
                    try:
                        with open(thumb_path, 'rb') as f:
                            return f.read()
                    except Exception as e:
                        logger.error(f"🛑 Error reading thumbnail {thumb_path}: {e}")
                return None
            
            def delete_thumbnail(self, article: Article) -> bool:
                sync_root = self.get_local_sync_root()
                if not sync_root or not article.thumbnail_url_local:
                    return False
                
                thumb_path = sync_root / article.thumbnail_url_local
                if thumb_path.exists():
                    try:
                        thumb_path.unlink()
                        logger.info(f"🟢 Deleted thumbnail: {thumb_path}")
                        article.thumbnail_url_local = None # Clear from article model
                        return True
                    except Exception as e:
                        logger.error(f"🛑 Error deleting thumbnail {thumb_path}: {e}")
                return False

            # Load/Save local device-specific settings (e.g., window size)
            def load_device_settings(self) -> Dict:
                if self.local_device_settings_path.exists():
                    try:
                        with open(self.local_device_settings_path, 'r') as f:
                            return yaml.safe_load(f) or {}
                    except Exception as e:
                        logger.error(f"🛑 Error loading device settings: {e}")
                return {}

            def save_device_settings(self, settings: Dict) -> None:
                try:
                    with open(self.local_device_settings_path, 'w') as f:
                        yaml.dump(settings, f, sort_keys=False, indent=2)
                    logger.info(f"🟢 Device settings saved to {self.local_device_settings_path}")
                except Exception as e:
                    logger.error(f"🛑 Error saving device settings: {e}")

        ```
    *   Add `from typing import Union, Dict` to imports.
    *   Add `import yaml` for device settings.
    *   Clarify the distinction and interaction between `app_data_dir` (for truly local things like index, logs, Toga app state) and `_local_sync_root` (the user's main article library, synced with cloud).
    *   The `get_article_filepath` method should consider potential filename collisions if titles are very similar. Adding a part of the UUID helps.
    *   Thumbnail path strategy: PRD mentions "relative to the article file".

---

#### 15. `src/purse/services/thumbnail_service.py` (Optional - or integrate into `ContentParserService` / `FileSystemManager`)
*   **Intent**: (If separated) Extracts lead images from articles or generates simple thumbnails.
*   **File Path**: `src/purse/services/thumbnail_service.py`
*   **Upstream Dependencies**: `httpx` (if fetching images), image manipulation library (e.g., `Pillow`), `logging`, `src/purse/models/article.py`, `src/purse/services/http_client.py`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: `content_parser.py` (to call after parsing), `file_system_manager.py` (to save).
*   **Changes Needed**:
    *   For now, let's assume basic thumbnail fetching/handling can be part of `ContentParserService` (finding image URLs in HTML) and saving in `FileSystemManager`. If advanced generation (e.g., text-to-image for bookmarks, resizing) is needed, this service would be justified.
    *   PRD 5.3: "For card view, extract and display a lead image from the article content."
        *   `trafilatura` (when parsing HTML) might provide image URLs if `include_images=True`.
        *   The `ContentParserService` can identify a candidate image URL.
        *   Then, `HttpClient` can fetch it, and `FileSystemManager` can save it.
    *   **Decision**: Integrate simple lead image extraction into `ContentParserService` and saving/loading into `FileSystemManager`. Avoid a separate `ThumbnailService` for now to reduce complexity, unless image manipulation (resize, crop) is required.

    *   **Modification to `ContentParserService.parse_url`**:
        *   After `trafilatura.bare_extraction`, check `extracted_data.get('image')` or parse `markdown_content` for the first image URL.
        *   If an image URL is found:
            ```python
            # In ContentParserService.parse_url, after getting article object
            # ...
            # image_url_from_parser = extracted_data.get('image') # trafilatura might give lead image
            # if image_url_from_parser:
            #    article.potential_thumbnail_source_url = image_url_from_parser # Store for later fetching
            ```
    *   A new method in `FileSystemManager` or a coordinated effort post-parsing:
        ```python
        # Potentially a new method in a higher-level orchestrator or in FileSystemManager
        # async def fetch_and_save_thumbnail_for_article(article: Article, http_client: HttpClient, fs_manager: FileSystemManager):
        #    if hasattr(article, 'potential_thumbnail_source_url') and article.potential_thumbnail_source_url:
        #        try:
        #            img_response = await http_client.get_url(article.potential_thumbnail_source_url)
        #            # TODO: Add image validation/resizing here if Pillow is included
        #            fs_manager.save_thumbnail(article, img_response.content)
        #        except Exception as e:
        #            logger.warning(f"🟡 Failed to fetch/save thumbnail from {article.potential_thumbnail_source_url}: {e}")
        ```
        This logic might fit best in the part of the application that *adds* a new article, after `ContentParserService` has run. For example, in a `ArticleService` or `LibraryManager` if such orchestrating classes are introduced, or directly in UI command handlers.

---

### Phase 3: Search, Cloud Sync Precursors

#### 16. `src/purse/services/search_manager.py`
*   **File Path**: `src/purse/services/search_manager.py`
*   **Intent**: Manages the Whoosh search index: creating schema, adding/updating/deleting articles, and performing searches.
*   **Upstream Dependencies**: `whoosh`, `logging`, `src/purse/models/article.py`, `src/purse/services/file_system_manager.py`, `src/purse/services/markdown_handler.py` (for extracting highlights/notes if not directly on Article object).
*   **Downstream Dependencies**: UI components for search functionality.
*   **Changes Needed**:
    *   Create the file.
    *   Add imports:
        ```python
        import whoosh.index as index
        from whoosh.fields import Schema, TEXT, ID, KEYWORD, DATETIME, BOOLEAN, NUMERIC
        from whoosh.qparser import MultifieldParser, QueryParser, GtLtParser, FuzzyTermPlugin, WildcardPlugin
        from whoosh.analysis import StemmingAnalyzer
        from whoosh.writing import AsyncWriter # For concurrent writes
        import logging
        from pathlib import Path
        from typing import List, Optional, Dict, Any

        from purse.models.article import Article
        from purse.services.file_system_manager import FileSystemManager
        from purse.services.markdown_handler import MarkdownHandler # For highlight extraction if needed

        logger = logging.getLogger(__name__)
        ```
    *   Define `SearchManager` class:
        ```python
        class SearchManager:
            SCHEMA = Schema(
                # From Article model, PRD 5.2, 5.4
                id=ID(stored=True, unique=True), # Article UUID
                original_url=ID(stored=True),
                title=TEXT(stored=True, field_boost=2.0, analyzer=StemmingAnalyzer()),
                content=TEXT(stored=True, analyzer=StemmingAnalyzer()), # Markdown body + notes + highlights text
                tags=KEYWORD(stored=True, commas=True, scorable=True, lowercase=True), # Comma-separated string for Whoosh
                author=KEYWORD(stored=True, commas=True, lowercase=True), # Assuming authors are comma-separated if multiple
                publication_name=TEXT(stored=True, analyzer=StemmingAnalyzer()),
                publication_date=DATETIME(stored=True, sortable=True),
                saved_date=DATETIME(stored=True, sortable=True),
                status=ID(stored=True),
                favorite=BOOLEAN(stored=True),
                notes=TEXT(stored=True, analyzer=StemmingAnalyzer()), # Extracted notes
                highlights=TEXT(stored=True, analyzer=StemmingAnalyzer()), # Extracted highlights
                # Add other searchable fields if necessary
                # word_count=NUMERIC(stored=True, sortable=True),
                # language=ID(stored=True),
            )

            def __init__(self, fs_manager: FileSystemManager):
                self.fs_manager = fs_manager
                self.index_dir = self.fs_manager.search_index_dir
                self.ix = self._open_or_create_index()

            def _open_or_create_index(self) -> index.Index:
                if not self.index_dir.exists():
                    self.index_dir.mkdir(parents=True, exist_ok=True)
                
                if index.exists_in(self.index_dir):
                    logger.info(f"🟢 Opening existing Whoosh index at {self.index_dir}")
                    return index.open_dir(self.index_dir, schema=self.SCHEMA) # Pass schema to handle potential evolution
                else:
                    logger.info(f"🟢 Creating new Whoosh index at {self.index_dir}")
                    return index.create_in(self.index_dir, self.SCHEMA)

            def _get_publication_date_obj(self, article: Article):
                if article.publication_date:
                    try: return common.parse_iso_timestamp(article.publication_date)
                    except: return None
                return None

            def _get_saved_date_obj(self, article: Article):
                try: return common.parse_iso_timestamp(article.saved_date)
                except: return None # Should always exist

            def add_or_update_article(self, article: Article) -> None:
                logger.debug(f"Indexing article: {article.id} - {article.title}")
                try:
                    writer = AsyncWriter(self.ix) # Use AsyncWriter for potentially better performance
                    
                    # Consolidate all text for 'content' field
                    # PRD: "index should cover article text, notes, highlights"
                    notes_text = article.get_notes()
                    highlights_list = MarkdownHandler.extract_highlights(article.markdown_content)
                    highlights_text = " ".join(highlights_list)
                    main_content_text = article.get_content_without_notes() # Already excludes notes

                    # Cleanse highlights text from markup for indexing
                    highlights_text_cleaned = highlights_text.replace(constants.MARKDOWN_HIGHLIGHT_START_TAG, "").replace(constants.MARKDOWN_HIGHLIGHT_END_TAG, "")

                    full_searchable_content = f"{main_content_text}\n{notes_text}\n{highlights_text_cleaned}"

                    writer.update_document(
                        id=article.id,
                        original_url=article.original_url,
                        title=article.title,
                        content=full_searchable_content,
                        tags=",".join(article.tags).lower() if article.tags else "",
                        author=",".join(article.author).lower() if article.author else "",
                        publication_name=article.publication_name,
                        publication_date=self._get_publication_date_obj(article),
                        saved_date=self._get_saved_date_obj(article),
                        status=article.status,
                        favorite=article.favorite,
                        notes=notes_text,
                        highlights=highlights_text_cleaned
                    )
                    writer.commit()
                    logger.info(f"🟢 Article '{article.title}' (ID: {article.id}) indexed/updated.")
                except Exception as e:
                    logger.error(f"🛑 Error indexing article {article.id}: {e}")

            def delete_article(self, article_id: str) -> None:
                try:
                    writer = AsyncWriter(self.ix)
                    writer.delete_by_term('id', article_id)
                    writer.commit()
                    logger.info(f"🟢 Article ID '{article_id}' deleted from index.")
                except Exception as e:
                    logger.error(f"🛑 Error deleting article ID {article_id} from index: {e}")
            
            def rebuild_index(self, articles: List[Article]) -> None:
                """Clears and rebuilds the entire index from a list of articles."""
                logger.info(" rebuilding search index...")
                # Re-create index to ensure clean state
                self.ix = index.create_in(self.index_dir, self.SCHEMA) # This clears existing
                
                writer = AsyncWriter(self.ix)
                count = 0
                for article in articles:
                    notes_text = article.get_notes()
                    highlights_list = MarkdownHandler.extract_highlights(article.markdown_content)
                    highlights_text = " ".join(highlights_list)
                    main_content_text = article.get_content_without_notes()
                    highlights_text_cleaned = highlights_text.replace(constants.MARKDOWN_HIGHLIGHT_START_TAG, "").replace(constants.MARKDOWN_HIGHLIGHT_END_TAG, "")
                    full_searchable_content = f"{main_content_text}\n{notes_text}\n{highlights_text_cleaned}"

                    writer.add_document( # Use add_document for fresh build
                        id=article.id,
                        original_url=article.original_url,
                        title=article.title,
                        content=full_searchable_content,
                        tags=",".join(article.tags).lower() if article.tags else "",
                        author=",".join(article.author).lower() if article.author else "",
                        publication_name=article.publication_name,
                        publication_date=self._get_publication_date_obj(article),
                        saved_date=self._get_saved_date_obj(article),
                        status=article.status,
                        favorite=article.favorite,
                        notes=notes_text,
                        highlights=highlights_text_cleaned
                    )
                    count += 1
                writer.commit()
                logger.info(f"🟢 Search index rebuilt. {count} articles indexed.")


            def search(self, query_string: str, fields: Optional[List[str]] = None, limit: int = 20) -> List[Dict[str, Any]]:
                """
                Performs a search.
                `query_string` can include field specifiers like 'title:Python tags:programming'.
                `fields` specifies which fields to search if no field specifiers in query_string.
                """
                if not self.ix:
                    logger.warning("🟡 Search index not available.")
                    return []

                # Default fields to search if not specified in query
                if fields is None:
                    fields_to_search = ["title", "content", "tags", "author", "publication_name", "notes", "highlights"]
                else:
                    fields_to_search = fields
                
                with self.ix.searcher() as searcher:
                    # PRD 5.4: "Boolean operators (AND, OR, NOT), phrase searching."
                    # QueryParser by default supports AND, OR, NOT, phrases.
                    # Add GtLtPlugin for date/numeric range searches (e.g. saved_date:>2024-01-01)
                    # Add FuzzyTermPlugin for fuzzy searches (e.g. term~)
                    # Add WildcardPlugin for wildcard searches (e.g. wild*card)
                    parser = MultifieldParser(fields_to_search, schema=self.SCHEMA)
                    parser.add_plugin(GtLtParser()) # For date ranges etc.
                    parser.add_plugin(FuzzyTermPlugin())
                    parser.add_plugin(WildcardPlugin())


                    try:
                        query = parser.parse(query_string)
                        results = searcher.search(query, limit=limit) # Add sort order options later
                        
                        # PRD 5.4: Results Presentation: Sortable by relevance, date saved, publication date, title.
                        # Example: results = searcher.search(query, limit=limit, sortedby="saved_date", reverse=True)

                        found_articles: List[Dict[str, Any]] = []
                        for hit in results:
                            # Store all stored fields from the hit
                            article_data = {k: v for k, v in hit.items()}
                            article_data['score'] = hit.score # Add relevance score
                            found_articles.append(article_data)
                        
                        logger.info(f"🟢 Search for '{query_string}' found {len(found_articles)} results.")
                        return found_articles
                    except Exception as e: # Catch Whoosh query parsing errors, etc.
                        logger.error(f"🛑 Error during search for '{query_string}': {e}")
                        return []

            def get_all_indexed_article_ids(self) -> List[str]:
                """Retrieves all article IDs currently in the index."""
                ids = []
                if not self.ix: return ids
                with self.ix.reader() as reader:
                    for docnum, _ in reader.iter_docs():
                        stored_fields = reader.stored_fields(docnum)
                        if stored_fields and 'id' in stored_fields:
                            ids.append(stored_fields['id'])
                return ids

            # PRD 5.4: Similar Article Recommendations (V1 - Keyword-based)
            def find_similar_articles(self, article_id: str, num_recommendations: int = 5) -> List[Dict[str, Any]]:
                """Finds similar articles based on shared keywords in content/tags."""
                if not self.ix: return []

                with self.ix.searcher() as searcher:
                    try:
                        # Get the document for the given article_id
                        docnum = searcher.document_number(id=article_id)
                        if docnum is None:
                            logger.warning(f"🟡 Article ID {article_id} not found in index for similarity search.")
                            return []

                        # Use Whoosh's "More Like This" functionality
                        # Need to specify which fields to use for similarity
                        # 'content' and 'tags' are good candidates.
                        # Whoosh's mlt() returns a Query object.
                        # This requires the field to be analyzed and have term vectors, or be text.
                        # Our 'content' field (TEXT with StemmingAnalyzer) should work.
                        # 'tags' (KEYWORD) might also work if treated as text for MLT.

                        # Get the content of the source article to generate a query
                        # stored_fields = searcher.stored_fields(docnum)
                        # if not stored_fields: return []
                        # text_for_mlt = stored_fields.get('content', '') + " " + stored_fields.get('tags', '').replace(',', ' ')

                        # query = WhooshMLT(field="content", text=text_for_mlt).query(searcher, docnum)
                        # Alternative using MoreLikeThisQuery directly
                        # This is more complex to set up correctly with analyzers.
                        
                        # A simpler approach: construct a disjunctive query from top terms in the article
                        # Or, use the `more_like()` method of a `Hit` object if available during a search.
                        # For now, use the `more_like_this` method on the searcher if available
                        # or the `key_terms_from_text` to build a query.

                        # Focusing on TF-IDF + Cosine Similarity (as PRD hints at):
                        # Whoosh searcher has a `vector_as()` method to get term vectors if stored.
                        # This is more advanced. For V1:
                        # Use `searcher.more_like(docnum, fieldname='content', top=10)`
                        # This gets documents sharing many terms with the given document in the 'content' field.
                        # `num_recommendations` will be `top` + 1 (includes original), so adjust.

                        results = searcher.more_like(docnum, fieldname="content", top=num_recommendations)
                        
                        similar_articles: List[Dict[str, Any]] = []
                        for hit in results:
                            if hit['id'] == article_id: continue # Don't recommend itself
                            article_data = {k: v for k, v in hit.items()}
                            article_data['score'] = hit.score
                            similar_articles.append(article_data)
                        
                        logger.info(f"🟢 Found {len(similar_articles)} similar articles for ID {article_id}")
                        return similar_articles[:num_recommendations] # Ensure limit

                    except Exception as e:
                        logger.error(f"🛑 Error finding similar articles for {article_id}: {e}")
                        return []
        ```
    *   Need `from purse.utils import common` for date parsing.
    *   Ensure schema matches PRD requirements for search (full-text, metadata).
    *   Implement robust add/update/delete methods. `AsyncWriter` is a good choice.
    *   The `search` method needs to support fielded search and operators as per PRD 5.4. `MultifieldParser` is a good start.
    *   TF-IDF for similar articles: Whoosh has some support for "More Like This" queries, which can be explored. Or, extract keywords and form a new OR query. PRD mentions "TF-IDF on article text/tags + cosine similarity". This is more involved than simple Whoosh MLT. For V1, Whoosh's `searcher.more_like(docnum, "fieldname")` is a good starting point.

---


### Phase 4: Cloud Integration and Synchronization

This phase introduces a base class for cloud storage services and then implements it for Dropbox, Google Drive, and OneDrive.

#### 17. `src/purse/services/cloud_storage/base_cloud_service.py`
*   **File Path**: `src/purse/services/cloud_storage/base_cloud_service.py`
*   **Intent**: Defines an abstract base class (ABC) for cloud storage operations, ensuring a consistent interface for different providers.
*   **Upstream Dependencies**: `abc`, `typing`, `pathlib`, `logging`, `src/purse/models/article.py` (for type hinting, though not directly manipulating).
*   **Downstream Dependencies**: Specific cloud service implementations (`dropbox_service.py`, etc.), `sync_manager.py`.
*   **Changes Needed**:
    *   Create `src/purse/services/cloud_storage/__init__.py` (empty).
    *   Create `src/purse/services/cloud_storage/base_cloud_service.py`.
    *   Add imports:
        ```python
        from abc import ABC, abstractmethod
        from typing import List, Optional, Tuple, Dict, Any, AsyncGenerator
        from pathlib import Path
        import logging
        from dataclasses import dataclass

        logger = logging.getLogger(__name__)

        @dataclass
        class CloudFileMetadata:
            id: str  # Provider-specific ID
            name: str
            path_display: str # Full path in cloud storage
            rev: str # Revision identifier
            size: int # Size in bytes
            modified_timestamp: float # UTC Unix timestamp (seconds since epoch)
            is_folder: bool = False
            is_deleted: bool = False # For providers that mark deletions
            # Add other common fields if necessary, e.g. content_hash
        ```
    *   Define `BaseCloudService` ABC:
        ```python
        class BaseCloudService(ABC):
            PROVIDER_NAME: str = "AbstractCloudProvider"

            def __init__(self, config_manager: Any, access_token: Optional[str] = None, refresh_token: Optional[str] = None):
                self.config_manager = config_manager # For API keys, app secrets etc. if needed
                self.access_token = access_token
                self.refresh_token = refresh_token
                self.root_folder_path: str = "/Apps/Purse" # Default, user-configurable
                self.user_id: Optional[str] = None # Store user ID for the cloud service

            @abstractmethod
            async def authenticate_url(self, state: Optional[str] = None) -> Tuple[str, str]:
                """
                Generates an authorization URL for OAuth and a PKCE code verifier if needed.
                Returns (auth_url, code_verifier_if_pkce_else_none).
                """
                pass

            @abstractmethod
            async def exchange_code_for_token(self, auth_code: str, code_verifier: Optional[str] = None) -> Dict[str, str]:
                """
                Exchanges an authorization code for an access token and refresh token.
                Returns {'access_token': '...', 'refresh_token': '...', 'user_id': '...'}.
                """
                pass

            @abstractmethod
            async def refresh_access_token(self) -> Optional[str]:
                """
                Refreshes the access token using the refresh token.
                Updates self.access_token and returns the new access token, or None on failure.
                """
                pass

            @abstractmethod
            async def get_user_info(self) -> Optional[Dict[str, Any]]:
                """Fetches basic user information (e.g., email, name, user ID)."""
                pass

            @abstractmethod
            async def list_folder(self, folder_path: str, recursive: bool = False) -> AsyncGenerator[CloudFileMetadata, None]:
                """
                Lists files and folders in a given cloud path.
                Yields CloudFileMetadata objects.
                folder_path is relative to the app's root folder in the cloud.
                """
                # Example structure of what needs to be implemented:
                # path_to_list = self.get_full_cloud_path(folder_path)
                # async for item in self._internal_list_folder(path_to_list, recursive):
                #     yield item
                pass

            @abstractmethod
            async def download_file(self, cloud_file_path: str, local_target_path: Path) -> bool:
                """
                Downloads a file from the cloud to a local path.
                cloud_file_path is relative to the app's root folder.
                """
                pass

            @abstractmethod
            async def download_file_content(self, cloud_file_path: str) -> Optional[bytes]:
                """
                Downloads a file's content directly into bytes.
                cloud_file_path is relative to the app's root folder.
                """
                pass

            @abstractmethod
            async def upload_file(self, local_file_path: Path, cloud_target_folder: str, cloud_file_name: Optional[str] = None) -> Optional[CloudFileMetadata]:
                """
                Uploads a local file to the specified cloud folder.
                cloud_target_folder is relative to the app's root folder.
                If cloud_file_name is None, uses local_file_path.name.
                Returns metadata of the uploaded file.
                """
                pass

            @abstractmethod
            async def upload_file_content(self, content_bytes: bytes, cloud_target_folder: str, cloud_file_name: str) -> Optional[CloudFileMetadata]:
                """
                Uploads bytes directly as a file to the specified cloud folder.
                cloud_target_folder is relative to the app's root folder.
                Returns metadata of the uploaded file.
                """
                pass

            @abstractmethod
            async def delete_file(self, cloud_file_path: str) -> bool:
                """
                Deletes a file or folder from the cloud.
                cloud_file_path is relative to the app's root folder.
                """
                pass

            @abstractmethod
            async def create_folder(self, cloud_folder_path: str) -> bool:
                """
                Creates a folder in the cloud.
                cloud_folder_path is relative to the app's root folder.
                """
                pass
            
            @abstractmethod
            async def get_file_metadata(self, cloud_file_path: str) -> Optional[CloudFileMetadata]:
                """
                Gets metadata for a specific file or folder.
                cloud_file_path is relative to the app's root folder.
                """
                pass

            def get_full_cloud_path(self, relative_path: str) -> str:
                """Combines the app's root folder with a relative path."""
                # Ensure self.root_folder_path ends with / if not empty, and relative_path doesn't start with /
                # Or use Path-like concatenation if provider SDK supports it.
                # For string paths:
                clean_root = self.root_folder_path.rstrip('/')
                clean_relative = relative_path.lstrip('/')
                if not clean_root: return f"/{clean_relative}" # If root is effectively '/'
                return f"{clean_root}/{clean_relative}"

            def set_root_folder_path(self, root_path: str) -> None:
                """Sets the user-defined root folder for the application in their cloud storage."""
                self.root_folder_path = root_path.strip()
                if not self.root_folder_path.startswith('/'):
                    self.root_folder_path = '/' + self.root_folder_path
                logger.info(f"{self.PROVIDER_NAME}: Root folder set to '{self.root_folder_path}'")

            async def ensure_app_root_folder_exists(self) -> bool:
                """Checks if the app's root folder exists, creates it if not."""
                # This often involves listing the parent and checking, or trying to get metadata.
                # Some APIs might allow a create_folder call that succeeds if it already exists.
                # This is a common pattern, so providing a default (that might need overriding) or guidance.
                try:
                    meta = await self.get_file_metadata(self.root_folder_path.lstrip('/')) # Assuming root is relative to actual cloud root
                    if meta and meta.is_folder:
                        return True
                    # If it's a file or not found, try to create
                except Exception: # Typically a "not found" error
                    pass
                
                logger.info(f"{self.PROVIDER_NAME}: App root folder '{self.root_folder_path}' not found or not a folder. Attempting to create.")
                # Need to handle creation of nested root folders.
                # Example: /Apps/Purse - create /Apps then /Apps/Purse if they don't exist.
                # For simplicity, assume create_folder can handle nested creation or direct path.
                # The path passed to create_folder is relative to the actual cloud root.
                # So, for self.root_folder_path = "/Apps/Purse", we pass "Apps/Purse"
                return await self.create_folder(self.root_folder_path.lstrip('/'))

        ```
    *   Add type hint `from purse.config_manager import ConfigManager` for `config_manager: Any` when defined.
    *   The `CloudFileMetadata` dataclass will standardize how file info is passed around.
    *   All path arguments to these methods should be relative to the app's root folder (e.g., `self.root_folder_path`), and the methods internally resolve them to full cloud paths.

---

#### 18. `src/purse/services/cloud_storage/dropbox_service.py`
*   **File Path**: `src/purse/services/cloud_storage/dropbox_service.py`
*   **Intent**: Dropbox implementation of `BaseCloudService`.
*   **Upstream Dependencies**: `dropbox` SDK, `src/purse/services/cloud_storage/base_cloud_service.py`, `logging`, `src/purse/config_manager.py`, `httpx` (if SDK doesn't use its own async client or if we need to customize).
*   **Downstream Dependencies**: `sync_manager.py`.
*   **Changes Needed**:
    *   Implement all abstract methods from `BaseCloudService` using the Dropbox Python SDK.
    *   Handle OAuth2 PKCE flow for authentication.
    *   Store Dropbox App Key and Secret in `config.yml` (or these are fetched by ConfigManager from a secure source not committed). For self-hosted app, these might be user-provided during setup.
        **Decision**: App Key/Secret should be in `config.yml` initially, perhaps with a note for users to create their own Dropbox App if they prefer.
        ```yaml
        # In config.yml
        cloud_providers:
          dropbox:
            app_key: "YOUR_DROPBOX_APP_KEY"
            app_secret: "YOUR_DROPBOX_APP_SECRET"
            # redirect_uri should be determined by Toga app or a fixed local one for desktop.
            # For Toga, a custom URL scheme might be needed.
            # For desktop, http://localhost:<port> is common.
            redirect_uri: "http://localhost:8765/dropbox_oauth_callback" # Example
        ```
    *   Key implementation details:
        *   Use `Dropbox(oauth2_access_token=...)` or `Dropbox(oauth2_refresh_token=..., app_key=..., app_secret=...)` for API calls.
        *   File/folder listing: `files_list_folder`, `files_list_folder_continue`.
        *   Download: `files_download_to_file` or `files_download`.
        *   Upload: `files_upload`.
        *   Delete: `files_delete_v2`.
        *   Metadata: `files_get_metadata`.
        *   Error handling for Dropbox API errors.
        *   Convert Dropbox timestamps (UTC `datetime` objects) to UTC Unix timestamps.
        *   Dropbox paths are case-insensitive but preserve case.
        *   The Dropbox SDK methods are synchronous. Need to wrap them in `asyncio.to_thread` or use an async Dropbox SDK if one exists and is suitable. **Decision**: Use `asyncio.to_thread` for now with the official sync SDK.
        ```python
        # Example snippet for a method
        # import asyncio
        # from dropbox import Dropbox
        # from dropbox.exceptions import AuthError, ApiError
        # from dropbox.files import FileMetadata, FolderMetadata, DeletedMetadata

        # class DropboxService(BaseCloudService):
        #     PROVIDER_NAME = "Dropbox"
        #     def __init__(self, config_manager: ConfigManager, access_token: Optional[str] = None, refresh_token: Optional[str] = None):
        #         super().__init__(config_manager, access_token, refresh_token)
        #         self.app_key = self.config_manager.get('cloud_providers.dropbox.app_key')
        #         self.app_secret = self.config_manager.get('cloud_providers.dropbox.app_secret')
        #         self.redirect_uri = self.config_manager.get('cloud_providers.dropbox.redirect_uri')
        #         self.dbx: Optional[Dropbox] = None
        #         if self.access_token:
        #             self.dbx = Dropbox(oauth2_access_token=self.access_token)
        #         elif self.refresh_token and self.app_key and self.app_secret:
        #             self.dbx = Dropbox(
        #                 oauth2_refresh_token=self.refresh_token,
        #                 app_key=self.app_key,
        #                 app_secret=self.app_secret
        #             )
        #             # May need to call refresh_access_token immediately

        #     async def _run_sync(self, func, *args, **kwargs):
        #         # Helper to run synchronous SDK calls in a thread
        #         return await asyncio.to_thread(func, *args, **kwargs)

        #     async def refresh_access_token(self) -> Optional[str]:
        #         if not (self.refresh_token and self.app_key and self.app_secret):
        #             logger.error(f"{self.PROVIDER_NAME}: Missing refresh token, app key, or app secret for token refresh.")
        #             return None
        #         try:
        #             # The Dropbox SDK handles refresh automatically if constructed with refresh_token, app_key, app_secret
        #             # and then an API call is made. We might need to explicitly trigger it or check.
        #             # For explicit refresh, one way is to instantiate Dropbox with only those and it refreshes on first call.
        #             # Or use DropboxOAuth2Flow.refresh_access_token (more manual)
        #             temp_dbx = Dropbox(oauth2_refresh_token=self.refresh_token, app_key=self.app_key, app_secret=self.app_secret)
        #             temp_dbx.check_user() # This should trigger a refresh and get new access token
        #             self.access_token = temp_dbx.session.token_access # This might not be directly exposed; SDK manages it.
        #             # The SDK is designed to auto-refresh. We just need to ensure dbx object is correctly configured.
        #             # If we need the new token explicitly:
        #             # This part is tricky with the official SDK's auto-refresh.
        #             # For now, assume dbx object handles it.
        #             # Let's test by making a simple call.
        #             if not self.dbx: # If dbx was not initialized due to no initial access_token
        #                  self.dbx = Dropbox(oauth2_refresh_token=self.refresh_token, app_key=self.app_key, app_secret=self.app_secret)
        #             await self._run_sync(self.dbx.users_get_current_account) # Make a call to ensure token is fresh
        #             # The access token is managed internally by the SDK instance.
        #             # If we need to persist the potentially new access_token and refresh_token (if it changed, rare):
        #             # This is where it gets complex if SDK doesn't expose them after refresh.
        #             # For now, assume SDK handles it and we don't need to extract it back unless for first time.
        #             logger.info(f"{self.PROVIDER_NAME}: Access token implicitly refreshed (if needed).")
        #             return self.access_token # Or a placeholder if SDK hides it
        #         except AuthError as e:
        #             logger.error(f"{self.PROVIDER_NAME}: AuthError during token refresh: {e}")
        #             self.access_token = None
        #             self.refresh_token = None # Potentially invalidate refresh token
        #             return None
        #         except Exception as e:
        #             logger.error(f"{self.PROVIDER_NAME}: Exception during token refresh: {e}")
        #             return None

            # ... Implement other abstract methods using self._run_sync(self.dbx.files_xxx, ...)
            # ... Map Dropbox API responses to CloudFileMetadata
        ```

---

#### 19. `src/purse/services/cloud_storage/google_drive_service.py`
*   **File Path**: `src/purse/services/cloud_storage/google_drive_service.py`
*   **Intent**: Google Drive implementation of `BaseCloudService`.
*   **Upstream Dependencies**: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`, `src/purse/services/cloud_storage/base_cloud_service.py`, `logging`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: `sync_manager.py`.
*   **Changes Needed**:
    *   Implement all abstract methods from `BaseCloudService` using the Google Drive API Client Library for Python.
    *   Handle OAuth2 flow. Google requires `client_secret.json` or individual credentials.
        **Decision**: Store `client_id`, `client_secret`, `project_id` in `config.yml`.
        ```yaml
        # In config.yml
        cloud_providers:
          google_drive:
            client_id: "YOUR_GOOGLE_CLIENT_ID"
            client_secret: "YOUR_GOOGLE_CLIENT_SECRET"
            project_id: "YOUR_GOOGLE_PROJECT_ID" # From GCP console
            scopes:
              - "https://www.googleapis.com/auth/drive.file" # Scope for app data folder or drive access
              # - "https://www.googleapis.com/auth/drive.appdata" # For app data folder only
              # - "https://www.googleapis.com/auth/userinfo.email"
              # - "https://www.googleapis.com/auth/userinfo.profile"
            redirect_uri: "http://localhost:8765/gdrive_oauth_callback" # Example
        ```    *   Key implementation details:
        *   Use `googleapiclient.discovery.build('drive', 'v3', credentials=...)`.
        *   File/folder listing: `files().list()`. Needs handling of pagination (`pageToken`).
        *   Download: `files().get_media(fileId=...)`.
        *   Upload: `files().create(media_body=...)`. Multipart upload for metadata + content.
        *   Delete: `files().delete(fileId=...)`.
        *   Metadata: `files().get()`.
        *   Error handling for Google API errors.
        *   Convert Google Drive timestamps (RFC3339 string) to UTC Unix timestamps.
        *   Google Drive uses file IDs extensively. Need to map paths to IDs. This can be complex for a path-based interface. May need an internal path-to-ID cache or frequent lookups.
        *   The Google API client library for Python supports asyncio using `googleapiclient.http.build_async_http_session`.
        *   Or, use `asyncio.to_thread` if async version is too complex to set up. **Decision**: Explore `build_async_http_session` first.
        ```python
        # Example snippet for a method
        # from google.oauth2.credentials import Credentials
        # from google_auth_oauthlib.flow import Flow
        # from googleapiclient.discovery import build
        # from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
        # import google.auth.transport.requests
        # import io

        # class GoogleDriveService(BaseCloudService):
        #     PROVIDER_NAME = "GoogleDrive"
            # ...
            # async def _get_drive_service(self):
            #     creds = Credentials(
            #         token=self.access_token,
            #         refresh_token=self.refresh_token,
            #         token_uri='https://oauth2.googleapis.com/token',
            #         client_id=self.config_manager.get('cloud_providers.google_drive.client_id'),
            #         client_secret=self.config_manager.get('cloud_providers.google_drive.client_secret'),
            #         scopes=self.config_manager.get('cloud_providers.google_drive.scopes')
            #     )
            #     if not creds.valid:
            #         if creds.expired and creds.refresh_token:
            #             try:
            #                 request = google.auth.transport.requests.Request()
            #                 await asyncio.to_thread(creds.refresh, request) # refresh is sync
            #                 self.access_token = creds.token
            #                 # Persist updated tokens via callback
            #             except Exception as e:
            #                 logger.error(f"{self.PROVIDER_NAME}: Failed to refresh token: {e}")
            #                 return None
            #         else:
            #             logger.error(f"{self.PROVIDER_NAME}: Invalid credentials, no refresh token or not expired.")
            #             return None
            #     # Use build_async_http_session() for async client if possible
            #     # http_async = await asyncio.to_thread(google_auth_httplib2.AuthorizedHttp, creds)
            #     # service = await asyncio.to_thread(build, 'drive', 'v3', http=http_async, cache_discovery=False)
            #     # For simplicity with official examples, often sync build is shown:
            #     service = await asyncio.to_thread(build, 'drive', 'v3', credentials=creds, cache_discovery=False, static_discovery=False)
            #     return service

            # Helper to get file ID from path - this is the hardest part for GDrive
            # async def _get_id_for_path(self, service, cloud_path: str) -> Optional[str]:
            #    # ... implementation to traverse path components and find ID ...
            #    # Start with 'root' or appDataFolder alias.
            #    # For each component, list files in parent_id with component name.

            # ... Implement other abstract methods using service.files().xxx calls.
            # ... Map Google Drive API responses to CloudFileMetadata.
        ```

---

#### 20. `src/purse/services/cloud_storage/onedrive_service.py`
*   **File Path**: `src/purse/services/cloud_storage/onedrive_service.py`
*   **Intent**: Microsoft OneDrive implementation of `BaseCloudService` (using Microsoft Graph API).
*   **Upstream Dependencies**: `msal` (Microsoft Authentication Library for Python), `httpx` (for direct Graph API calls if `msal` only handles auth), `src/purse/services/cloud_storage/base_cloud_service.py`, `logging`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: `sync_manager.py`.
*   **Changes Needed**:
    *   Implement all abstract methods from `BaseCloudService` using the Microsoft Graph API.
    *   Handle OAuth2 flow.
        **Decision**: Store `client_id` and `client_secret` (if using confidential client flow) or just `client_id` (for public client flow) in `config.yml`. For a desktop app, public client flow with PKCE is common.
        ```yaml
        # In config.yml
        cloud_providers:
          onedrive: # Microsoft Graph
            client_id: "YOUR_ONEDRIVE_CLIENT_ID" # Application (client) ID
            # client_secret: "YOUR_ONEDRIVE_CLIENT_SECRET" # Only if using confidential client flow
            authority: "https://login.microsoftonline.com/common" # Or consumers for personal accounts
            scopes:
              - "Files.ReadWrite.AppFolder" # Or Files.ReadWrite if broader access needed
              - "offline_access"
              - "User.Read"
            redirect_uri: "http://localhost:8765/onedrive_oauth_callback" # Example
            # Graph API endpoints
            graph_api_endpoint_v1: "https://graph.microsoft.com/v1.0"
        ```
    *   Key implementation details:
        *   Use `msal.PublicClientApplication` or `msal.ConfidentialClientApplication`.
        *   Acquire token: `acquire_token_by_authorization_code`, `acquire_token_silent`, `acquire_token_by_refresh_token`.
        *   Make Graph API calls using `httpx` with the access token in Authorization header.
            *   Endpoint: `https://graph.microsoft.com/v1.0/me/drive/`
            *   Listing: `/me/drive/root:/path/to/folder:/children` or `/me/drive/items/{item-id}/children`
            *   Download: `/me/drive/items/{item-id}/content`
            *   Upload: `/me/drive/root:/path/to/file:/content` (simple upload for <4MB), or create upload session for larger files.
            *   Delete: `/me/drive/items/{item-id}`
            *   Metadata: `/me/drive/items/{item-id}` or `/me/drive/root:/path/to/file`
        *   Error handling for Graph API errors.
        *   Convert Graph API timestamps (ISO 8601 string) to UTC Unix timestamps.
        *   Graph API uses item IDs but also supports path-based addressing for Drive items (e.g., `/root:/Folder/File.txt:`).
        ```python
        # Example snippet
        # import msal
        # import httpx
        # from datetime import datetime, timezone

        # class OneDriveService(BaseCloudService):
        #     PROVIDER_NAME = "OneDrive"
        #     def __init__(self, config_manager: ConfigManager, access_token: Optional[str] = None, refresh_token: Optional[str] = None, msal_cached_accounts: Optional[List[Any]] = None):
        #         super().__init__(config_manager, access_token, refresh_token)
        #         self.client_id = self.config_manager.get('cloud_providers.onedrive.client_id')
        #         self.authority = self.config_manager.get('cloud_providers.onedrive.authority')
        #         self.scopes = self.config_manager.get('cloud_providers.onedrive.scopes')
        #         self.redirect_uri = self.config_manager.get('cloud_providers.onedrive.redirect_uri')
        #         self.graph_endpoint = self.config_manager.get('cloud_providers.onedrive.graph_api_endpoint_v1', 'https://graph.microsoft.com/v1.0')
                
        #         self.msal_app = msal.PublicClientApplication(
        #             client_id=self.client_id,
        #             authority=self.authority,
        #             # token_cache can be used to persist tokens if desired
        #         )
        #         self.msal_cached_accounts = msal_cached_accounts if msal_cached_accounts else [] # From previous session

        #     async def _get_headers(self) -> Optional[Dict[str, str]]:
        #         token_result = None
        #         if not self.msal_cached_accounts: # Try to get accounts from cache if not passed
        #             self.msal_cached_accounts = self.msal_app.get_accounts()

        #         if self.msal_cached_accounts:
        #             token_result = await asyncio.to_thread(
        #                 self.msal_app.acquire_token_silent,
        #                 scopes=self.scopes,
        #                 account=self.msal_cached_accounts[0] # Assume first account
        #             )
                
        #         if not token_result and self.refresh_token: # Fallback if silent failed and we have an old RT
        #             # MSAL's acquire_token_silent should use RT if available in cache.
        #             # This is more for if the cache is not used or token is external.
        #             logger.info(f"{self.PROVIDER_NAME}: Attempting to use stored refresh token.")
        #             token_result = await asyncio.to_thread(
        #                 self.msal_app.acquire_token_by_refresh_token,
        #                 refresh_token=self.refresh_token,
        #                 scopes=self.scopes
        #             )

        #         if token_result and "access_token" in token_result:
        #             self.access_token = token_result["access_token"]
        #             # MSAL cache handles RT persistence. If RT changed, it's updated in cache.
        #             # If user_id needed, it's in token_result['id_token_claims']['oid'] or from /me
        #             if not self.user_id and 'id_token_claims' in token_result and 'oid' in token_result['id_token_claims']:
        #                 self.user_id = token_result['id_token_claims']['oid']
        #             return {"Authorization": f"Bearer {self.access_token}"}
        #         else:
        #             if token_result: logger.warning(f"{self.PROVIDER_NAME}: Failed to acquire token: {token_result.get('error_description')}")
        #             else: logger.warning(f"{self.PROVIDER_NAME}: No cached accounts or refresh token to acquire token silently.")
        #             return None

            # ... Implement other abstract methods using httpx.AsyncClient and Graph API endpoints.
            # ... e.g., `async with httpx.AsyncClient() as client: response = await client.get(url, headers=await self._get_headers())`
            # ... Map Graph API responses to CloudFileMetadata.
        ```

---

#### 21. `src/purse/services/sync_manager.py`
*   **File Path**: `src/purse/services/sync_manager.py`
*   **Intent**: Orchestrates the two-way synchronization of articles between the local file system and the chosen cloud storage provider. Handles conflict resolution.
*   **Upstream Dependencies**: `logging`, `asyncio`, `datetime`, `src/purse/services/cloud_storage/base_cloud_service.py` (and its implementations), `src/purse/services/file_system_manager.py`, `src/purse/services/markdown_handler.py`, `src/purse/models/article.py`, `src/purse/services/search_manager.py` (to update index after sync), `src/purse/config_manager.py`.
*   **Downstream Dependencies**: UI components (for triggering sync, displaying status).
*   **Changes Needed**:
    *   Create the file.
    *   Define `SyncManager` class:
        ```python
        import asyncio
        import logging
        from datetime import datetime, timezone, timedelta
        from pathlib import Path
        from typing import Dict, Optional, List, Set, Tuple, TYPE_CHECKING
        import time # For timestamps

        from purse.services.cloud_storage.base_cloud_service import BaseCloudService, CloudFileMetadata
        from purse.services.file_system_manager import FileSystemManager
        from purse.services.markdown_handler import MarkdownHandler
        from purse.models.article import Article
        from purse.services.search_manager import SearchManager # To update index
        from purse.utils import constants # For SYNC_CONFLICT_LOG_FILENAME

        if TYPE_CHECKING:
            from purse.config_manager import ConfigManager

        logger = logging.getLogger(__name__)

        # Helper dataclass for sync state
        @dataclass
        class LocalFileState:
            path: Path
            modified_timestamp: float # UTC Unix timestamp
            article_id: Optional[str] = None # If known

        class SyncManager:
            def __init__(self,
                         config_manager: 'ConfigManager',
                         fs_manager: FileSystemManager,
                         cloud_service: BaseCloudService,
                         search_manager: SearchManager):
                self.config_manager = config_manager
                self.fs_manager = fs_manager
                self.cloud_service = cloud_service
                self.search_manager = search_manager
                self._last_sync_time_utc: Optional[float] = None # Store as UTC Unix timestamp
                self._sync_lock = asyncio.Lock()
                self.conflict_log_path = self.fs_manager.logs_dir / constants.SYNC_CONFLICT_LOG_FILENAME

            def _log_conflict(self, message: str):
                timestamp = datetime.now(timezone.utc).isoformat()
                full_message = f"[{timestamp}] {message}\n"
                logger.warning(f"🟡 SYNC CONFLICT: {message}")
                try:
                    with open(self.conflict_log_path, 'a', encoding='utf-8') as f:
                        f.write(full_message)
                except Exception as e:
                    logger.error(f"🛑 Could not write to conflict log: {e}")

            async def _get_local_file_states(self) -> Dict[str, LocalFileState]:
                """Gets states of local .md files (path relative to sync root -> state)."""
                local_files: Dict[str, LocalFileState] = {}
                sync_root = self.fs_manager.get_local_sync_root()
                if not sync_root: return local_files

                for local_path in sync_root.glob("**/*.md"): # Assuming .md files for articles
                    if local_path.is_file() and not local_path.name.startswith('.'): # Skip hidden files
                        try:
                            # Relative path for key
                            relative_path_str = str(local_path.relative_to(sync_root))
                            # Get mtime and convert to UTC timestamp if it's naive
                            stat_info = local_path.stat()
                            mtime_utc = stat_info.st_mtime # Assuming local mtime is fine, or convert if FS is known
                            
                            # Try to get article ID for better matching (optional optimization)
                            # article = MarkdownHandler.parse_markdown_file(local_path) # This is slow
                            # article_id = article.id if article else None
                            
                            local_files[relative_path_str] = LocalFileState(
                                path=local_path,
                                modified_timestamp=mtime_utc,
                                # article_id=article_id # Defer ID loading
                            )
                        except Exception as e:
                            logger.error(f"🛑 Error stating local file {local_path}: {e}")
                return local_files

            async def _get_cloud_file_states(self) -> Dict[str, CloudFileMetadata]:
                """Gets states of cloud .md files (path relative to sync root -> metadata)."""
                cloud_files: Dict[str, CloudFileMetadata] = {}
                try:
                    # List files in the app's root folder (e.g., /Apps/Purse/)
                    # The path passed to list_folder is relative to this app root.
                    # So, for files directly in /Apps/Purse/, pass "" or "."
                    async for cloud_meta in self.cloud_service.list_folder("", recursive=True): # TODO: confirm recursive for all providers
                        if not cloud_meta.is_folder and cloud_meta.name.endswith(".md") and not cloud_meta.name.startswith('.'):
                             # Ensure path_display is relative to the app's cloud root for consistency
                            cloud_files[cloud_meta.path_display] = cloud_meta
                except Exception as e:
                    logger.error(f"🛑 Error listing cloud files: {e}")
                return cloud_files

            async def synchronize_articles(self, force_full_rescan: bool = False):
                """Performs a two-way sync."""
                async with self._sync_lock:
                    logger.info("🟢 Starting article synchronization...")
                    if not self.fs_manager.get_local_sync_root():
                        logger.error("🛑 Sync failed: Local sync root not configured.")
                        return
                    if not self.cloud_service.access_token and not await self.cloud_service.refresh_access_token():
                        logger.error("🛑 Sync failed: Cloud authentication failed or token expired.")
                        return

                    # 0. Ensure app root and .purse_config folder exist in cloud
                    await self.cloud_service.ensure_app_root_folder_exists()
                    synced_config_dir_in_cloud = self.fs_manager.synced_config_dir_name
                    await self.cloud_service.create_folder(synced_config_dir_in_cloud)


                    # 1. Get local and remote file states
                    logger.info("Fetching local file states...")
                    local_states = await self._get_local_file_states()
                    logger.info(f"Found {len(local_states)} local .md files.")

                    logger.info("Fetching cloud file states...")
                    cloud_states = await self._get_cloud_file_states()
                    logger.info(f"Found {len(cloud_states)} cloud .md files.")
                    
                    # Use a small tolerance for timestamp comparisons (e.g., 2 seconds)
                    # due to potential clock drift or precision differences.
                    timestamp_tolerance = 2.0 

                    # 2. Compare and determine actions
                    # Paths are relative to their respective sync roots.
                    # We assume file names/paths are the primary key for matching.
                    # This could be problematic if files are renamed. Article ID based sync is more robust
                    # but requires reading every file, which is slow for initial check.
                    # For now, path-based matching with "last write wins".

                    all_relative_paths = set(local_states.keys()) | set(cloud_states.keys())
                    actions_taken = False

                    for rel_path in sorted(list(all_relative_paths)):
                        local = local_states.get(rel_path)
                        cloud = cloud_states.get(rel_path)

                        # Case 1: Only local
                        if local and not cloud:
                            logger.info(f"'{rel_path}' exists locally, not in cloud. Uploading.")
                            await self.cloud_service.upload_file(local.path, str(Path(rel_path).parent), Path(rel_path).name)
                            actions_taken = True
                            # Index local article after successful upload (or assume it's indexed)

                        # Case 2: Only in cloud
                        elif cloud and not local:
                            logger.info(f"'{rel_path}' exists in cloud, not locally. Downloading.")
                            local_target_path = self.fs_manager.get_local_sync_root() / rel_path
                            local_target_path.parent.mkdir(parents=True, exist_ok=True)
                            await self.cloud_service.download_file(cloud.path_display, local_target_path)
                            # Index downloaded article
                            article_obj = MarkdownHandler.parse_markdown_file(local_target_path)
                            if article_obj: self.search_manager.add_or_update_article(article_obj)
                            actions_taken = True

                        # Case 3: Exists in both - Conflict Resolution
                        elif local and cloud:
                            # Compare modification timestamps (PRD 5.7: "Last Write Wins")
                            # Timestamps are UTC Unix floats
                            if abs(local.modified_timestamp - cloud.modified_timestamp) <= timestamp_tolerance:
                                # logger.debug(f"'{rel_path}' timestamps match or are close. No action.")
                                continue # Considered in sync

                            if local.modified_timestamp > cloud.modified_timestamp:
                                self._log_conflict(
                                    f"Conflict for '{rel_path}'. Local is newer ({datetime.fromtimestamp(local.modified_timestamp, tz=timezone.utc)}) "
                                    f"than cloud ({datetime.fromtimestamp(cloud.modified_timestamp, tz=timezone.utc)}). Uploading local."
                                )
                                await self.cloud_service.upload_file(local.path, str(Path(rel_path).parent), Path(rel_path).name)
                                actions_taken = True
                                # Re-index if local changed (already indexed, but this confirms)
                                article_obj = MarkdownHandler.parse_markdown_file(local.path)
                                if article_obj: self.search_manager.add_or_update_article(article_obj)


                            else: # Cloud is newer
                                self._log_conflict(
                                    f"Conflict for '{rel_path}'. Cloud is newer ({datetime.fromtimestamp(cloud.modified_timestamp, tz=timezone.utc)}) "
                                    f"than local ({datetime.fromtimestamp(local.modified_timestamp, tz=timezone.utc)}). Downloading cloud."
                                )
                                local_target_path = self.fs_manager.get_local_sync_root() / rel_path
                                local_target_path.parent.mkdir(parents=True, exist_ok=True)
                                await self.cloud_service.download_file(cloud.path_display, local_target_path)
                                # Index downloaded article
                                article_obj = MarkdownHandler.parse_markdown_file(local_target_path)
                                if article_obj: self.search_manager.add_or_update_article(article_obj)
                                actions_taken = True
                        
                        # Handle deletions (more complex, needs tombstoning or checking against last sync state)
                        # For V1, simple presence check. Deletions propagate.
                        # If a file was present in _last_sync_state_cloud but not now, it was deleted in cloud.
                        # If a file was present in _last_sync_state_local but not now, it was deleted locally.
                        # This requires storing last sync state, which is not yet implemented here.
                        # For now, the logic implies if deleted on one side, it will be re-uploaded/downloaded.
                        # True deletion sync requires comparing current state to a *previous synced state*.
                        # This simplified version handles additions and updates based on "last write wins".

                    # Sync settings.yml (PRD 5.9)
                    await self._sync_settings_file()

                    if not actions_taken and not force_full_rescan:
                       logger.info("🟢 No changes detected. Synchronization complete.")
                    else:
                       logger.info("🟢 Synchronization process finished.")
                    
                    self._last_sync_time_utc = time.time()

            async def _sync_settings_file(self):
                """Synchronizes the settings.yml file."""
                logger.info("Syncing settings.yml...")
                settings_filename = self.fs_manager.synced_settings_filename
                config_dir_name = self.fs_manager.synced_config_dir_name # e.g. ".purse_config"
                
                cloud_settings_rel_path = f"{config_dir_name}/{settings_filename}" # Relative to app cloud root
                local_settings_path = self.fs_manager.get_synced_settings_path()

                if not local_settings_path:
                    logger.error("🛑 Cannot sync settings: local settings path could not be determined.")
                    return

                cloud_meta = await self.cloud_service.get_file_metadata(cloud_settings_rel_path)

                if local_settings_path.exists() and not cloud_meta:
                    logger.info(f"Local '{settings_filename}' exists, not in cloud. Uploading.")
                    await self.cloud_service.upload_file(local_settings_path, config_dir_name, settings_filename)
                elif not local_settings_path.exists() and cloud_meta:
                    logger.info(f"Cloud '{settings_filename}' exists, not locally. Downloading.")
                    local_settings_path.parent.mkdir(parents=True, exist_ok=True)
                    await self.cloud_service.download_file(cloud_settings_rel_path, local_settings_path)
                    # App needs to reload settings from ConfigManager after this
                elif local_settings_path.exists() and cloud_meta:
                    local_mtime = local_settings_path.stat().st_mtime
                    if abs(local_mtime - cloud_meta.modified_timestamp) > 2.0: # Timestamp tolerance
                        if local_mtime > cloud_meta.modified_timestamp:
                            self._log_conflict(f"Conflict for '{settings_filename}'. Local is newer. Uploading.")
                            await self.cloud_service.upload_file(local_settings_path, config_dir_name, settings_filename)
                        else:
                            self._log_conflict(f"Conflict for '{settings_filename}'. Cloud is newer. Downloading.")
                            await self.cloud_service.download_file(cloud_settings_rel_path, local_settings_path)
                            # App needs to reload settings
                elif not local_settings_path.exists() and not cloud_meta:
                    logger.info(f"'{settings_filename}' not found locally or in cloud. Creating a default one if app has settings.")
                    # If ConfigManager has settings, save them, which will trigger upload on next sync or if done now.
                    # This assumes an initial settings.yml might be created locally by the app first.
                    # If settings are managed by ConfigManager.save_settings(), that file will be picked up.
        ```
    *   Implement conflict resolution ("Last Write Wins" based on file modification timestamps).
    *   Log conflicts to `sync_actions.log`.
    *   This sync logic is path-based and simplified. A more robust sync would involve:
        *   Tracking file IDs (from cloud) and article UUIDs.
        *   Handling renames/moves.
        *   Properly handling deletions (e.g., using tombstones or comparing against a persisted last known state). This PRD doesn't explicitly ask for complex deletion handling beyond "last write wins" implicitly covering it if a file is re-added.
        *   The current logic will re-upload/re-download deleted files if the other side has them. True "sync deletions" is harder.
    *   Needs careful handling of relative vs. absolute paths for cloud and local.
    *   `_get_cloud_file_states`: the `cloud_meta.path_display` from `list_folder` must be made relative to the app's cloud root if it isn't already. The `BaseCloudService.list_folder` should yield paths relative to the *folder_path* it was given.
    *   Synchronization of `settings.yml` needs to be handled. The `ConfigManager` should be reloaded if `settings.yml` is downloaded.

---

### Phase 5: Data Import, Application Services, and UI/App Assembly

#### 22. `src/purse/services/pocket_importer.py`
*   **File Path**: `src/purse/services/pocket_importer.py`
*   **Intent**: Handles importing articles from a Pocket export file.
*   **Upstream Dependencies**: `html` (for unescaping), `json` (if Pocket export is JSON, typically it's HTML), `logging`, `datetime`, `bs4` (BeautifulSoup4, if parsing HTML export), `src/purse/models/article.py`, `src/purse/services/content_parser.py`, `src/purse/services/file_system_manager.py`, `src/purse/services/search_manager.py`, `src/purse/utils/constants.py`, `src/purse/utils/common.py`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: UI component for triggering import.
*   **Changes Needed**:
    *   Create the file.
    *   Add imports:
        ```python
        import json # If Pocket export can be JSON. Usually it's ril_export.html
        import logging
        from datetime import datetime, timezone
        from pathlib import Path
        from typing import List, Optional, Tuple, Dict, TYPE_CHECKING, Any
        import html # For HTML unescaping of titles etc.
        from bs4 import BeautifulSoup # For parsing Pocket's HTML export

        from purse.models.article import Article
        from purse.services.content_parser import ContentParserService
        from purse.services.file_system_manager import FileSystemManager
        from purse.services.search_manager import SearchManager
        from purse.utils import constants, common

        if TYPE_CHECKING:
            from purse.config_manager import ConfigManager

        logger = logging.getLogger(__name__)
        ```
    *   Define `PocketImporterService` class:
        ```python
        class PocketImporterService:
            def __init__(self,
                         config_manager: 'ConfigManager',
                         content_parser: ContentParserService,
                         fs_manager: FileSystemManager,
                         search_manager: SearchManager):
                self.config_manager = config_manager
                self.content_parser = content_parser
                self.fs_manager = fs_manager
                self.search_manager = search_manager
                self.reparse_html_from_pocket = self.config_manager.get(
                    'pocket_importer.reparse_pocket_html', True
                )

            def _parse_pocket_export_html(self, html_content: str) -> List[Dict[str, Any]]:
                """Parses Pocket's ril_export.html file."""
                # Pocket's export format: an <ul> list where each <li> is an article.
                # Each <li> contains an <a> tag.
                # Attributes of <a>: href (original_url), time_added (unix timestamp), tags (comma-separated).
                # The text content of <a> is the title.
                # PRD 5.8: "Content from Pocket's export should be re-parsed/cleaned using Trafilatura if it's raw HTML,
                # or used as-is if it's already sufficiently clean."
                # The export file itself DOES NOT contain the article content, only links and metadata.
                # So, we always need to fetch and parse the URL.
                # Notes and Highlights are NOT in the standard Pocket export HTML.
                # This implies PRD 5.8 "Map Pocket data fields (... notes, highlights)" might be an issue
                # unless Pocket has another export format or API access that provides these.
                # For now, assume standard HTML export which lacks content, notes, highlights.

                logger.info("Parsing Pocket HTML export file...")
                soup = BeautifulSoup(html_content, 'html.parser')
                imported_items: List[Dict[str, Any]] = []

                # Find the main list of articles, usually the first <h1> followed by <ul>
                # Or more robustly, find all <a> tags within <li> that seem to be articles.
                # Typically, Pocket export has "Unread" and "Read Archive" sections.
                # Each section is an <h1> followed by a <p> (optional) and then an <ul>.

                article_links = soup.find_all('a', href=True) # A bit broad, might need refinement
                # A more specific selector if Pocket's structure is consistent:
                # list_items = soup.select('ul > li > a[href][time_added]')

                parsed_count = 0
                for link in article_links:
                    # Ensure it's an article link and not e.g. category link
                    if not link.has_attr('time_added'): # A good indicator of an article link
                        continue

                    url = link['href']
                    title = html.unescape(link.string.strip() if link.string else url)
                    time_added_str = link['time_added'] # Unix timestamp string
                    tags_str = link.get('tags', '') # Comma-separated string

                    try:
                        saved_date_unix = int(time_added_str)
                        saved_date_iso = datetime.fromtimestamp(saved_date_unix, tz=timezone.utc).isoformat()
                    except ValueError:
                        logger.warning(f"🟡 Could not parse time_added '{time_added_str}' for {url}. Using current time.")
                        saved_date_iso = common.get_current_timestamp_iso()

                    tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]

                    imported_items.append({
                        'original_url': url,
                        'title': title,
                        'saved_date_iso': saved_date_iso,
                        'tags': tags_list,
                        # Pocket ID is not in the HTML export.
                        # Status (read/unread) can be inferred from the section (<h1>) it's under.
                        # For simplicity, let's assume all imported are 'unread' or use tags.
                        # Pocket uses a "Read Archive" section.
                        'is_archived': link.find_parent('ul').find_previous_sibling('h1', string='Read Archive') is not None
                    })
                    parsed_count +=1
                
                logger.info(f"Parsed {parsed_count} items from Pocket export.")
                return imported_items

            async def import_from_pocket_file(self, export_file_path: Path, progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[int, int]:
                """
                Imports articles from a Pocket export file (ril_export.html).
                Returns (successful_imports, failed_imports_or_duplicates).
                """
                if not self.fs_manager.get_local_sync_root():
                    logger.error("🛑 Import failed: Local sync root not configured.")
                    return 0, 0

                try:
                    with open(export_file_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                except Exception as e:
                    logger.error(f"🛑 Could not read Pocket export file {export_file_path}: {e}")
                    return 0, 0

                pocket_items_metadata = self._parse_pocket_export_html(html_content)
                total_items = len(pocket_items_metadata)
                successful_imports = 0
                failed_or_skipped = 0

                # Check for duplicates based on original_url before fetching
                # This requires loading all existing article URLs.
                existing_urls: Set[str] = set()
                # For better performance on large libraries, query the index or a dedicated URL store.
                # For now, iterate through local files (can be slow).
                # Optimization: Get URLs from search index if available and comprehensive.
                # all_articles = [self.fs_manager.load_article(p) for p in self.fs_manager.get_all_article_filepaths()]
                # existing_urls = {art.original_url for art in all_articles if art}
                # This is still slow. A better way is to query Whoosh for all 'original_url' fields or maintain a set.

                # Let's assume a method in SearchManager or a local cache of URLs for deduplication
                # For now, we'll check one by one, which is inefficient but illustrates the logic.
                # A better deduplication would be `search_manager.find_article_by_url(url)`.

                for i, item_meta in enumerate(pocket_items_metadata):
                    url = item_meta['original_url']
                    logger.info(f"Processing Pocket import ({i+1}/{total_items}): {url}")

                    # Deduplication (PRD 5.8)
                    # Simplistic check: if a file with a similar name or same URL exists in index.
                    # A robust check needs to query the search index for `original_url`.
                    # For now, we skip this fine-grained check and rely on content parser not overwriting
                    # or assuming this is a first-time import.
                    # Proper deduplication:
                    # existing_article_hits = self.search_manager.search(f"original_url:\"{url}\"", limit=1)
                    # if existing_article_hits:
                    #    logger.info(f"Skipping duplicate (URL exists): {url}")
                    #    failed_or_skipped += 1
                    #    if progress_callback: progress_callback(i + 1, total_items)
                    #    continue

                    # Fetch and parse content using ContentParserService
                    # PRD 5.8: "Content from Pocket's export should be re-parsed/cleaned using Trafilatura"
                    # This is handled by content_parser.parse_url()
                    article: Optional[Article] = await self.content_parser.parse_url(url)

                    if article:
                        # Apply metadata from Pocket export
                        article.title = item_meta['title'] # Override title from Pocket
                        article.saved_date = item_meta['saved_date_iso']
                        article.tags = list(set(article.tags + item_meta['tags'])) # Merge tags
                        article.source_application = constants.SOURCE_POCKET_MIGRATION
                        if item_meta.get('is_archived', False):
                            article.status = constants.STATUS_ARCHIVED
                        
                        # Pocket ID is not available from HTML export, so article.pocket_id remains None.

                        # Save the article
                        saved_path = self.fs_manager.save_article(article)
                        if saved_path:
                            self.search_manager.add_or_update_article(article)
                            successful_imports += 1
                            # Optionally, fetch thumbnail here
                            # await self._fetch_and_save_thumbnail_for_article(article)
                        else:
                            logger.error(f"Failed to save imported article: {url}")
                            failed_or_skipped += 1
                    else:
                        logger.error(f"Failed to parse content for imported article: {url}")
                        failed_or_skipped += 1
                    
                    if progress_callback:
                        progress_callback(i + 1, total_items)
                
                logger.info(f"Pocket import complete. Successfully imported: {successful_imports}, Failed/Skipped: {failed_or_skipped}")
                return successful_imports, failed_or_skipped
        ```
    *   Add `from typing import Callable, Set` to imports.
    *   Pocket's standard HTML export (`ril_export.html`) **does not include article content, notes, or highlights**. It only contains links and metadata (URL, title, time added, tags). The PRD (5.8) expectation of migrating notes and highlights from Pocket might require a different Pocket export mechanism or API access, which is not standard. This implementation assumes the standard HTML export.
    *   The importer should re-fetch and re-parse content using `ContentParserService` as per PRD.
    *   Deduplication: Crucial. The best way is to check `original_url` against the existing library (e.g., via `SearchManager`).
    *   Progress monitoring via `tqdm` (for console/log) or a UI callback.

---

#### 23. `src/purse/services/notification_service.py`
*   **File Path**: `src/purse/services/notification_service.py`
*   **Intent**: Fetches and manages developer notifications. Also provides a way for the app to show system notifications (Toga's capability).
*   **Upstream Dependencies**: `httpx`, `json`, `logging`, `src/purse/services/http_client.py`, `src/purse/config_manager.py`.
*   **Downstream Dependencies**: UI components (to display developer notifications), various services (to trigger system notifications).
*   **Changes Needed**:
    *   Create the file.
    *   Add imports:
        ```python
        import json
        import logging
        from typing import Optional, List, Dict, Any, TYPE_CHECKING

        from purse.services.http_client import HttpClient

        if TYPE_CHECKING:
            from purse.config_manager import ConfigManager
            from toga import App # For system notifications

        logger = logging.getLogger(__name__)

        @dataclass
        class DeveloperNotification:
            id: str
            title: str
            message: str
            level: str = "info" # info, warning, error
            url: Optional[str] = None # Link for more info
            timestamp_iso: str # When the notification was issued
        ```
    *   Define `NotificationService` class:
        ```python
        from dataclasses import dataclass # Put at top with other imports

        class NotificationService:
            def __init__(self, config_manager: 'ConfigManager', http_client: HttpClient, toga_app: Optional['App'] = None):
                self.config_manager = config_manager
                self.http_client = http_client
                self.toga_app = toga_app
                self.developer_notifications_url = self.config_manager.get(
                    'developer_notifications_url',
                    "https_default_fallback_url/purse/notifications.json" # Ensure config.yml has a real default
                )
                # Store IDs of notifications already seen/dismissed by user (in local device settings)
                self.seen_notification_ids: Set[str] = set() 
                self._load_seen_notifications()


            def _load_seen_notifications(self):
                # This requires FileSystemManager to be available to load device settings
                # Or, pass device_settings dict if already loaded.
                # For simplicity, assume it's handled externally or not persisted across sessions in this snippet.
                # In a real app, load from fs_manager.load_device_settings().get('seen_notification_ids', [])
                pass

            def _save_seen_notifications(self):
                # Save to fs_manager.save_device_settings({'seen_notification_ids': list(self.seen_notification_ids)})
                pass

            async def fetch_developer_notifications(self) -> List[DeveloperNotification]:
                """Fetches new notifications from the developer-specified URL."""
                if not self.developer_notifications_url:
                    logger.info("Developer notifications URL not configured.")
                    return []
                
                try:
                    logger.debug(f"Fetching developer notifications from: {self.developer_notifications_url}")
                    response = await self.http_client.get_url(self.developer_notifications_url, timeout=10.0)
                    raw_notifications = response.json() # Assuming JSON response

                    notifications: List[DeveloperNotification] = []
                    for raw_notif in raw_notifications: # Assuming raw_notifications is a list of dicts
                        if not isinstance(raw_notif, dict): continue # Skip malformed entries
                        notif_id = raw_notif.get('id')
                        if not notif_id: continue # Skip notifications without an ID

                        # Filter out already seen notifications
                        # if notif_id in self.seen_notification_ids:
                        #     continue

                        notifications.append(DeveloperNotification(
                            id=notif_id,
                            title=raw_notif.get('title', 'Notification'),
                            message=raw_notif.get('message', ''),
                            level=raw_notif.get('level', 'info'),
                            url=raw_notif.get('url'),
                            timestamp_iso=raw_notif.get('timestamp_iso', common.get_current_timestamp_iso())
                        ))
                    
                    logger.info(f"Fetched {len(notifications)} new developer notifications.")
                    return notifications
                except Exception as e:
                    logger.error(f"🛑 Failed to fetch or parse developer notifications: {e}")
                    return []

            def mark_notification_seen(self, notification_id: str):
                self.seen_notification_ids.add(notification_id)
                self._save_seen_notifications()


            # --- System Notifications (using Toga) ---
            def show_system_notification(self, title: str, message: str, level: str = "info"):
                """
                Displays a system notification.
                'level' can influence icon or behavior if Toga supports it.
                PRD 3.5, 5.10: "System notifications for important errors or completion of significant background tasks"
                """
                if not self.toga_app:
                    logger.warning("Toga app instance not available, cannot show system notification via Toga.")
                    # Fallback to console log
                    log_method = logger.info
                    if level == "error": log_method = logger.error
                    elif level == "warning": log_method = logger.warning
                    log_method(f"SYSTEM NOTIFICATION [{title}]: {message}")
                    return

                try:
                    # Toga's notification API might be simpler, e.g. app.main_window.info_dialog(title, message)
                    # Or for more passive notifications if Toga supports system tray style:
                    # Check Toga documentation for `toga.Notification` or similar.
                    # As of current Toga, there isn't a direct cross-platform "system tray notification API".
                    # Dialogs are the primary way.
                    if level == "error":
                        self.toga_app.main_window.error_dialog(title, message)
                    elif level == "warning":
                        self.toga_app.main_window.question_dialog(title, message) # Or warning_dialog if available
                    else: # info
                        self.toga_app.main_window.info_dialog(title, message)
                    logger.info(f"Displayed system notification: {title}")
                except Exception as e:
                    logger.error(f"🛑 Failed to show system notification using Toga: {e}")
        ```
    *   Add `from dataclasses import dataclass` and `from typing import Set` and `from purse.utils import common` to imports.
    *   Developer notifications URL should be configurable, defaulting as per PRD.
    *   Need a mechanism to store seen notification IDs (e.g., in local device settings managed by `FileSystemManager`) to avoid re-showing them.
    *   System notifications (PRD 5.10) will likely use Toga's dialogs (`info_dialog`, `error_dialog`) or other platform-specific notification mechanisms if Toga provides access.

---

#### 24. `src/purse/services/tts_service.py`
*   **File Path**: `src/purse/services/tts_service.py`
*   **Intent**: Provides Text-to-Speech functionality using native OS engines.
*   **Upstream Dependencies**: `platform`, `subprocess` (for direct CLI calls if no good library), or a cross-platform TTS Python library (e.g., `pyttsx3`, `gTTS` for online, or Toga's own capabilities if any). **Decision**: `pyttsx3` is a common offline, cross-platform choice.
*   **Downstream Dependencies**: UI components for TTS controls.
*   **Changes Needed**:
    *   Create the file.
    *   Add imports and initialize `pyttsx3` (or chosen library).
        ```python
        import pyttsx3
        import logging
        import platform
        from typing import Optional
        import asyncio

        logger = logging.getLogger(__name__)

        class TTSService:
            def __init__(self):
                self.engine: Optional[pyttsx3.Engine] = None
                self.is_speaking: bool = False
                self.current_spoken_text: Optional[str] = None
                try:
                    self.engine = pyttsx3.init()
                    # Configure engine if needed (rate, voice, volume) - can be done later via methods
                    # self.engine.connect('started-utterance', self.on_speech_start)
                    self.engine.connect('finished-utterance', self.on_speech_finish) # To reset is_speaking
                    self.engine.connect('error', self.on_speech_error)

                except Exception as e: # pyttsx3 might fail if drivers are missing
                    logger.error(f"🛑 Failed to initialize TTS engine (pyttsx3): {e}. TTS will be unavailable.")
                    self.engine = None
            
            def on_speech_finish(self, name, completed):
                logger.debug(f"TTS finished utterance (completed: {completed}). Name: {name}")
                if completed: # Check if it was the utterance we started
                    self.is_speaking = False
                    self.current_spoken_text = None
                    # The pyttsx3 runAndWait loop might exit now if queue is empty.
            
            def on_speech_error(self, name, exception):
                logger.error(f"🛑 TTS error during speech. Name: {name}, Error: {exception}")
                self.is_speaking = False
                self.current_spoken_text = None


            async def speak(self, text: str, voice_id: Optional[str] = None, rate: Optional[int] = None, volume: Optional[float] = None) -> bool:
                if not self.engine:
                    logger.warning("🟡 TTS engine not available. Cannot speak.")
                    return False
                if self.is_speaking:
                    logger.warning("🟡 TTS engine is already speaking. Call stop() first or wait.")
                    # Optionally, queue this request or stop current and speak new.
                    # For now, just reject.
                    return False

                try:
                    if voice_id: self.engine.setProperty('voice', voice_id)
                    if rate: self.engine.setProperty('rate', rate) # Default is often 200
                    if volume: self.engine.setProperty('volume', volume) # Range 0.0 to 1.0

                    self.is_speaking = True
                    self.current_spoken_text = text # Store for potential resume logic if supported
                    
                    logger.info(f"TTS starting to speak: \"{text[:50]}...\"")
                    self.engine.say(text)
                    
                    # runAndWait is blocking. To make it async-friendly and allow UI updates:
                    # We need to run this in a separate thread, or use pyttsx3's event loop if it's non-blocking.
                    # pyttsx3's `startLoop(False)` and `iterate()` driven by an external loop is an option.
                    # Or, simpler for now, run the blocking part in a thread.
                    await asyncio.to_thread(self.engine.runAndWait)
                    # Note: on_speech_finish should set is_speaking to False.
                    # However, runAndWait() blocks until all queued `say` commands are processed.
                    # If an error occurs or it's stopped early, on_speech_finish might not set it.
                    # So, reset here as a fallback, but rely on callback for cleaner state.
                    # self.is_speaking = False # This line makes on_speech_finish a bit redundant for this flag
                    
                    return True # True if it tried to speak (actual completion handled by callback)
                except Exception as e:
                    logger.error(f"🛑 Error during TTS speak call: {e}")
                    self.is_speaking = False
                    self.current_spoken_text = None
                    return False

            async def stop(self) -> None:
                if not self.engine: return
                if self.is_speaking: # Or if engine has items in queue
                    logger.info("TTS attempting to stop speech.")
                    # pyttsx3 stop command might not be immediate or always work across platforms.
                    # It clears the command queue.
                    self.engine.stop()
                    # For some backends, `runAndWait` might need to be called for `stop` to take full effect,
                    # or the loop needs to iterate. This can be tricky.
                    # If `engine.isBusy()` is available, can check.
                    # For now, assume stop() is effective.
                    self.is_speaking = False
                    self.current_spoken_text = None


            def get_available_voices(self) -> List[Dict[str, Any]]:
                if not self.engine: return []
                voices_data = []
                try:
                    voices = self.engine.getProperty('voices')
                    for voice in voices:
                        voices_data.append({
                            'id': voice.id,
                            'name': voice.name,
                            'languages': getattr(voice, 'languages', []), # May not exist on all platforms
                            'gender': getattr(voice, 'gender', None),   # May not exist
                            'age': getattr(voice, 'age', None)        # May not exist
                        })
                    return voices_data
                except Exception as e:
                    logger.error(f"🛑 Could not retrieve TTS voices: {e}")
                    return []

            def set_property(self, name: str, value: Any):
                if not self.engine: return
                try:
                    self.engine.setProperty(name, value)
                except Exception as e:
                    logger.error(f"🛑 Error setting TTS property {name} to {value}: {e}")

            # Future: pause, resume if pyttsx3/platform supports it.
            # Future: synchronized text highlighting (complex, requires event stream from TTS engine about word boundaries).
        ```
    *   PRD 5.6: UI controls for play, pause, stop. Voice selection, speed control.
    *   `pyttsx3` provides `getProperty('voices')`, `setProperty('voice', id)`, `setProperty('rate', val)`, `setProperty('volume', val)`.
    *   `engine.say(text)` is non-blocking (queues). `engine.runAndWait()` is blocking.
        *   For async UI, `runAndWait()` must be run in a thread (`asyncio.to_thread`).
        *   Or use `engine.startLoop(False)` and `engine.iterate()` in an external loop, but this is more complex.
    *   Error handling if TTS engine fails to initialize or speak.

---

#### 25. `src/purse/app_state.py` (Optional, or manage within Main Toga App Class)
*   **File Path**: `src/purse/app_state.py`
*   **Intent**: A centralized place to hold application-wide state, like the current list of articles being displayed, selected article, user preferences loaded from `settings.yml`. This helps in decoupling UI components.
*   **Upstream Dependencies**: `dataclasses`, `typing`, `src/purse/models/article.py`.
*   **Downstream Dependencies**: UI components, `main.py` (or Toga App class).
*   **Changes Needed**:
    *   Define a dataclass or a simple class to hold state.
        ```python
        from dataclasses import dataclass, field
        from typing import List, Optional, Dict, Any
        from purse.models.article import Article

        @dataclass
        class ReadingPreferences:
            font_family: str = "sans-serif" # Default values
            font_size: int = 14
            theme: str = "light" # light, dark, sepia
            # Add other UI preferences from PRD 5.3, 5.9

        @dataclass
        class AppState:
            # Loaded articles currently in the list view
            current_article_list: List[Article] = field(default_factory=list)
            selected_article: Optional[Article] = None
            
            # Search state
            last_search_query: Optional[str] = None
            current_search_results: List[Article] = field(default_factory=list) # Or list of dicts from search_manager

            # User preferences (loaded from settings.yml via ConfigManager)
            reading_prefs: ReadingPreferences = field(default_factory=ReadingPreferences)
            developer_notification_url: Optional[str] = None # From settings.yml
            # Other synced user settings

            # Cloud sync state
            cloud_provider_name: Optional[str] = None
            is_syncing: bool = False
            last_sync_status: Optional[str] = None # "Success", "Failed: reason"
            last_successful_sync_time_iso: Optional[str] = None

            # App status messages for UI
            status_messages: List[str] = field(default_factory=list) # For main page status area
            
            # Loaded on startup
            all_tags_in_library: Set[str] = field(default_factory=set)

            # Add other states as needed
        ```
    *   This object would be instantiated in `main.py` (or Toga `App` class) and passed to UI components or services that need to read/write shared state.
    *   Updates to this state should trigger UI refreshes (Toga's data binding or manual refresh calls).
    *   **Decision**: This is a good pattern. Create `app_state.py`.

---

#### 26. `src/purse/ui/widgets.py` (and other UI module files like `views.py`, `commands.py`)
*   **File Path**: `src/purse/ui/widgets.py` (and other Toga UI structure)
*   **Intent**: Contains custom Toga widgets or configurations of standard widgets used across the application. Organizes UI components.
*   **Upstream Dependencies**: `toga`, `src/purse/app_state.py`, service modules (for command handlers).
*   **Downstream Dependencies**: `main.py` (Toga App class).
*   **Changes Needed**: (This is high-level as Toga UI is extensive)
    *   Plan the Toga UI structure:
        *   `main_window` with main layout (e.g., sidebar for sources/tags, main area for article list/reader).
        *   `ArticleListView`: Displays articles (card, list, headline). Handles sorting.
        *   `ArticleReaderView`: Displays single article content. Font/theme customization.
        *   `SettingsView`: For cloud setup, preferences.
        *   `Toolbar/Menubar`: For global actions (Sync, Add URL, Import, Search bar).
    *   Implement UI elements as per PRD 5.3, 5.4, 5.5.
        *   Navigation, article list views (Card, List, Headline) with thumbnails.
        *   Sorting options.
        *   Reading view with font/theme customization.
        *   Search input and results display.
        *   Tagging interface (add/remove, batch, autocomplete).
        *   TTS controls (play, pause, stop).
        *   Status area for errors/sync status (PRD 3.5, 5.10).
        *   In-app log viewer (PRD 3.5, 5.10).
    *   Use `tqdm` principles for progress in UI (Toga `ProgressBar` or textual updates).
    *   Link UI actions to service methods via Toga command handlers.
    *   Data binding: Toga has some data binding capabilities (e.g., for `Table`, `DetailedList`). Use these where possible to link UI to `AppState` or other data sources.
    *   **This is a major part of the work and would be broken down into many smaller tasks/files for UI components.** Example:
        *   `src/purse/ui/article_list_view.py`
        *   `src/purse/ui/reader_view.py`
        *   `src/purse/ui/main_app_window.py`
        *   `src/purse/ui/commands.py` (for Toga command definitions)
    *   **Example of a simple command handler structure (in `main.py` or a commands module):**
        ```python
        # import toga
        # from purse.app_state import AppState
        # from purse.services import ...

        # async def add_url_command_handler(widget, app_state: AppState, services_container: Any):
        #     url = await widget.app.main_window.prompt_dialog("Add URL", "Enter URL to save:")
        #     if url:
        #         widget.app.show_status_message(f"Saving {url}...") # Hypothetical status update
        #         # Call content_parser.parse_url, then fs_manager.save_article, then search_manager.add
        #         # Update app_state.current_article_list
        #         # Refresh UI
        #         pass
        ```

---

#### 27. `src/purse/main.py` (or `src/purse/__main__.py` for `python -m purse`)
*   **File Path**: `src/purse/main.py`
*   **Intent**: Main entry point of the application. Initializes Toga app, services, and orchestrates overall application flow.
*   **Upstream Dependencies**: `toga`, all service modules, `logger_setup.py`, `config_manager.py`, `app_state.py`, UI modules.
*   **Downstream Dependencies**: None (it's the executable).
*   **Changes Needed**:
    *   Define the main Toga `App` class.
        ```python
        import toga
        from toga.style import Pack
        from toga.style.pack import COLUMN, ROW, LEFT, RIGHT, CENTER, BOLD

        from purse.config_manager import ConfigManager
        from purse.logger_setup import setup_logging
        from purse.app_state import AppState #, ReadingPreferences
        from purse.utils import constants, common
        from purse.services.http_client import HttpClient
        from purse.services.file_system_manager import FileSystemManager
        # Import other services: ContentParser, SearchManager, Cloud Services, SyncManager, etc.
        from purse.services.content_parser import ContentParserService
        from purse.services.search_manager import SearchManager
        from purse.services.pocket_importer import PocketImporterService
        from purse.services.notification_service import NotificationService
        from purse.services.tts_service import TTSService
        from purse.services.cloud_storage.base_cloud_service import BaseCloudService # For type hint
        # Import specific cloud services as needed for setup
        from purse.services.cloud_storage.dropbox_service import DropboxService 
        # from purse.services.cloud_storage.google_drive_service import GoogleDriveService
        # from purse.services.cloud_storage.onedrive_service import OneDriveService
        from purse.services.sync_manager import SyncManager

        # Import UI components (these would be defined in ui sub-package)
        # from purse.ui.main_app_window import MainAppWindow # Example

        class PurseApp(toga.App):
            def startup(self):
                """Construct and show the Toga app."""
                # 1. Initialize ConfigManager (base config.yml)
                self.config_manager = ConfigManager(base_config_path='config.yml') # Adjust path if needed

                # 2. Setup Logging (uses ConfigManager for log settings)
                # FileSystemManager needs to be initialized first if logs_dir is relative to app_data_dir
                # For now, assume logs_dir in config.yml is relative to execution or absolute.
                # Or, pass a temporary simple FSM to logger_setup if needed for paths.
                # Let's assume logger can use a config-defined path for now.
                # The logger setup MUST HAPPEN EARLY.
                setup_logging(self.config_manager) 
                logger = logging.getLogger(__name__) # Get logger after setup
                logger.info(f"🟢 {constants.APP_NAME} starting up...")

                # 3. Initialize AppState
                self.app_state = AppState()

                # 4. Initialize Services (dependency injection style)
                self.http_client = HttpClient(self.config_manager)
                # Pass self (toga.App instance) to FSM for OS-idiomatic paths
                self.fs_manager = FileSystemManager(self.config_manager, toga_app=self) 
                
                # --- Post FSM Init: Load device settings and synced settings ---
                self._load_device_specific_settings() # Affects AppState, e.g. seen notifications
                self._attempt_load_synced_settings() # Affects AppState, ConfigManager

                # --- Continue service initialization ---
                self.content_parser = ContentParserService(self.http_client, self.config_manager)
                self.search_manager = SearchManager(self.fs_manager)
                self.tts_service = TTSService()
                self.notification_service = NotificationService(self.config_manager, self.http_client, toga_app=self)
                # Pass FSM to notification service if it saves seen_ids via device_settings
                # self.notification_service.fs_manager = self.fs_manager (or pass in constructor)


                # Cloud Service and Sync Manager (conditionally initialized after setup)
                self.cloud_service: Optional[BaseCloudService] = None
                self.sync_manager: Optional[SyncManager] = None
                self._initialize_cloud_and_sync() # Based on saved settings

                self.pocket_importer = PocketImporterService(
                    self.config_manager, self.content_parser, self.fs_manager, self.search_manager
                )
                
                # TODO: Initial load of articles from local filesystem if sync root is known
                self.load_initial_articles_and_tags()


                # 5. Create Main Window and UI
                # self.main_window = MainAppWindow(app=self, app_state=self.app_state, services_container=self)
                # For now, a placeholder window:
                self.main_window = toga.MainWindow(title=self.title)
                main_box = toga.Box(style=Pack(direction=COLUMN, padding=10))
                main_box.add(toga.Label(f"Welcome to {constants.APP_NAME}! Content goes here.", style=Pack(text_align=CENTER)))
                
                status_label = toga.Label("Status: Initializing...", style=Pack(padding_top=10))
                self.app_state.status_label_widget = status_label # Store for updates
                main_box.add(status_label)

                self.main_window.content = main_box
                self.main_window.show()

                # TODO: Trigger initial sync, fetch developer notifications in background
                # self.add_background_task(self.initial_background_tasks)

            def _load_device_specific_settings(self):
                device_settings = self.fs_manager.load_device_settings()
                # Example: self.app_state.seen_notification_ids = set(device_settings.get('seen_notification_ids', []))
                # Example: self.main_window.position, self.main_window.size (if Toga allows setting these from loaded values)
                logger.info("Device specific settings loaded (if any).")


            def _attempt_load_synced_settings(self):
                """Loads settings.yml from the configured local sync root."""
                local_sync_root_str = self.config_manager.get('user_preferences.local_sync_root') # Assuming this is stored
                if local_sync_root_str:
                    self.fs_manager.set_local_sync_root(local_sync_root_str)
                    synced_settings_path = self.fs_manager.get_synced_settings_path()
                    if synced_settings_path and synced_settings_path.exists():
                        self.config_manager.load_settings(synced_settings_path)
                        logger.info(f"Synced settings loaded from {synced_settings_path}")
                        # Update AppState from these newly loaded settings
                        self._update_app_state_from_synced_settings()
                    else:
                        logger.info("No synced settings.yml found at configured path. Using defaults or base config.")
                else:
                    logger.info("Local sync root not configured. Synced settings not loaded.")


            def _update_app_state_from_synced_settings(self):
                """Update AppState attributes based on settings from settings.yml (via ConfigManager)."""
                self.app_state.reading_prefs.font_family = self.config_manager.get(
                    'ui.reading_view.font_family', constants.DEFAULT_FONT_FAMILY
                )
                # ... load other preferences into self.app_state ...
                self.app_state.developer_notification_url = self.config_manager.get(
                    'developer_notifications_url_override', # User can override default from config.yml
                    self.config_manager.get('developer_notifications_url') # Default from config.yml
                )
                # Update notification service URL if it changed
                if self.notification_service and self.app_state.developer_notification_url:
                    self.notification_service.developer_notifications_url = self.app_state.developer_notification_url
                
                self.app_state.cloud_provider_name = self.config_manager.get('cloud.provider_name')
                logger.info("AppState updated from synced settings.")


            def _initialize_cloud_and_sync(self):
                """Initializes cloud service and sync manager if configured."""
                provider_name = self.config_manager.get('cloud.provider_name')
                access_token = self.config_manager.get('cloud.access_token') # Securely load these
                refresh_token = self.config_manager.get('cloud.refresh_token')
                user_cloud_root = self.config_manager.get('cloud.user_root_folder_path', '/Apps/Purse')

                if provider_name:
                    logger.info(f"Initializing cloud provider: {provider_name}")
                    if provider_name == DropboxService.PROVIDER_NAME:
                        self.cloud_service = DropboxService(self.config_manager, access_token, refresh_token)
                    # elif provider_name == GoogleDriveService.PROVIDER_NAME:
                    #     self.cloud_service = GoogleDriveService(self.config_manager, access_token, refresh_token)
                    # elif provider_name == OneDriveService.PROVIDER_NAME:
                    #     self.cloud_service = OneDriveService(self.config_manager, access_token, refresh_token)
                    else:
                        logger.error(f"Unsupported cloud provider in settings: {provider_name}")
                        return

                    if self.cloud_service:
                        self.cloud_service.set_root_folder_path(user_cloud_root)
                        self.sync_manager = SyncManager(
                            self.config_manager, self.fs_manager, self.cloud_service, self.search_manager
                        )
                        logger.info("SyncManager initialized.")
                        # Potentially trigger an initial sync here or after UI is fully up.
                else:
                    logger.info("No cloud provider configured in settings.")

            def load_initial_articles_and_tags(self):
                """Loads all articles from local file system and populates AppState, rebuilds index if needed."""
                logger.info("Loading initial articles from local file system...")
                sync_root = self.fs_manager.get_local_sync_root()
                if not sync_root:
                    logger.warning("Cannot load initial articles: local sync root not configured.")
                    self.app_state.current_article_list = []
                    self.app_state.all_tags_in_library = set()
                    return

                all_articles: List[Article] = []
                all_tags: Set[str] = set()
                article_paths = self.fs_manager.get_all_article_filepaths()
                
                # For tqdm like progress in logs for initial load
                # from tqdm import tqdm
                # for fpath in tqdm(article_paths, desc="Loading local articles"):
                for fpath in article_paths:
                    article = self.fs_manager.load_article(fpath)
                    if article:
                        all_articles.append(article)
                        if article.tags:
                            all_tags.update(article.tags)
                
                self.app_state.current_article_list = sorted(all_articles, key=lambda a: a.saved_date, reverse=True) # Default sort
                self.app_state.all_tags_in_library = all_tags
                logger.info(f"Loaded {len(all_articles)} articles and {len(all_tags)} unique tags from local storage.")

                # Optionally, rebuild search index on startup or ensure it's consistent.
                # This can be time-consuming. For now, assume index is managed per-change.
                # If a full rebuild is desired:
                # self.add_background_task(self.search_manager.rebuild_index, articles=all_articles)
                # Or just verify index consistency if Whoosh supports it.

            async def on_exit(self):
                # Save any pending state, close resources
                logger.info(f"🟢 {constants.APP_NAME} shutting down...")
                if self.http_client:
                    await self.http_client.close()
                
                # Save device-specific settings
                # device_settings_to_save = {'seen_notification_ids': list(self.app_state.seen_notification_ids)}
                # self.fs_manager.save_device_settings(device_settings_to_save)

                # Ensure TTS engine stops if it was speaking
                if self.tts_service and self.tts_service.is_speaking:
                    await self.tts_service.stop()

                logger.info(f"{constants.APP_NAME} shutdown complete.")
                return True # True to allow exit


        def main():
            return PurseApp(
                formal_name=constants.APP_NAME,
                app_id=constants.APP_ID,
                app_name="purse", # project name for resources
                author=constants.APP_AUTHOR,
                icon='resources/purse_icon', # Will look for purse_icon.png, .icns etc.
                # home_page='https://github.com/cspenn/purse' # Optional
            )

        if __name__ == '__main__':
            main().main_loop()
        ```
    *   Structure:
        *   `PurseApp.startup()`: Initializes services, loads initial data, builds UI.
        *   `PurseApp.on_exit()`: Clean up resources.
        *   Service instances should be stored on `self` (e.g., `self.content_parser`).
        *   Pass `self` (the Toga `App` instance) to services that need it (e.g., `FileSystemManager` for `app.paths`, `NotificationService` for dialogs).
    *   Configuration load order:
        1.  `ConfigManager` loads `config.yml` (base defaults).
        2.  `FileSystemManager` initialized (knows where user data dirs are).
        3.  App tries to load `device_settings.yml` (local non-synced UI state etc.).
        4.  App tries to load `settings.yml` from the configured sync root (if known). `ConfigManager` is updated with these. `AppState` is populated.
        5.  Cloud service initialized using tokens/settings from `ConfigManager`.
    *   Initial data load: On startup, scan the local sync directory, load articles into `AppState`, and populate/verify the search index.
    *   Background tasks for initial sync or developer notifications using `app.add_background_task()`.

---

#### 28. Resource Files (`resources/`)
*   **File Path**: `purse/resources/` (directory)
*   **Intent**: Store application icons and other static resources.
*   **Changes Needed**:
    *   Create the directory: `src/purse/resources/` (if `app_name="purse"` is used in `toga.App`, Toga looks in `src/purse/resources`). Or just `resources/` at the project root if `app_name` is not set or refers to project dir. The example uses `app_name="purse"`.
    *   Add application icons in various formats/sizes as needed by Toga for different platforms (e.g., `purse_icon.png`, `purse_icon.icns`). Refer to Toga documentation for icon specifics.

---

