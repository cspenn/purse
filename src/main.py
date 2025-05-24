import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT, RIGHT, CENTER, BOLD # For potential future use in UI
import logging
from pathlib import Path # For type hinting if needed, though mostly handled by services
from typing import TYPE_CHECKING, List, Optional, Set # Added TYPE_CHECKING and other used types

if TYPE_CHECKING:
    from src.models.article import Article
    # Forward declare services that PurseApp holds, if needed for type hints within PurseApp methods
    # For example, if _fetch_and_store_article_thumbnail needed to hint self.fs_manager type explicitly.
    # However, attribute annotations in __init__ or startup usually cover this.
    # from purse.services.file_system_manager import FileSystemManager
    # from purse.services.http_client import HttpClient

# Core application components
from src.config_manager import ConfigManager
from src.logger_setup import setup_logging # setup_logging needs ConfigManager
from src.app_state import AppState, ReadingPreferences # ReadingPreferences for type hinting
from src.utils import constants, common # For APP_NAME, APP_ID, etc.

# Services
from src.services.http_client import HttpClient
from src.services.file_system_manager import FileSystemManager
from src.services.content_parser import ContentParserService
from src.services.search_manager import SearchManager
from src.services.pocket_importer import PocketImporterService
from src.services.notification_service import NotificationService
from src.services.tts_service import TTSService
from src.services.sync_manager import SyncManager

# Cloud Service Implementations (import all, but only instantiate configured one)
from src.services.cloud_storage.base_cloud_service import BaseCloudService
from src.services.cloud_storage.dropbox_service import DropboxService
from src.services.cloud_storage.google_drive_service import GoogleDriveService
from src.services.cloud_storage.onedrive_service import OneDriveService

# UI Placeholders (not fully used in this step, but good for structure)
# from src.ui.main_app_window import MainAppWindow # Example if UI was more built out
# from src.ui import commands as app_commands # Example

# Get a module-level logger after setup_logging is called.
# This will be configured by setup_logging.
logger = logging.getLogger(__name__)


