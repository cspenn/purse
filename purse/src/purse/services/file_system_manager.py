import os
import shutil # shutil might be needed for more complex operations like rmtree, but not for this spec
from pathlib import Path
import logging
import yaml # For device settings
from typing import Optional, List, Union, Dict, TYPE_CHECKING

from purse.models.article import Article
from purse.services.markdown_handler import MarkdownHandler
from purse.utils import common # For sanitize_filename

if TYPE_CHECKING:
    from purse.config_manager import ConfigManager
    # It's good practice to guard Toga import for non-GUI environments or tests,
    # though for type checking it's fine.
    try:
        from toga import App
    except ImportError:
        App = None # type: ignore # Define App as None if Toga is not available

logger = logging.getLogger(__name__)

class FileSystemManager:
    def __init__(self, config_manager: 'ConfigManager', toga_app: Optional['App'] = None):
        self.config_manager = config_manager
        self.toga_app = toga_app

        # --- Base data directory for Purse application (OS-idiomatic) ---
        if self.toga_app and hasattr(self.toga_app, 'paths') and self.toga_app.paths and hasattr(self.toga_app.paths, 'data'):
            self.app_data_dir: Path = Path(self.toga_app.paths.data)
        else:
            self.app_data_dir: Path = Path.home() / ".Purse" # Fallback
            if self.toga_app is None: # Only log warning if toga_app was expected but not provided for a GUI app run
                 logger.warning(
                    f"🟡 Toga app instance not provided or 'paths.data' not available. "
                    f"Using fallback app_data_dir: {self.app_data_dir}. "
                    f"This is normal for tests, but not for a production GUI app run."
                )
        try:
            self.app_data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"🛑 CRITICAL: Could not create or access app_data_dir at {self.app_data_dir}: {e}. "
                         "Application might not function correctly.")
            # Depending on how critical this is, could raise an exception.

        self._local_sync_root: Optional[Path] = None # Set after user configures cloud sync via set_local_sync_root

        # --- Path for Whoosh index (within app_data_dir) ---
        # config 'paths.local_search_index_dir' from workplan 5 was changed to 'paths.local_search_index_dir_fragment' in config.yml (Turn 5)
        search_index_fragment = self.config_manager.get('paths.local_search_index_dir_fragment', 'search_index')
        self.search_index_dir: Path = self.app_data_dir / search_index_fragment
        self.search_index_dir.mkdir(parents=True, exist_ok=True)

        # --- Logs directory (within app_data_dir) ---
        # config 'logging.logs_dir' is a path fragment e.g. "logs"
        logs_dir_fragment = self.config_manager.get('logging.logs_dir', 'logs')
        self.logs_dir: Path = self.app_data_dir / logs_dir_fragment
        # logger_setup.py might also create this. mkdir(exist_ok=True) is safe.
        self.logs_dir.mkdir(parents=True, exist_ok=True) 

        # --- Local, non-synced device settings (e.g., window size) ---
        self.local_device_settings_path: Path = self.app_data_dir / "device_settings.yml"

        # --- Synced settings path (names stored, full path depends on _local_sync_root) ---
        self.synced_config_dir_name: str = self.config_manager.get('paths.synced_config_dir_name', '.purse_config')
        self.synced_settings_filename: str = self.config_manager.get('paths.synced_settings_filename', 'settings.yml')

    def set_local_sync_root(self, path: Union[str, Path]) -> None:
        """Sets the root directory for the local copy of synced articles."""
        self._local_sync_root = Path(path).resolve() # Resolve to make it absolute
        try:
            self._local_sync_root.mkdir(parents=True, exist_ok=True)
            logger.info(f"🟢 Local sync root set to: {self._local_sync_root}")
        except OSError as e:
            logger.error(f"🛑 Could not create local_sync_root at {self._local_sync_root}: {e}")
            # Potentially unset or handle error appropriately
            self._local_sync_root = None 


    def get_local_sync_root(self) -> Optional[Path]:
        if not self._local_sync_root:
            logger.warning("🟡 Local sync root not yet configured.")
        return self._local_sync_root
    
    def get_synced_settings_path(self) -> Optional[Path]:
        """Path to settings.yml within the sync root."""
        root = self.get_local_sync_root()
        if not root: 
            # logger.warning("🟡 Cannot get synced_settings_path, local_sync_root is not set.") # Can be noisy
            return None
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

        sanitized_title = common.sanitize_filename(article.title if article.title else "Untitled")
        # Use first part of UUID for uniqueness but keep it shorter, as per workplan
        short_id = article.id.split('-')[0]
        filename = f"{sanitized_title}_{short_id}.md"
        
        article_path = sync_root / filename

        if ensure_exists:
            try:
                article_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"🛑 Could not create parent directory for article path {article_path}: {e}")
                return None # Cannot ensure existence, so cannot proceed
        return article_path

    def save_article(self, article: Article) -> Optional[Path]:
        """Saves an article to the local sync folder."""
        filepath = self.get_article_filepath(article, ensure_exists=True)
        if not filepath: 
            logger.error(f"🛑 Could not determine filepath for article '{article.title}'. Save failed.")
            return None

        if MarkdownHandler.save_article_to_file(article, filepath):
            # article.local_path is updated by MarkdownHandler.save_article_to_file
            return filepath
        return None

    def load_article(self, filepath: Path) -> Optional[Article]:
        """Loads an article from a given filepath."""
        article = MarkdownHandler.parse_markdown_file(filepath)
        if article:
            article.local_path = str(filepath.resolve()) # Ensure it's an absolute path
        return article

    def delete_article_file(self, article_or_filepath: Union[Article, Path]) -> bool:
        """Deletes the markdown file for an article."""
        filepath_to_delete: Optional[Path] = None

        if isinstance(article_or_filepath, Article):
            article = article_or_filepath
            if article.local_path:
                filepath_to_delete = Path(article.local_path)
            else:
                # Try to construct it if not set (e.g. article object was created but not saved/loaded yet)
                logger.warning(f"Article '{article.title}' (ID: {article.id}) has no local_path. Attempting to derive path for deletion.")
                derived_path = self.get_article_filepath(article)
                if derived_path:
                    filepath_to_delete = derived_path
                else:
                    logger.error(f"🛑 Cannot delete article '{article.title}', local path unknown and could not be derived.")
                    return False
        else: # It's a Path object
            filepath_to_delete = Path(article_or_filepath)

        if filepath_to_delete and filepath_to_delete.exists():
            try:
                filepath_to_delete.unlink()
                logger.info(f"🟢 Deleted article file: {filepath_to_delete}")
                if isinstance(article_or_filepath, Article): # Clear local_path if it was an Article obj
                    article_or_filepath.local_path = None
                return True
            except Exception as e:
                logger.error(f"🛑 Error deleting article file {filepath_to_delete}: {e}")
                return False
        elif filepath_to_delete:
            logger.warning(f"🟡 Article file not found for deletion (already deleted?): {filepath_to_delete}")
            return True # File not there, so deletion is effectively successful / state is as desired
        else: # Should not happen if logic above is correct
            logger.error("🛑 Could not determine file path for deletion.")
            return False


    def get_all_article_filepaths(self) -> List[Path]:
        """Returns a list of all .md file paths in the local sync root (non-recursive)."""
        sync_root = self.get_local_sync_root()
        if not sync_root: 
            logger.warning("🟡 Cannot get all article filepaths, sync root not set.")
            return []
        
        # Assuming flat structure for now, as per workplan.
        # If recursive search is needed later: sync_root.rglob("*.md")
        return list(sync_root.glob("*.md"))

    # --- Thumbnail Management (PRD 5.3) ---
    def get_thumbnail_path(self, article: Article, create_subdirs: bool = True) -> Optional[Path]:
        """
        Generates a path for a thumbnail image, relative to the article's .md file.
        Example: <article_md_path_stem>_thumb.jpg
        """
        article_md_path_str = article.local_path
        if not article_md_path_str:
            # If article not saved yet, try to get prospective path to determine where thumbnail would go
            temp_article_md_path = self.get_article_filepath(article)
            if not temp_article_md_path:
                logger.warning(f"🟡 Cannot determine thumbnail path for unsaved article: {article.title} (ID: {article.id})")
                return None
            article_md_path = temp_article_md_path
        else:
            article_md_path = Path(article_md_path_str)

        # Filename: article_stem + "_thumb.jpg" (assuming JPEG for thumbnails)
        thumb_filename = f"{article_md_path.stem}_thumb.jpg"
        # Thumbnails are stored alongside the .md file.
        thumb_path = article_md_path.parent / thumb_filename

        # create_subdirs is not really applicable here as it's in the same dir as article.
        # The parent dir is created by get_article_filepath(ensure_exists=True) when saving article.
        # If saving thumbnail for an article whose file doesn't exist yet, this might be an issue.
        # However, get_article_filepath above is called with ensure_exists=False by default.
        # Let's ensure parent dir for thumbnail exists if create_subdirs is True.
        if create_subdirs: # This will typically be the sync_root itself.
            try:
                thumb_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"🛑 Could not create parent directory for thumbnail path {thumb_path}: {e}")
                return None
        return thumb_path

    def save_thumbnail(self, article: Article, image_bytes: bytes) -> Optional[str]:
        """Saves thumbnail image_bytes and updates article.thumbnail_url_local with relative path."""
        thumb_abs_path = self.get_thumbnail_path(article, create_subdirs=True) # Ensure parent dir exists
        if not thumb_abs_path:
            logger.error(f"🛑 Could not get thumbnail path for article '{article.title}'. Thumbnail not saved.")
            return None
        
        sync_root = self.get_local_sync_root()
        if not sync_root:
            logger.error("🛑 Cannot save thumbnail, sync root not set. Thumbnail path would be ambiguous.")
            return None

        try:
            with open(thumb_abs_path, 'wb') as f:
                f.write(image_bytes)
            
            # Store path relative to the sync root for portability in YAML.
            relative_thumb_path_str = str(thumb_abs_path.relative_to(sync_root))
            article.thumbnail_url_local = relative_thumb_path_str
            logger.info(f"🟢 Thumbnail saved for '{article.title}' at {thumb_abs_path} (relative: {relative_thumb_path_str})")
            return relative_thumb_path_str
        except Exception as e:
            logger.error(f"🛑 Error saving thumbnail for '{article.title}' to {thumb_abs_path}: {e}")
            return None

    def get_thumbnail_bytes(self, article: Article) -> Optional[bytes]:
        """Loads thumbnail image bytes from path stored in article.thumbnail_url_local (relative to sync_root)."""
        sync_root = self.get_local_sync_root()
        if not sync_root:
            logger.warning("🟡 Cannot get thumbnail bytes, sync root not set.")
            return None
        if not article.thumbnail_url_local:
            # logger.debug(f"Article '{article.title}' has no thumbnail_url_local.") # Can be noisy
            return None

        # thumbnail_url_local is relative to sync_root
        thumb_abs_path = sync_root / article.thumbnail_url_local
        if thumb_abs_path.exists() and thumb_abs_path.is_file():
            try:
                with open(thumb_abs_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"🛑 Error reading thumbnail {thumb_abs_path} for article '{article.title}': {e}")
        else:
            logger.warning(f"🟡 Thumbnail file not found at {thumb_abs_path} for article '{article.title}'.")
        return None
    
    def delete_thumbnail(self, article: Article) -> bool:
        """Deletes the thumbnail file associated with the article and clears article.thumbnail_url_local."""
        sync_root = self.get_local_sync_root()
        if not sync_root:
            logger.warning(f"🟡 Cannot delete thumbnail for '{article.title}', sync root not set.")
            return False
        if not article.thumbnail_url_local:
            logger.debug(f"Article '{article.title}' has no thumbnail to delete.")
            return True # No thumbnail to delete, so operation is "successful"

        thumb_abs_path = sync_root / article.thumbnail_url_local
        deleted_on_fs = False
        if thumb_abs_path.exists():
            try:
                thumb_abs_path.unlink()
                logger.info(f"🟢 Deleted thumbnail: {thumb_abs_path} for article '{article.title}'")
                deleted_on_fs = True
            except Exception as e:
                logger.error(f"🛑 Error deleting thumbnail file {thumb_abs_path}: {e}")
                return False # Failed to delete file, so do not clear field
        else:
            logger.warning(f"🟡 Thumbnail file not found for deletion (already deleted?): {thumb_abs_path}")
            deleted_on_fs = True # File not there, consider it deleted from FS point of view

        if deleted_on_fs:
            article.thumbnail_url_local = None # Clear from article model
        return deleted_on_fs


    # --- Local Device Settings (using YAML) ---
    def load_device_settings(self) -> Dict[str, Any]:
        """Loads and parses YAML from self.local_device_settings_path. Returns empty dict on error or if not found."""
        if self.local_device_settings_path.exists() and self.local_device_settings_path.is_file():
            try:
                with open(self.local_device_settings_path, 'r', encoding='utf-8') as f:
                    settings_data = yaml.safe_load(f)
                    if settings_data is None: # Empty file
                        return {}
                    if not isinstance(settings_data, dict):
                        logger.warning(f"🟡 Device settings file {self.local_device_settings_path} does not contain a dictionary. Ignoring.")
                        return {}
                    logger.info(f"Loaded device settings from {self.local_device_settings_path}")
                    return settings_data
            except yaml.YAMLError as e:
                logger.error(f"🛑 Error parsing YAML in device settings file {self.local_device_settings_path}: {e}")
            except Exception as e: # Other file IO errors
                logger.error(f"🛑 Error loading device settings file {self.local_device_settings_path}: {e}")
        else:
            logger.info(f"Device settings file {self.local_device_settings_path} not found. Using defaults.")
        return {} # Return empty dict if file not found, parsing error, or not a dict

    def save_device_settings(self, settings_data: Dict[str, Any]) -> None:
        """Saves settings_data to self.local_device_settings_path as YAML."""
        try:
            # Ensure parent directory exists (should be app_data_dir, created in __init__)
            self.local_device_settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.local_device_settings_path, 'w', encoding='utf-8') as f:
                yaml.dump(settings_data, f, sort_keys=False, indent=2, allow_unicode=True)
            logger.info(f"🟢 Device settings saved to {self.local_device_settings_path}")
        except Exception as e:
            logger.error(f"🛑 Error saving device settings to {self.local_device_settings_path}: {e}")

```
