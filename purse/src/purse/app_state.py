from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set # Dict might be for current_search_results if not List[Article]

# Assuming Article model is defined and can be imported
from purse.models.article import Article
# Assuming constants for defaults are available
from purse.utils import constants

@dataclass
class ReadingPreferences:
    """Stores user's reading preferences."""
    font_family: str = constants.DEFAULT_FONT_FAMILY
    font_size: int = constants.DEFAULT_FONT_SIZE
    theme: str = constants.DEFAULT_THEME # Expected values: "light", "dark", "sepia"

@dataclass
class AppState:
    """Holds the application-wide state."""
    
    # Article and list management
    current_article_list: List[Article] = field(default_factory=list)
    selected_article: Optional[Article] = None
    
    # Search state
    last_search_query: Optional[str] = None
    # Assuming search results ideally return Article objects for consistency in UI.
    # If SearchManager returns dicts, this could be List[Dict[str, Any]].
    current_search_results: List[Article] = field(default_factory=list) 
                                             
    # User preferences (some loaded from settings.yml via ConfigManager into AppState)
    reading_prefs: ReadingPreferences = field(default_factory=ReadingPreferences)
    
    # Synced settings that might affect behavior or UI
    developer_notification_url: Optional[str] = None # User override from settings.yml
    
    # Cloud synchronization state
    cloud_provider_name: Optional[str] = None # Name of the configured cloud provider
    is_syncing: bool = False # True if a sync operation is currently in progress
    last_sync_status: Optional[str] = None # e.g., "Success", "Failed: reason", "In Progress..."
    last_successful_sync_time_iso: Optional[str] = None # ISO 8601 timestamp
    
    # UI related state
    status_messages: List[str] = field(default_factory=list) # For displaying messages in a status bar/area
    all_tags_in_library: Set[str] = field(default_factory=set) # Set of all unique tags in the library
    
    # Reference to a Toga widget for status updates, if direct manipulation is chosen.
    # Using Any to avoid direct Toga import dependency at this level if possible,
    # or a forward reference string 'toga.Label' if that's preferred and works with type checker.
    # For simplicity, Any is often used for UI widget types in state models if they are loosely coupled.
    status_label_widget: Optional[Any] = None 

    # Add other application-wide states as they become necessary.
    # For example:
    # - current_filter_criteria: Optional[Dict[str, Any]] = None
    # - is_offline_mode: bool = False # Though offline-first is a principle
    # - active_cloud_service_client: Optional[Any] = None # If storing the client instance here (less common)

```