class PurseApp(toga.App):
    def startup(self):
        """
        Construct and show the Toga application.
        This method is called once when the application is starting.
        """
        # 0. Base configuration (config.yml - provides defaults before any user settings)
        # The workplan implies config.yml is at project root, or relative to where app runs.
        # For a packaged app, it might be bundled. Assuming 'config.yml' is findable.
        # If packaged with Briefcase, path might need to be self.paths.app / 'config.yml'
        # For now, direct path, assuming CWD or Python path allows finding it.
        # If purse/config.yml, then path should be relative to main.py location.
        # Assuming main.py is in purse/src/purse/, then config.yml is ../../config.yml
        # This needs to be robust for packaged app. For now, relative to expected execution.
        # Let's assume config.yml is in the same directory as the main module or easily found.
        # For Briefcase, resources are often in `self.paths.app`.
        # A common pattern: if `self.paths.app / 'config.yml'` doesn't exist, copy from template.
        # For now, let's assume it's at a location findable by a simple path.
        # If `main.py` is in `src/purse`, then `config.yml` at project root is `Path(__file__).parent.parent.parent / 'config.yml'`
        
        # For simplicity, assume config.yml is in the expected location relative to where the app is run
        # or that PYTHONPATH is set up. If running `python -m purse` from project root,
        # `config.yml` should be found. If running from `src/purse`, then `../../config.yml`.
        # Briefcase places resources under `self.paths.app`.
        # Let's use a path relative to this file for development, assuming standard project structure.
        # `main.py` is in `src/purse/`. `config.yml` is in `purse/` at project root.
        # So, path from `src/purse/main.py` to `config.yml` is `../../../config.yml` (if project root is `purse`)
        # Or, if project root is parent of `purse`, then `../../config.yml`.
        # The subtask assumes 'config.yml'. This implies it's in the CWD or Python path.
        # To make it more robust for typical execution from project root (`python -m purse`):
        config_file_path = Path("config.yml") # Assumes in CWD (e.g. project root)
        if not config_file_path.exists():
            # Fallback for when running from src/purse or if structure is different
            # This is heuristic. A proper app would use appdirs or defined resource paths.
            alt_path1 = Path(__file__).parent.parent.parent / "config.yml" # if project root is parent of "purse" dir
            alt_path2 = Path(__file__).parent.parent / "config.yml" # if main.py is in "purse/src" and config.yml in "purse"
            if alt_path1.exists(): config_file_path = alt_path1
            elif alt_path2.exists(): config_file_path = alt_path2
            # If still not found, ConfigManager will raise FileNotFoundError.

        self.config_manager = ConfigManager(base_config_path=config_file_path)

        # 1. Setup Logging (MUST be early, uses ConfigManager for settings)
        # logger_setup needs logs_base_path from FileSystemManager. fs_manager needs config_manager.
        # Temporary FSM for logger path, or logger_setup handles relative path initially.
        # Workplan for logger_setup: "logs_base_path: Optional[Path] = None".
        # If None, logs_dir from config is relative to CWD or absolute.
        # This is acceptable for now. A more robust setup might pass fs_manager.logs_dir later
        # or have fs_manager created before logger if logger path is critical to be app_data_dir.
        # For now, following sequence from subtask.
        self.logs_dir_path = setup_logging(self.config_manager) # Returns actual logs_dir_path used
        logger.info(f"PURSE APP: {constants.APP_NAME} (v0.1.0) starting up...") # Example version
        logger.info(f"Logging to: {self.logs_dir_path}")


        # 2. Initialize AppState
        self.app_state = AppState()
        logger.info("AppState initialized.")

        # 3. Initialize Core Services (order matters for dependencies)
        self.http_client = HttpClient(self.config_manager)
        logger.info("HttpClient initialized.")
        
        # FileSystemManager needs toga_app (self) for platform-specific paths (like app_data_dir)
        self.fs_manager = FileSystemManager(self.config_manager, toga_app=self)
        logger.info(f"FileSystemManager initialized. App data dir: {self.fs_manager.app_data_dir}")

        # --- Load settings after core services that might provide paths or need early config ---
        self._load_device_specific_settings() # Loads local, non-synced settings
        self._attempt_load_synced_settings()  # Loads synced settings.yml if configured

        # --- Initialize remaining services that might depend on fully configured ConfigManager/AppState ---
        self.content_parser = ContentParserService(self.http_client, self.config_manager)
        logger.info("ContentParserService initialized.")
        
        self.search_manager = SearchManager(self.fs_manager) # Needs fs_manager for index path
        logger.info("SearchManager initialized.")
        
        self.tts_service = TTSService()
        logger.info("TTSService initialized.")
        
        # NotificationService needs fs_manager to load/save seen notification IDs
        self.notification_service = NotificationService(
            self.config_manager, self.http_client, self.fs_manager, toga_app=self
        )
        logger.info("NotificationService initialized.")

        # Cloud Service and Sync Manager (conditionally initialized based on settings)
        self.cloud_service: Optional[BaseCloudService] = None
        self.sync_manager: Optional[SyncManager] = None
        self._initialize_cloud_and_sync() # Sets up self.cloud_service and self.sync_manager

        self.pocket_importer = PocketImporterService(
            self.config_manager, self.content_parser, self.fs_manager, self.search_manager
        )
        logger.info("PocketImporterService initialized.")
        
        # --- Load initial data ---
        self.load_initial_articles_and_tags()

        # 4. Create Main Window and UI
        self.main_window = toga.MainWindow(title=self.formal_name) # self.formal_name from toga.App
        
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=10))
        main_box.add(toga.Label(
            f"Welcome to {constants.APP_NAME}! UI is under construction.", 
            style=Pack(text_align=CENTER, padding_bottom=10))
        )
        
        # Status label for messages
        self.status_label = toga.Label("Status: Initialized.", style=Pack(padding_top=5))
        self.app_state.status_label_widget = self.status_label # Store in app_state for global access
        main_box.add(self.status_label)
        
        # Example button (TODO: Move to UI modules and use commands.py)
        # test_button = toga.Button("Test Notification", on_press=self.test_notification_action)
        # main_box.add(test_button)

        self.main_window.content = main_box
        self.main_window.show()
        logger.info("Main window shown.")

        # 5. Initial background tasks (optional for this step, but good practice)
        # self.add_background_task(self.initial_background_tasks)

    # def test_notification_action(self, widget):
    #     logger.info("Test button pressed.")
    #     if self.notification_service:
    #         self.notification_service.show_system_notification("Test", "This is a test system notification.")
    #     if self.app_state.status_label_widget:
    #         self.app_state.status_label_widget.text = "Test notification shown!"


    # async def initial_background_tasks(self, app, **kwargs):
    #     logger.info("Running initial background tasks...")
    #     # Example: Fetch developer notifications
    #     if self.notification_service:
    #         dev_notifications = await self.notification_service.fetch_developer_notifications()
    #         if dev_notifications:
    #             # Process/display them (e.g., show the latest one if unread)
    #             logger.info(f"Fetched {len(dev_notifications)} new developer notifications.")
    #             # self.notification_service.show_system_notification("Developer Notice", dev_notifications[0].title)

    #     # Example: Trigger initial sync if configured
    #     if self.sync_manager:
    #         logger.info("Attempting initial background sync...")
    #         await self.sync_manager.synchronize_articles()
    #     logger.info("Initial background tasks complete.")


    async def trigger_pocket_import(self, export_html_filepath: Path) -> None: # Added as per workplan
        """
        Triggers the import of articles from a Pocket export HTML file.
        Processes each article by fetching thumbnails, saving, and indexing.
        """
        if not self.pocket_importer or not self.fs_manager or not self.search_manager:
            logger.error("Cannot start Pocket import, core services (PocketImporter, FileSystemManager, or SearchManager) not initialized.")
            if self.app_state.status_label_widget:
                self.app_state.status_label_widget.text = "Error: Import services not ready."
            return

        logger.info(f"Starting Pocket import from: {export_html_filepath}")
        if self.app_state.status_label_widget:
            self.app_state.status_label_widget.text = f"Starting Pocket import from {export_html_filepath.name}..."

        successful_imports = 0
        failed_or_skipped_articles = 0 # Renamed for clarity, counts articles that were yielded but failed to save, or were skipped by importer.

        # Placeholder for a UI progress callback
        # def ui_progress_callback(current, total):
        #    if self.app_state.status_label_widget:
        #        self.app_state.status_label_widget.text = f"Importing Pocket: {current}/{total}"
        #    logger.debug(f"Pocket import progress: {current}/{total}")

        try:
            # The pocket_importer.import_from_pocket_file is now an async generator
            async for article_from_importer in self.pocket_importer.import_from_pocket_file(
                export_html_filepath, 
                # progress_callback=ui_progress_callback # Pass UI callback if implemented
            ):
                try:
                    logger.debug(f"Processing yielded article from Pocket: '{article_from_importer.title}'")
                    # 1. Fetch and store thumbnail (if potential URL exists)
                    await self._fetch_and_store_article_thumbnail(article_from_importer)

                    # 2. Save article to file system
                    saved_path = self.fs_manager.save_article(article_from_importer)
                    
                    if saved_path:
                        logger.info(f"Pocket import: Article '{article_from_importer.title}' saved to {saved_path}")
                        # 3. Add/Update article in search index
                        self.search_manager.add_or_update_article(article_from_importer)
                        successful_imports += 1
                        
                        # 4. Update AppState and UI (placeholders)
                        # self.app_state.current_article_list.insert(0, article_from_importer) # Add to top
                        # self.app_state.all_tags_in_library.update(article_from_importer.tags or [])
                        # self.refresh_ui_article_list() # Placeholder for UI update method
                        logger.debug(f"Pocket import: Successfully processed and saved '{article_from_importer.title}'.")
                    else:
                        failed_or_skipped_articles += 1
                        logger.warning(f"Pocket import: Failed to save article '{article_from_importer.title}'.")
                except Exception as e_article: # Catch errors during processing of a single article
                    failed_or_skipped_articles += 1
                    logger.error(f"Pocket import: Error processing article '{article_from_importer.title if article_from_importer else 'unknown'}': {e_article}", exc_info=True)

            logger.info(f"Pocket import finished. Successfully imported: {successful_imports} articles. Failed/Skipped articles: {failed_or_skipped_articles}.")
            if self.app_state.status_label_widget:
                self.app_state.status_label_widget.text = f"Pocket import complete. Imported: {successful_imports}, Failed/Skipped: {failed_or_skipped_articles}."
            # self.refresh_ui_article_list() # Placeholder: Refresh UI after all imports

        except Exception as e_import_process: # Catch errors in the import_from_pocket_file generator itself or setup
            logger.error(f"Error during Pocket import process: {e_import_process}", exc_info=True)
            if self.app_state.status_label_widget:
                self.app_state.status_label_widget.text = "Pocket import failed critically."

    async def process_new_url_submission(self, url_to_add: str) -> None: # Added as per workplan (Phase 1, Section 2.2)
        """
        Processes a new URL submitted by the user, including parsing, thumbnailing, saving, and indexing.
        """
        if not self.content_parser or not self.fs_manager or not self.search_manager:
            logger.error("Cannot process new URL, core services (ContentParser, FileSystemManager, or SearchManager) not initialized.")
            if self.app_state.status_label_widget: # Update UI
                self.app_state.status_label_widget.text = "Error: Services not ready for URL processing."
            # Potentially show a more user-facing error dialog
            return

        logger.info(f"Processing new URL submission: {url_to_add}")
        if self.app_state.status_label_widget: # Update UI
            self.app_state.status_label_widget.text = f"Processing URL: {url_to_add}..."

        parsed_article: Optional['Article'] = None # Ensure it's defined for logging in case of parsing error
        try:
            parsed_article = await self.content_parser.parse_url(url_to_add)

            if parsed_article:
                # 1. Fetch and store thumbnail (if potential URL exists)
                # This modifies parsed_article in place (sets thumbnail_url_local)
                logger.debug(f"Fetching thumbnail for new URL submission: {parsed_article.title}")
                await self._fetch_and_store_article_thumbnail(parsed_article)

                # 2. Save article to file system (now includes local thumbnail path in YAML)
                logger.debug(f"Saving article from new URL submission: {parsed_article.title}")
                saved_path = self.fs_manager.save_article(parsed_article)
                
                if saved_path:
                    logger.info(f"New article '{parsed_article.title}' (from URL {url_to_add}) saved to {saved_path}")
                    
                    # 3. Add/Update article in search index
                    logger.debug(f"Indexing new article: {parsed_article.title}")
                    self.search_manager.add_or_update_article(parsed_article)
                    
                    # 4. Update AppState and UI (placeholders)
                    # self.app_state.current_article_list.insert(0, parsed_article) # Add to top
                    # self.app_state.all_tags_in_library.update(parsed_article.tags or [])
                    # self.refresh_ui_article_list() # Placeholder for UI update method
                    logger.info(f"Successfully added and indexed: {parsed_article.title}")
                    if self.app_state.status_label_widget: # Update UI
                        self.app_state.status_label_widget.text = f"Article added: {parsed_article.title}"
                else:
                    logger.error(f"Failed to save newly parsed article: {parsed_article.title} from URL {url_to_add}")
                    if self.app_state.status_label_widget: # Update UI
                        self.app_state.status_label_widget.text = f"Error saving: {parsed_article.title}"
                    # Potentially show a user-facing error dialog
            else:
                logger.error(f"Failed to parse URL: {url_to_add} (ContentParserService returned None)")
                if self.app_state.status_label_widget: # Update UI
                    self.app_state.status_label_widget.text = f"Error parsing URL: {url_to_add}"
                # Potentially show a user-facing error dialog
        
        except Exception as e: # Catch any other unexpected errors during the process
            title_for_log = parsed_article.title if parsed_article else "Unknown article"
            logger.error(f"Unexpected error processing URL '{url_to_add}' for article '{title_for_log}': {e}", exc_info=True)
            if self.app_state.status_label_widget: # Update UI
                self.app_state.status_label_widget.text = "An unexpected error occurred while adding URL."
            # Potentially show a user-facing error dialog

    async def _fetch_and_store_article_thumbnail(self, article: 'Article') -> None:
        """
        Fetches a potential thumbnail image for the article and stores it locally.
        Updates article.thumbnail_url_local if successful.
        Clears article.potential_thumbnail_source_url after attempting.
        """
        if not article.potential_thumbnail_source_url:
            logger.debug(f"No potential thumbnail URL for article '{article.title}'. Skipping thumbnail fetch.")
            return

        if not self.http_client or not self.fs_manager:
            logger.error("HttpClient or FileSystemManager not available. Cannot fetch thumbnail.")
            # Clear the transient URL even if services are missing, as we can't process it.
            article.potential_thumbnail_source_url = None
            return
        
        # FileSystemManager.get_thumbnail_path uses article.local_path.
        # If article.local_path is not set yet (e.g., new article not yet saved),
        # fs_manager.get_thumbnail_path and fs_manager.save_thumbnail need to handle this.
        # The current fs_manager.get_thumbnail_path can derive a prospective path.
        # This is generally okay as fs_manager.save_thumbnail will use this path.

        logger.info(f"Attempting to fetch thumbnail for '{article.title}' from: {article.potential_thumbnail_source_url}")
        try:
            # Fetch image (ensure HttpClient's get_url with is_html_content=False to bypass HTML size limits)
            image_response = await self.http_client.get_url(
                article.potential_thumbnail_source_url, 
                is_html_content=False # This is an image, not an HTML page
            )
            image_bytes = image_response.content # Get bytes from response

            # Optional validation/resizing (not in scope for this iteration per workplan)
            # if image_bytes:
            #     from PIL import Image
            #     from io import BytesIO
            #     try:
            #         img = Image.open(BytesIO(image_bytes))
            #         # img.thumbnail((THUMBNAIL_MAX_WIDTH, THUMBNAIL_MAX_HEIGHT))
            #         # output_buffer = BytesIO()
            #         # img.save(output_buffer, format="JPEG", quality=85)
            #         # image_bytes = output_buffer.getvalue()
            #     except Exception as img_e:
            #         logger.warning(f"Could not process image for thumbnail: {img_e}")
            #         image_bytes = None # Do not save if processing failed

            if image_bytes:
                # save_thumbnail now directly updates article.thumbnail_url_local
                # and returns the relative path, or None if save failed.
                relative_thumb_path = self.fs_manager.save_thumbnail(article, image_bytes)
                if relative_thumb_path:
                    logger.info(f"Thumbnail saved for article '{article.title}' at relative path: {relative_thumb_path}")
                    # article.thumbnail_url_local is updated by fs_manager.save_thumbnail
                else:
                    logger.warning(f"Failed to save thumbnail for article '{article.title}' (FileSystemManager.save_thumbnail returned None).")
            else:
                logger.warning(f"No image bytes obtained for thumbnail of article '{article.title}'.")

        except Exception as e:
            logger.error(f"Error fetching or saving thumbnail for article '{article.title}' from '{article.potential_thumbnail_source_url}': {e}", exc_info=True)
        finally:
            # Always clear the transient URL after attempting to fetch, regardless of success.
            article.potential_thumbnail_source_url = None

    def _load_device_specific_settings(self) -> None:
        """Loads device-specific settings (e.g., seen notifications, window state)."""
        logger.debug("Loading device-specific settings...")
        device_settings = self.fs_manager.load_device_settings()
        if not device_settings:
            logger.debug("No device-specific settings found or file was empty/invalid.")
            return

        # Load seen notification IDs into NotificationService
        seen_ids_list = device_settings.get('seen_notification_ids', [])
        if isinstance(seen_ids_list, list):
            self.notification_service.seen_notification_ids = set(seen_ids_list)
            logger.debug(f"Loaded {len(seen_ids_list)} seen notification IDs.")
        else:
            logger.warning("Malformed 'seen_notification_ids' in device settings; expected list.")

        # Example: Load window size/position (Toga might handle this automatically or require specific API)
        # self.main_window.size = tuple(device_settings.get('main_window_size', (640, 480)))
        # self.main_window.position = tuple(device_settings.get('main_window_position', (100, 100)))
        
        # Load local_sync_root if stored in device_settings (might be an alternative to config.yml for this)
        # This provides a way for the app to "remember" the sync root across sessions without it being in settings.yml
        # The workplan says _attempt_load_synced_settings checks config_manager for 'user_preferences.local_sync_root'
        # This key could be initially set from a first-run setup and saved in settings.yml,
        # or potentially stored in device_settings.yml if it's considered device-specific.
        # For now, assume it's primarily managed via settings.yml as per workplan.
        
        logger.info("Device-specific settings applied.")


    def _attempt_load_synced_settings(self) -> None:
        """
        Attempts to load settings.yml from the local sync root.
        The local_sync_root path itself is expected to be in config (could be from a previous run's settings.yml).
        """
        logger.debug("Attempting to load synced settings (settings.yml)...")
        # Key for local_sync_root might be 'user_preferences.local_sync_root' or similar from config.yml/settings.yml itself.
        # This implies settings.yml might contain the path to itself, or config.yml (base) does.
        # Let's assume 'cloud.local_sync_root_path' is a key in config.yml or settings.yml.
        local_sync_root_str = self.config_manager.get('cloud.local_sync_root_path')

        if local_sync_root_str:
            logger.info(f"Local sync root configured at: {local_sync_root_str}")
            self.fs_manager.set_local_sync_root(local_sync_root_str) # Inform FileSystemManager
            
            synced_settings_path = self.fs_manager.get_synced_settings_path()
            if synced_settings_path and synced_settings_path.exists():
                self.config_manager.load_settings(synced_settings_path) # Load settings.yml into ConfigManager
                logger.info(f"Successfully loaded synced settings from {synced_settings_path}.")
                self._update_app_state_from_synced_settings()
            else:
                logger.info("Synced settings file (settings.yml) not found at configured path. Using defaults or base config.")
        else:
            logger.info("Local sync root path not configured. Synced settings (settings.yml) not loaded.")


    def _update_app_state_from_synced_settings(self) -> None:
        """Updates AppState and relevant services based on newly loaded synced settings via ConfigManager."""
        logger.debug("Updating AppState from (potentially new) synced settings...")
        
        # Update reading preferences in AppState
        self.app_state.reading_prefs.font_family = self.config_manager.get(
            'ui.reading_view.font_family', constants.DEFAULT_FONT_FAMILY
        )
        self.app_state.reading_prefs.font_size = self.config_manager.get(
            'ui.reading_view.font_size', constants.DEFAULT_FONT_SIZE
        )
        self.app_state.reading_prefs.theme = self.config_manager.get(
            'ui.reading_view.theme', constants.DEFAULT_THEME
        )
        
        # Update developer notification URL in AppState and NotificationService
        # User can override the default from config.yml via settings.yml
        dev_notif_url_override = self.config_manager.get('developer_notifications_url_override')
        if dev_notif_url_override:
            self.app_state.developer_notification_url = dev_notif_url_override
            self.notification_service.developer_notifications_url = dev_notif_url_override
            logger.info(f"Developer notification URL updated from settings.yml: {dev_notif_url_override}")
        elif self.notification_service.developer_notifications_url is None : # If not set by override and was None from config.yml
             # Fallback to default from config.yml if it was missing there initially but NotificationService needs one
             default_dev_url_from_config = self.config_manager.get('developer_notifications_url')
             if default_dev_url_from_config:
                self.app_state.developer_notification_url = default_dev_url_from_config
                self.notification_service.developer_notifications_url = default_dev_url_from_config
                logger.info(f"Developer notification URL set from config.yml default: {default_dev_url_from_config}")


        # Update cloud provider name in AppState
        self.app_state.cloud_provider_name = self.config_manager.get('cloud.provider_name')
        if self.app_state.cloud_provider_name:
            logger.info(f"Cloud provider from settings: {self.app_state.cloud_provider_name}")

        # Other synced settings can be applied here to AppState or services.
        logger.info("AppState updated based on synced settings.")


    def _initialize_cloud_and_sync(self) -> None:
        """Initializes the configured cloud service and SyncManager."""
        logger.debug("Initializing cloud service and SyncManager...")
        provider_name = self.config_manager.get('cloud.provider_name')
        
        # Cloud service constructors will now load their own tokens/cache from keyring via BaseCloudService logic.
        # No need to fetch individual token parts here anymore.

        user_cloud_root_path = self.config_manager.get('cloud.user_root_folder_path', '/Apps/Purse') # Default if not in settings

        if provider_name:
            logger.info(f"Configured cloud provider: {provider_name}. Initializing client...")
            if provider_name == DropboxService.PROVIDER_NAME:
                self.cloud_service = DropboxService(self.config_manager)
            elif provider_name == GoogleDriveService.PROVIDER_NAME:
                self.cloud_service = GoogleDriveService(self.config_manager)
            elif provider_name == OneDriveService.PROVIDER_NAME:
                self.cloud_service = OneDriveService(self.config_manager)
            else:
                logger.error(f"Unsupported cloud provider configured: '{provider_name}'. Sync will be disabled.")
                self.app_state.cloud_provider_name = f"Unsupported: {provider_name}"
                return

            if self.cloud_service:
                self.cloud_service.set_root_folder_path(user_cloud_root_path)
                self.sync_manager = SyncManager(
                    self.config_manager, self.fs_manager, self.cloud_service, self.search_manager
                )
                logger.info(f"{provider_name} service and SyncManager initialized. App root: {user_cloud_root_path}")
                self.app_state.cloud_provider_name = provider_name # Update AppState
            else: # Should not happen if provider_name matched one of the above
                 logger.error(f"Failed to instantiate cloud service for {provider_name}.")
        else:
            logger.info("No cloud provider configured in settings. Sync functionality will be disabled.")
            self.app_state.cloud_provider_name = None


    def load_initial_articles_and_tags(self) -> None:
        """Loads all articles from the local sync root (if configured) and populates AppState."""
        logger.info("Loading initial articles and tags from local file system...")
        sync_root = self.fs_manager.get_local_sync_root()
        if not sync_root:
            logger.warning("Cannot load initial articles: Local sync root not configured.")
            self.app_state.current_article_list = []
            self.app_state.all_tags_in_library = set()
            return

        all_articles: List[Article] = []
        all_tags: Set[str] = set()
        
        try:
            article_paths = self.fs_manager.get_all_article_filepaths() # List of Path objects
            logger.debug(f"Found {len(article_paths)} potential article files in sync root.")

            for fpath in article_paths:
                article = self.fs_manager.load_article(fpath) # Returns Optional[Article]
                if article:
                    all_articles.append(article)
                    if article.tags: # article.tags is List[str]
                        all_tags.update(article.tags)
                else:
                    logger.warning(f"Could not load article from path: {fpath}")
            
            # Default sort: by saved_date, descending (newest first)
            self.app_state.current_article_list = sorted(all_articles, key=lambda a: a.saved_date, reverse=True)
            self.app_state.all_tags_in_library = all_tags
            logger.info(f"Loaded {len(all_articles)} articles and {len(all_tags)} unique tags from local storage.")

            # Search index consistency:
            # The workplan mentions: "Consider if SearchManager.rebuild_index is needed here or managed differently".
            # For now, assume index is updated per change (save, delete) or by sync operations.
            # A full rebuild on startup can be slow for large libraries.
            # A check for consistency or a user-triggered rebuild option might be better.
            # Example: if self.search_manager and len(all_articles) > 0:
            #    logger.info("Consider verifying/rebuilding search index if needed...")
            #    # self.add_background_task(self.search_manager.rebuild_index, articles=all_articles)
            
        except Exception as e:
            logger.error(f"Error during initial article load: {e}", exc_info=True)
            self.app_state.current_article_list = []
            self.app_state.all_tags_in_library = set()


    async def on_exit(self) -> bool:
        """Handler for application exit."""
        logger.info(f"PURSE APP: {constants.APP_NAME} shutting down...")
        
        if self.http_client:
            await self.http_client.close()
            logger.debug("HttpClient closed.")
        
        # Save device-specific settings
        if self.fs_manager and self.notification_service:
            logger.debug("Saving device-specific settings...")
            device_settings_to_save = self.fs_manager.load_device_settings() # Load current to preserve other settings
            device_settings_to_save['seen_notification_ids'] = list(self.notification_service.seen_notification_ids)
            # Add other settings to save, e.g., window size/pos if not Toga-managed
            # device_settings_to_save['main_window_size'] = self.main_window.size
            # device_settings_to_save['main_window_position'] = self.main_window.position
            self.fs_manager.save_device_settings(device_settings_to_save)
            logger.debug("Device-specific settings saved.")

        if self.tts_service: # TTSService has its own shutdown
            await self.tts_service.shutdown() # Stops speech, waits for task
            logger.debug("TTSService shutdown.")
            
        if self.search_manager: # Whoosh index might need explicit closing
            self.search_manager.close_index() # Added this in SearchManager (Turn 19)
            logger.debug("SearchManager index closed.")

        logger.info(f"{constants.APP_NAME} shutdown complete.")
        return True # True to allow exit, False to prevent (if applicable)


def main():
    """Main function to create and run the Toga application."""
    # Icon path needs to be relative to the app's resource directory.
    # Briefcase usually handles packaging resources.
    # `icon='resources/purse_icon'` implies `resources/purse_icon.png` or `.icns` etc.
    # Toga looks for this in platform-specific ways, often within the app bundle.
    # For development, it might be relative to `self.paths.app`.
    # If `app_name="purse"`, Toga might look in `src/purse/resources/`.
    
    # Determine icon path carefully. For now, use the string as specified.
    # A more robust way for dev: Path(__file__).parent.parent / 'resources' / 'purse_icon'
    # But Toga's resource handling is specific.
    
    return PurseApp(
        formal_name=constants.APP_NAME,
        app_id=constants.APP_ID,
        app_name="purse", # Used by Toga for resource paths, e.g., src/purse/resources/
        author=constants.APP_AUTHOR,
        description="A self-hosted, open-source 'read-it-later' application.", # From pyproject.toml
        icon='resources/purse_icon', 
        # home_page='https://github.com/cspenn/purse' # Optional
    )

if __name__ == '__main__':
    # This starts the Toga application event loop.
    main().main_loop()
