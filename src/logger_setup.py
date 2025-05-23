import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List
import os # Required for os.path.getmtime for sorting log files

# Conditional import for ConfigManager to avoid circular dependency at runtime
# if actual type checking is needed. For a .py file, can often just import.
if TYPE_CHECKING:
    from purse.config_manager import ConfigManager

# Assuming constants.py is in purse.utils
# Adjust import path if necessary based on project structure
from purse.utils import constants

class EmojiFormatter(logging.Formatter):
    """
    A custom log formatter that adds an emoji based on the log level.
    Uses LOG_EMOJI_MAP from constants.
    """
    def format(self, record: logging.LogRecord) -> str:
        # Get the emoji for the current log level, default to empty string if not found
        record.emoji_level = constants.LOG_EMOJI_MAP.get(record.levelno, "")
        return super().format(record)

def setup_logging(config_manager: 'ConfigManager', logs_base_path: Optional[Path] = None) -> Path:
    """
    Configures the application-wide logging system.

    Args:
        config_manager: An instance of ConfigManager to retrieve logging settings.
        logs_base_path: An optional base path for the logs directory. If None,
                        logs_dir from config will be treated as relative to CWD
                        or absolute if so defined in config. This path is ideally
                        provided by FileSystemManager as app_data_dir / logs_fragment.

    Returns:
        The absolute path to the initialized logs directory.
    """
    log_level_str = config_manager.get('logging.log_level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Determine logs directory path
    logs_dir_fragment = config_manager.get('logging.logs_dir', 'logs') # e.g., "logs" or "user_data/logs"
    
    if logs_base_path:
        logs_dir_abs = logs_base_path / logs_dir_fragment 
    else:
        # Fallback: if logs_base_path is not provided, treat logs_dir_fragment
        # as relative to CWD or absolute if it's an absolute path itself.
        logs_dir_abs = Path(logs_dir_fragment)
        if not logs_dir_abs.is_absolute():
            logs_dir_abs = Path.cwd() / logs_dir_abs
            
    try:
        logs_dir_abs.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # Fallback to a temporary directory if preferred logs_dir is unwritable
        # This is an emergency fallback, ideally permissions should be correct.
        temp_logs_dir = Path.home() / ".purse_temp_logs" / logs_dir_fragment
        logging.basicConfig(level=logging.WARNING) # Use basic config for this critical warning
        logging.warning(
            f"🛑 Original logs directory '{logs_dir_abs}' is not writable due to {e}. "
            f"Attempting to use fallback log directory: {temp_logs_dir}"
        )
        logs_dir_abs = temp_logs_dir
        try:
            logs_dir_abs.mkdir(parents=True, exist_ok=True)
        except OSError as final_e:
            logging.error(
                f"🛑 Fallback logs directory '{logs_dir_abs}' is also not writable due to {final_e}. "
                "Logging to console only."
            )
            # No file logging possible if this fails. Console logging will still be set up.
            # Set logs_dir_abs to None or a flag to indicate no file handler.
            # For now, let it proceed; file handler will fail and log an error.
            pass


    # Generate timestamped log file name
    current_time_str = datetime.now().strftime(config_manager.get('logging.date_format_logfile_suffix', '%Y-%m-%d-%H-%M-%S'))
    log_file_name = f"log-{current_time_str}.log"
    log_file_path = logs_dir_abs / log_file_name

    # Get format strings from config
    console_format_str = config_manager.get('logging.log_format_console', "%(asctime)s %(emoji_level)s%(name)s - %(message)s")
    file_format_str = config_manager.get('logging.log_format_file', "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s")
    date_format_str = config_manager.get('logging.date_format', "%Y-%m-%d %H:%M:%S")

    # Root logger configuration
    root_logger = logging.getLogger()
    
    # Check current log level of root logger. If it's the default WARNING or lower (more restrictive), set it.
    # If it's already set to something more verbose (e.g. DEBUG by a previous setup), don't make it less verbose.
    if root_logger.level == logging.NOTSET or root_logger.level > log_level:
        root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplication if setup_logging is called multiple times
    # (e.g., in tests or due to app lifecycle).
    for handler in root_logger.handlers[:]:
        # Check if it's one of our handlers to be safer, though workplan implies clearing all.
        # For now, clear all as per workplan's spirit.
        root_logger.removeHandler(handler)
        handler.close() # Close handler before removing

    # Console Handler with EmojiFormatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level) # Console handler respects the global log level
    console_formatter = EmojiFormatter(fmt=console_format_str, datefmt=date_format_str)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handler (only if logs_dir_abs is valid and writable)
    if logs_dir_abs.exists() and os.access(logs_dir_abs, os.W_OK):
        try:
            file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
            file_handler.setLevel(log_level) # File handler also respects the global log level
            file_formatter = logging.Formatter(fmt=file_format_str, datefmt=date_format_str)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

            # Clean up old log files
            max_log_files = config_manager.get('logging.max_log_files', 10)
            if max_log_files > 0: # Ensure max_log_files is positive
                # List log files, sort by modification time (oldest first)
                # Glob for "log-*.log" to match the timestamped format
                existing_logs: List[Path] = sorted(
                    [p for p in logs_dir_abs.glob('log-*.log') if p.is_file()],
                    key=os.path.getmtime # os.path.getmtime for Path objects
                )
                
                files_to_delete_count = len(existing_logs) - max_log_files
                if files_to_delete_count > 0:
                    logs_to_delete = existing_logs[:files_to_delete_count]
                    for old_log_file in logs_to_delete:
                        try:
                            old_log_file.unlink()
                        except OSError as e:
                            # Use a basic print or pre-existing basicConfig logger if root_logger is not fully set up
                            logging.warning(f"🟡 Could not delete old log file {old_log_file}: {e}")
            root_logger.info(f"Logging initialized. Level: {log_level_str}. Log file: {log_file_path}")
        except Exception as e:
            # Fallback to console if file handler fails for any reason (e.g. disk full)
            logging.basicConfig(level=log_level) # Ensure basicConfig is set if we only have console
            root_logger.error(f"🛑 Failed to set up file logging to {log_file_path}: {e}. File logging disabled.")
    else:
        root_logger.warning(f"🟡 Log directory {logs_dir_abs} is not writable or does not exist. File logging disabled.")


    # Example of how to get a logger in other modules:
    # import logging
    # logger = logging.getLogger(__name__) # Get logger for current module
    # logger.info("This is an info message from my_module")
    return logs_dir_abs # Return the path of the logs directory used.

# Placeholder for ConfigManager to allow direct execution for testing if needed
# In real app, ConfigManager instance is passed by main.py
if TYPE_CHECKING:
    from purse.config_manager import ConfigManager
else:
    # This is a mock/dummy ConfigManager for standalone testing of logger_setup.py
    # It's NOT used when integrated into the main application.
    class ConfigManager:
        def __init__(self, settings=None):
            self._settings = settings if settings else {
                'logging.log_level': 'DEBUG',
                'logging.logs_dir': 'temp_logs_for_testing',
                'logging.max_log_files': 3,
                'logging.log_format_console': "%(asctime)s %(emoji_level)s[%(levelname)s] %(name)s - %(message)s",
                'logging.log_format_file': "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
                'logging.date_format': "%Y-%m-%d %H:%M:%S",
                'logging.date_format_logfile_suffix': '%Y-%m-%d-%H-%M-%S' # Added for testing
            }
        def get(self, key, default=None):
            return self._settings.get(key, default)

if __name__ == '__main__':
    # This block is for testing logger_setup.py directly.
    # It will not run when imported by the main application.
    print("Running logger_setup.py directly for testing purposes...")
    
    # Create a dummy constants.py if it's not found (e.g. running standalone)
    try:
        from purse.utils import constants as test_constants
    except ImportError:
        print("Mocking constants for standalone test...")
        class MockConstants:
            LOG_EMOJI_MAP = {
                logging.INFO: "🟢", logging.WARNING: "🟡", logging.ERROR: "🛑",
                logging.CRITICAL: "🛑", logging.DEBUG: "🐛"
            }
        constants = MockConstants() # type: ignore

    # Create a dummy ConfigManager for testing
    mock_config_manager = ConfigManager()

    # Test setup_logging
    # You can pass a specific base path for logs here if you want to control where they go during test
    # e.g., logs_output_dir = Path("test_run_logs")
    # setup_logging(mock_config_manager, logs_base_path=logs_output_dir)
    
    # Default behavior (logs relative to CWD or as defined in mock_config_manager)
    setup_logging(mock_config_manager)


    # Test logging with various levels
    test_logger = logging.getLogger("my_test_module") # Get a logger instance for a "module"
    test_logger.debug("This is a debug message from logger_setup test.")
    test_logger.info("This is an info message from logger_setup test.")
    test_logger.warning("This is a warning message from logger_setup test.")
    test_logger.error("This is an error message from logger_setup test.")
    test_logger.critical("This is a critical message from logger_setup test.")

    # Test another module's logger
    another_logger = logging.getLogger("another.module")
    another_logger.info("Info from another module.")

    print(f"Test complete. Check console output and the '{mock_config_manager.get('logging.logs_dir')}' directory for log files.")
    # Create a few dummy log files to test cleanup
    logs_test_dir = Path(mock_config_manager.get('logging.logs_dir'))
    if logs_test_dir.exists():
        for i in range(5):
            (logs_test_dir / f"log-old-dummy-{i}.log").touch()
        print(f"Created dummy old log files in {logs_test_dir} to test cleanup on next run.")
    else:
        print(f"Log test directory {logs_test_dir} not created, skipping dummy file creation.")

    # Re-run setup_logging to test log cleanup
    print("\nRe-running setup_logging to test log file cleanup...")
    setup_logging(mock_config_manager)
    test_logger.info("Log message after second setup_logging call (for cleanup test).")
    print(f"Cleanup test complete. Check {logs_test_dir} for number of log files.")
