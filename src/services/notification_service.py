import json # For parsing JSON from http_client if it doesn't auto-parse to dict
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Set, TYPE_CHECKING

from src.services.http_client import HttpClient
from src.utils import common # For get_current_timestamp_iso

# Type hints for services to avoid circular imports at runtime
if TYPE_CHECKING:
    from src.config_manager import ConfigManager
    from src.services.file_system_manager import FileSystemManager
    try:
        from toga import App
    except ImportError:
        App = None # type: ignore


logger = logging.getLogger(__name__)

@dataclass
class DeveloperNotification:
    """Represents a notification fetched from the developer's notification service."""
    id: str
    title: str
    message: str
    level: str = "info"  # "info", "warning", "error"
    url: Optional[str] = None  # Optional URL for more details
    timestamp_iso: str # ISO 8601 timestamp string of when the notification was issued


class NotificationService:
    def __init__(self, 
                 config_manager: 'ConfigManager', 
                 http_client: HttpClient, 
                 fs_manager: 'FileSystemManager', 
                 toga_app: Optional['App'] = None):
        self.config_manager = config_manager
        self.http_client = http_client
        self.fs_manager = fs_manager
        self.toga_app = toga_app
        
        # Default fallback URL should be defined in config.yml or constants if it's a true constant.
        # For now, using a placeholder string if not found in config, as per instructions.
        self.developer_notifications_url: Optional[str] = self.config_manager.get(
            'developer_notifications_url', 
            None # Or a default URL string like "https://example.com/notifications.json"
                  # The workplan had "https_default_fallback_url/purse/notifications.json"
                  # but config.yml has "https://www.christopherspenn.com/purse/notifications.json"
                  # So, if config.yml is correctly loaded, this will pick it up.
                  # If key is missing, get() returns None.
        )
        if not self.developer_notifications_url:
            logger.warning("Developer notifications URL is not configured. Developer notifications will not be fetched.")

        self.seen_notification_ids: Set[str] = self._load_seen_notifications()

    def _load_seen_notifications(self) -> Set[str]:
        """Loads seen notification IDs from device settings via FileSystemManager."""
        try:
            device_settings = self.fs_manager.load_device_settings()
            seen_ids = device_settings.get('seen_notification_ids', [])
            if not isinstance(seen_ids, list): # Ensure it's a list before converting to set
                logger.warning("Malformed 'seen_notification_ids' in device settings; expected a list.")
                return set()
            return set(seen_ids)
        except Exception as e:
            logger.error(f"Error loading seen notification IDs: {e}", exc_info=True)
            return set() # Return empty set on error

    def _save_seen_notifications(self) -> None:
        """Saves the current set of seen notification IDs to device settings."""
        try:
            # Load existing settings to ensure we don't overwrite other unrelated device settings.
            device_settings = self.fs_manager.load_device_settings() 
            device_settings['seen_notification_ids'] = list(self.seen_notification_ids)
            self.fs_manager.save_device_settings(device_settings)
        except Exception as e:
            logger.error(f"Error saving seen notification IDs: {e}", exc_info=True)

    async def fetch_developer_notifications(self) -> List[DeveloperNotification]:
        """
        Fetches new (unseen) notifications from the developer-specified URL.
        Returns a list of DeveloperNotification objects.
        """
        if not self.developer_notifications_url:
            # Already logged warning in __init__ if URL is None
            return []
        
        logger.info(f"Fetching developer notifications from: {self.developer_notifications_url}")
        new_notifications: List[DeveloperNotification] = []
        
        try:
            # Assuming http_client.get_url handles retries as configured
            response = await self.http_client.get_url(self.developer_notifications_url, timeout=10.0)
            
            # httpx response.json() parses JSON content into a Python dict/list
            raw_notifications_list = response.json()

            if not isinstance(raw_notifications_list, list):
                logger.error(f"Developer notifications response is not a list: {type(raw_notifications_list)}")
                return []

            for raw_notif_dict in raw_notifications_list:
                if not isinstance(raw_notif_dict, dict):
                    logger.warning(f"Skipping malformed notification entry (not a dict): {raw_notif_dict}")
                    continue

                notif_id = raw_notif_dict.get('id')
                if not notif_id or not isinstance(notif_id, str):
                    logger.warning(f"Skipping notification with missing or invalid ID: {raw_notif_dict}")
                    continue

                if notif_id in self.seen_notification_ids:
                    logger.debug(f"Skipping already seen notification ID: {notif_id}")
                    continue
                
                # Use provided timestamp or default to current time if missing
                timestamp_iso = raw_notif_dict.get('timestamp_iso', common.get_current_timestamp_iso())

                try:
                    notification = DeveloperNotification(
                        id=notif_id,
                        title=str(raw_notif_dict.get('title', 'Notification')),
                        message=str(raw_notif_dict.get('message', '')),
                        level=str(raw_notif_dict.get('level', 'info')).lower(), # Normalize level
                        url=raw_notif_dict.get('url'), # Optional, can be None
                        timestamp_iso=timestamp_iso
                    )
                    new_notifications.append(notification)
                except Exception as e: # Catch errors during DeveloperNotification instantiation (e.g. type errors if data is bad)
                    logger.warning(f"Could not create DeveloperNotification object from data {raw_notif_dict}: {e}")
            
            logger.info(f"Fetched {len(new_notifications)} new developer notifications.")
            return new_notifications
            
        except httpx.HTTPStatusError as e: # Specific HTTP errors (4xx, 5xx)
            logger.error(f"HTTP error fetching developer notifications: {e.response.status_code} - {e.response.text[:200]}")
        except httpx.RequestError as e: # Network errors, timeouts
            logger.error(f"Request error fetching developer notifications: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from developer notifications response: {e}")
        except Exception as e: # Catch-all for other unexpected issues
            logger.error(f"An unexpected error occurred while fetching developer notifications: {e}", exc_info=True)
        
        return [] # Return empty list on any error

    def mark_notification_seen(self, notification_id: str) -> None:
        """Marks a notification ID as seen and saves the updated set."""
        if not isinstance(notification_id, str) or not notification_id:
            logger.warning("Attempted to mark an invalid notification_id as seen.")
            return
            
        if notification_id not in self.seen_notification_ids:
            self.seen_notification_ids.add(notification_id)
            self._save_seen_notifications()
            logger.debug(f"Marked notification ID '{notification_id}' as seen.")
        else:
            logger.debug(f"Notification ID '{notification_id}' was already marked as seen.")


    def show_system_notification(self, title: str, message: str, level: str = "info") -> None:
        """
        Displays a system notification using Toga dialogs if available,
        otherwise logs to the console.
        'level' can be "info", "warning", or "error".
        """
        logger.debug(f"Attempting to show system notification: Level='{level}', Title='{title}'")
        
        if self.toga_app and hasattr(self.toga_app, 'main_window') and self.toga_app.main_window:
            try:
                if level == "error":
                    self.toga_app.main_window.error_dialog(title, message)
                elif level == "warning":
                    # Toga's question_dialog is for yes/no. Use info_dialog for warnings for now,
                    # or consider if main_window.confirm_dialog or a custom dialog is more appropriate.
                    # For simplicity, mapping warning to info_dialog with a prepended title.
                    self.toga_app.main_window.info_dialog(f"Warning: {title}", message) 
                    # Or, if a more distinct warning dialog is desired:
                    # self.toga_app.main_window.confirm_dialog(title, message) # Confirm has Yes/No
                    # self.toga_app.main_window.warn_dialog(title, message) # If Toga adds this
                else: # "info" or any other level
                    self.toga_app.main_window.info_dialog(title, message)
                logger.info(f"Displayed Toga system notification: '{title}'")
            except Exception as e:
                logger.error(f"🛑 Failed to show Toga system notification: {e}. Falling back to console log.", exc_info=True)
                self._log_notification_to_console(title, message, level) # Fallback
        else:
            logger.info("Toga app or main_window not available. Logging notification to console.")
            self._log_notification_to_console(title, message, level)

    def _log_notification_to_console(self, title: str, message: str, level: str):
        """Helper to log notifications to console based on level."""
        log_message = f"SYSTEM NOTIFICATION [{title.upper()}]: {message}"
        if level == "error":
            logger.error(log_message)
        elif level == "warning":
            logger.warning(log_message)
        else: # info
            logger.info(log_message)

