import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
import time # For time.time() and UTC timestamps
from typing import Dict, Optional, List, Set, Tuple, TYPE_CHECKING, AsyncGenerator
from dataclasses import dataclass

# Assuming BaseCloudService and CloudFileMetadata are in base_cloud_service.py
from purse.services.cloud_storage.base_cloud_service import BaseCloudService, CloudFileMetadata
from purse.services.file_system_manager import FileSystemManager
from purse.services.markdown_handler import MarkdownHandler
from purse.models.article import Article
from purse.services.search_manager import SearchManager
from purse.utils import constants # For SYNC_CONFLICT_LOG_FILENAME

if TYPE_CHECKING:
    from purse.config_manager import ConfigManager

logger = logging.getLogger(__name__)

@dataclass
class LocalFileState:
    """Represents the state of a local article file for synchronization purposes."""
    path: Path  # Absolute path to the local file
    modified_timestamp: float  # UTC Unix timestamp of last modification
    article_id: Optional[str] = None # Optional: Article UUID if known (e.g. from parsing file)
                                     # Not strictly needed for path/timestamp based sync.

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
        self._sync_lock = asyncio.Lock() # Ensures only one sync operation runs at a time
        
        # Path for logging sync conflicts
        self.conflict_log_path: Path = self.fs_manager.logs_dir / constants.SYNC_CONFLICT_LOG_FILENAME
        try:
            self.conflict_log_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Could not create directory for conflict log at {self.conflict_log_path.parent}: {e}")


    def _log_conflict(self, message: str) -> None:
        """Appends a timestamped conflict message to the sync conflict log file."""
        timestamp_str = datetime.now(timezone.utc).isoformat()
        full_message = f"[{timestamp_str}] CONFLICT: {message}\n"
        logger.warning(f"SYNC {full_message.strip()}") # Also log to main logger
        try:
            with open(self.conflict_log_path, 'a', encoding='utf-8') as f:
                f.write(full_message)
        except Exception as e:
            logger.error(f"🛑 Could not write to sync conflict log '{self.conflict_log_path}': {e}")

    async def _get_local_file_states(self) -> Dict[str, LocalFileState]:
        """
        Gets states of local .md files.
        Returns a dictionary mapping path relative to sync root (str) to LocalFileState.
        """
        local_files: Dict[str, LocalFileState] = {}
        sync_root = self.fs_manager.get_local_sync_root()
        if not sync_root:
            logger.warning("Cannot get local file states: Local sync root not set.")
            return local_files

        # Non-recursive scan for .md files in the sync root, as per workplan ("for now")
        for local_path in sync_root.glob("*.md"):
            if local_path.is_file() and not local_path.name.startswith('.'): # Skip hidden files
                try:
                    relative_path_str = str(local_path.relative_to(sync_root))
                    stat_info = local_path.stat()
                    # Ensure mtime is UTC. Path.stat().st_mtime is typically naive UTC or local.
                    # For cross-platform consistency, assume it's naive UTC or convert if known.
                    # Python's time.time() is UTC. os.path.getmtime() is float seconds.
                    # For simplicity, directly use st_mtime. Cloud timestamps are UTC.
                    mtime_utc_ts = stat_info.st_mtime 
                    
                    # Article ID loading is deferred/optional as per workplan.
                    # If needed for more robust sync (content-based hash, ID matching):
                    # article_obj = MarkdownHandler.parse_markdown_file(local_path)
                    # article_id = article_obj.id if article_obj else None
                    
                    local_files[relative_path_str] = LocalFileState(
                        path=local_path, # Store absolute path for easy access
                        modified_timestamp=mtime_utc_ts,
                        # article_id=article_id 
                    )
                except Exception as e:
                    logger.error(f"🛑 Error processing local file {local_path}: {e}")
        logger.info(f"Found {len(local_files)} local .md files for sync.")
        return local_files

    async def _get_cloud_file_states(self) -> Dict[str, CloudFileMetadata]:
        """
        Gets states of cloud .md files from the app's cloud root.
        Returns a dictionary mapping path relative to app cloud root (str) to CloudFileMetadata.
        """
        cloud_files: Dict[str, CloudFileMetadata] = {}
        try:
            # list_folder with "" path lists the app's configured root folder.
            # recursive=True gets all files in subdirectories as well.
            async for cloud_meta in self.cloud_service.list_folder("", recursive=True):
                # Filter for .md files and skip hidden or folder items
                if not cloud_meta.is_folder and cloud_meta.name.endswith(".md") and \
                   not cloud_meta.name.startswith('.'):
                    # cloud_meta.path_display is already relative to the app's cloud root
                    # as per BaseCloudService.list_folder yielding it this way.
                    cloud_files[cloud_meta.path_display] = cloud_meta
        except Exception as e:
            logger.error(f"🛑 Error listing cloud files for sync: {e}", exc_info=True)
        logger.info(f"Found {len(cloud_files)} cloud .md files for sync.")
        return cloud_files


    async def synchronize_articles(self, force_full_rescan: bool = False) -> None:
        """
        Performs a two-way synchronization of articles between local filesystem and cloud storage.
        Uses "Last Write Wins" for conflict resolution.
        `force_full_rescan` is not explicitly used in current logic but could influence caching.
        """
        if not await self._sync_lock.acquire(timeout=1.0): # Try to acquire lock, timeout after 1s
            logger.warning("Sync operation already in progress. Skipping this run.")
            return
        
        logger.info("🟢 Starting article synchronization process...")
        try:
            if not self.fs_manager.get_local_sync_root():
                logger.error("🛑 Sync failed: Local sync root not configured.")
                return
            
            # Check cloud authentication and try to refresh token if needed
            # BaseCloudService.refresh_access_token updates self.access_token
            if not self.cloud_service.access_token: # If no token at all
                if not self.cloud_service.refresh_token: # And no refresh token
                    logger.error("🛑 Sync failed: Cloud service not authenticated (no access or refresh token).")
                    return
                # Try to get initial access token using refresh token
                if not await self.cloud_service.refresh_access_token():
                    logger.error("🛑 Sync failed: Could not obtain access token using refresh token.")
                    return
            # If there is an access token, _run_sync in provider specific service (e.g. DropboxService)
            # should attempt refresh if token is expired. ensure_app_root_folder_exists will test this.

            # Ensure app root folder and .purse_config directory exist in cloud
            if not await self.cloud_service.ensure_app_root_folder_exists():
                logger.error(f"🛑 Sync failed: Could not ensure application root folder '{self.cloud_service.root_folder_path}' exists in cloud.")
                return
            
            synced_config_dir_in_cloud = self.fs_manager.synced_config_dir_name # e.g., ".purse_config"
            if not await self.cloud_service.create_folder(synced_config_dir_in_cloud):
                logger.error(f"🛑 Sync failed: Could not ensure config directory '{synced_config_dir_in_cloud}' exists in cloud app root.")
                return

            logger.info("Fetching local and cloud file states...")
            local_states = await self._get_local_file_states()
            cloud_states = await self._get_cloud_file_states()
            
            timestamp_tolerance_seconds = 2.0 
            actions_taken_summary = {"uploaded": 0, "downloaded": 0, "conflicts_local_won": 0, "conflicts_cloud_won": 0, "no_action":0}

            all_relative_paths = set(local_states.keys()) | set(cloud_states.keys())

            for rel_path in sorted(list(all_relative_paths)):
                local_file_state = local_states.get(rel_path)
                cloud_file_meta = cloud_states.get(rel_path)

                # Case 1: Only local - Upload
                if local_file_state and not cloud_file_meta:
                    logger.info(f"File '{rel_path}' exists locally, not in cloud. Uploading.")
                    # cloud_target_folder is relative to app root. Path(rel_path).parent gives this.
                    # For files in sync_root, parent is "."
                    target_cloud_folder = str(Path(rel_path).parent)
                    if target_cloud_folder == ".": target_cloud_folder = "" # Root of app folder in cloud

                    upload_meta = await self.cloud_service.upload_file(
                        local_file_state.path, 
                        target_cloud_folder, 
                        Path(rel_path).name
                    )
                    if upload_meta:
                        actions_taken_summary["uploaded"] += 1
                        # Optionally, update local_file_state's timestamp from upload_meta if precise,
                        # or re-stat local file if cloud provider might adjust mtime on upload slightly.
                        # For now, assume local mtime is source of truth for "last write wins" on this path.
                    else:
                        logger.error(f"Failed to upload '{rel_path}'.")

                # Case 2: Only in cloud - Download
                elif cloud_file_meta and not local_file_state:
                    logger.info(f"File '{rel_path}' exists in cloud, not locally. Downloading.")
                    local_target_path = self.fs_manager.get_local_sync_root() / rel_path # type: ignore # sync_root checked
                    local_target_path.parent.mkdir(parents=True, exist_ok=True) # Ensure parent dir for file
                    
                    # cloud_file_meta.path_display should be the relative path for download
                    success = await self.cloud_service.download_file(cloud_file_meta.path_display, local_target_path)
                    if success:
                        actions_taken_summary["downloaded"] += 1
                        # Index the newly downloaded article
                        article_obj = MarkdownHandler.parse_markdown_file(local_target_path)
                        if article_obj:
                            self.search_manager.add_or_update_article(article_obj)
                        else:
                            logger.warning(f"Could not parse downloaded article '{local_target_path}' for indexing.")
                    else:
                        logger.error(f"Failed to download '{rel_path}'.")
                
                # Case 3: Exists in both - Conflict Resolution
                elif local_file_state and cloud_file_meta:
                    # Compare modification timestamps (UTC Unix floats)
                    local_mtime = local_file_state.modified_timestamp
                    cloud_mtime = cloud_file_meta.modified_timestamp

                    if abs(local_mtime - cloud_mtime) <= timestamp_tolerance_seconds:
                        actions_taken_summary["no_action"] += 1
                        # logger.debug(f"File '{rel_path}' timestamps match or are close. No action.")
                        continue 

                    if local_mtime > cloud_mtime: # Local is newer
                        self._log_conflict(
                            f"Conflict for '{rel_path}'. Local is newer ({datetime.fromtimestamp(local_mtime, tz=timezone.utc).isoformat()}) "
                            f"than cloud ({datetime.fromtimestamp(cloud_mtime, tz=timezone.utc).isoformat()}). Uploading local."
                        )
                        target_cloud_folder = str(Path(rel_path).parent)
                        if target_cloud_folder == ".": target_cloud_folder = ""
                        
                        upload_meta = await self.cloud_service.upload_file(
                            local_file_state.path, target_cloud_folder, Path(rel_path).name
                        )
                        if upload_meta:
                             actions_taken_summary["conflicts_local_won"] += 1
                             # If local changes were significant, it should already be indexed.
                             # Re-indexing here might be redundant unless cloud mtime needs to be source of truth for index.
                        else:
                            logger.error(f"Conflict resolution: Failed to upload newer local file '{rel_path}'.")

                    else: # Cloud is newer
                        self._log_conflict(
                            f"Conflict for '{rel_path}'. Cloud is newer ({datetime.fromtimestamp(cloud_mtime, tz=timezone.utc).isoformat()}) "
                            f"than local ({datetime.fromtimestamp(local_mtime, tz=timezone.utc).isoformat()}). Downloading cloud."
                        )
                        local_target_path = self.fs_manager.get_local_sync_root() / rel_path # type: ignore
                        local_target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        success = await self.cloud_service.download_file(cloud_file_meta.path_display, local_target_path)
                        if success:
                            actions_taken_summary["conflicts_cloud_won"] += 1
                            article_obj = MarkdownHandler.parse_markdown_file(local_target_path)
                            if article_obj:
                                self.search_manager.add_or_update_article(article_obj)
                            else:
                                logger.warning(f"Conflict resolution: Could not parse downloaded article '{local_target_path}' for indexing.")
                        else:
                             logger.error(f"Conflict resolution: Failed to download newer cloud file '{rel_path}'.")
                
                # Deletion handling is more complex and requires tracking tombstones or comparing to a last known state.
                # The current logic implies if a file is deleted on one side, it will be re-uploaded/downloaded from the other.
                # This is "last write wins" extended to existence. True deletion sync is a V2 feature.

            await self._sync_settings_file() # Sync settings.yml

            logger.info(f"Synchronization process finished. Summary: {actions_taken_summary}")
            self._last_sync_time_utc = time.time() # Record sync time as float (Unix timestamp)

        except Exception as e:
            logger.error(f"🛑 An unexpected error occurred during synchronization: {e}", exc_info=True)
        finally:
            self._sync_lock.release()


    async def _sync_settings_file(self) -> None:
        """Synchronizes the application settings file (e.g., settings.yml) using Last Write Wins."""
        logger.info("Syncing settings.yml...")
        local_settings_path = self.fs_manager.get_synced_settings_path()
        if not local_settings_path:
            logger.error("🛑 Cannot sync settings: Local settings path could not be determined (sync root not set?).")
            return

        # Path of settings.yml relative to app's cloud root (e.g., ".purse_config/settings.yml")
        cloud_settings_rel_path = str(
            Path(self.fs_manager.synced_config_dir_name) / self.fs_manager.synced_settings_filename
        )
        
        cloud_meta = await self.cloud_service.get_file_metadata(cloud_settings_rel_path)
        local_exists = local_settings_path.exists()
        local_mtime: Optional[float] = None
        if local_exists:
            try: local_mtime = local_settings_path.stat().st_mtime
            except Exception as e: 
                logger.error(f"Could not stat local settings file {local_settings_path}: {e}")
                local_exists = False # Treat as not existing if cannot stat


        if local_exists and local_mtime is not None and not cloud_meta: # Local only, upload
            logger.info(f"Local '{local_settings_path.name}' exists, not in cloud. Uploading.")
            await self.cloud_service.upload_file(
                local_settings_path, 
                self.fs_manager.synced_config_dir_name, # Target folder in cloud (e.g. .purse_config)
                self.fs_manager.synced_settings_filename
            )
        elif not local_exists and cloud_meta: # Cloud only, download
            logger.info(f"Cloud '{cloud_settings_rel_path}' exists, not locally. Downloading.")
            local_settings_path.parent.mkdir(parents=True, exist_ok=True)
            await self.cloud_service.download_file(cloud_settings_rel_path, local_settings_path)
            # IMPORTANT: Application needs to be signaled to reload ConfigManager with these new settings.
            logger.info(f"'{local_settings_path.name}' downloaded. Application may need to reload settings.")
        elif local_exists and local_mtime is not None and cloud_meta: # Exists in both
            if abs(local_mtime - cloud_meta.modified_timestamp) > 2.0: # Timestamp tolerance
                if local_mtime > cloud_meta.modified_timestamp:
                    self._log_conflict(f"Conflict for '{local_settings_path.name}'. Local is newer. Uploading.")
                    await self.cloud_service.upload_file(
                        local_settings_path, self.fs_manager.synced_config_dir_name, self.fs_manager.synced_settings_filename
                    )
                else:
                    self._log_conflict(f"Conflict for '{local_settings_path.name}'. Cloud is newer. Downloading.")
                    await self.cloud_service.download_file(cloud_settings_rel_path, local_settings_path)
                    logger.info(f"'{local_settings_path.name}' downloaded due to conflict. Application may need to reload settings.")
            # else: Timestamps close, no action.
        # else: Neither exists, no action. (App might create default local one on next save by ConfigManager)
        logger.info("Settings.yml sync attempt complete.")

```
