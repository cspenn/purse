from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any, AsyncGenerator, TYPE_CHECKING
from pathlib import Path
import logging
from dataclasses import dataclass
import keyring
import json
# from purse.utils import constants # Import handled in _get_keyring_service_name

if TYPE_CHECKING:
    from purse.config_manager import ConfigManager # For type hinting

logger = logging.getLogger(__name__)

@dataclass
class CloudFileMetadata:
    """
    Standardized representation of file/folder metadata from a cloud provider.
    """
    id: str  # Provider-specific ID for the file or folder
    name: str # Name of the file or folder
    path_display: str # Full path as displayed by the provider, or path relative to app root.
                      # Implementations should clarify if this is full path or relative to app root.
                      # For consistency, relative to app root might be better if feasible.
    rev: str # Revision identifier (e.g., content hash, version ID)
    size: int # Size in bytes (for files)
    modified_timestamp: float # UTC Unix timestamp (seconds since epoch) of last modification
    is_folder: bool = False
    is_deleted: bool = False # For providers that mark deletions (e.g., soft delete)


class BaseCloudService(ABC):
    """
    Abstract Base Class for cloud storage operations.
    Defines a common interface for interacting with different cloud storage providers.
    """
    PROVIDER_NAME: str = "AbstractCloudProvider" # Should be overridden by subclasses

    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry_timestamp: Optional[float] = None # Store expiry as Unix timestamp
        
        # Default application root folder in the cloud. User might override this via settings.
        # It's the base path under which this application will store its data.
        self.root_folder_path: str = "/Apps/Purse" 
        self.user_id: Optional[str] = None # Cloud provider's user ID, often obtained during auth
        self._load_tokens_from_keyring()

    @abstractmethod
    async def authenticate_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generates an authorization URL for OAuth2 PKCE flow.
        
        Args:
            state: An optional opaque value used to maintain state between the request and callback.

        Returns:
            A tuple containing:
            - auth_url (str): The URL to which the user should be redirected.
            - code_verifier (str): The PKCE code verifier. This should be stored securely
                                   (e.g., in session or local cache) to be used when exchanging the code.
        """
        pass

    @abstractmethod
    async def exchange_code_for_token(self, auth_code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchanges an authorization code for an access token and refresh token.
        
        Args:
            auth_code: The authorization code received from the OAuth callback.
            code_verifier: The PKCE code verifier generated during `authenticate_url`.

        Returns:
            A dictionary containing token information, typically including:
            - 'access_token' (str)
            - 'refresh_token' (str)
            - 'expires_in' (int, seconds)
            - 'user_id' (str, optional, provider-specific user identifier)
            - Potentially other fields like 'scope', 'token_type'.
        
        Implementations of this method MUST:
        1. Extract token details (access_token, refresh_token, expiry, user_id).
        2. Construct a dictionary with these details.
        3. Call `self._save_tokens_to_keyring(token_dict)` to persist them.
        4. Set `self.user_id` on the instance.
        5. Call `self._reinitialize_client_with_loaded_tokens()` to update the client.
        """
        pass

    @abstractmethod
    async def refresh_access_token(self) -> Optional[str]:
        """
        Refreshes the access token using the stored refresh token.
        Updates `self.access_token` and potentially `self.refresh_token` if it's rotated.
        
        Returns:
            The new access token if successful, otherwise None.
        
        Implementations of this method, upon successful token refresh, MUST:
        1. Update `self.access_token`, `self.refresh_token` (if changed), and `self.token_expiry_timestamp`.
        2. Construct a dictionary with the new token details.
        3. Call `self._save_tokens_to_keyring(new_token_dict)`.
        4. Call `self._reinitialize_client_with_loaded_tokens()`.
        """
        pass

    @abstractmethod
    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Fetches basic user information from the cloud provider (e.g., email, name, user ID).
        
        Returns:
            A dictionary containing user information, or None on failure.
            Structure depends on the provider (e.g., {'email': '...', 'name': '...', 'id': '...'}).
        """
        pass

    @abstractmethod
    async def list_folder(self, folder_path: str, recursive: bool = False) -> AsyncGenerator[CloudFileMetadata, None]:
        """
        Lists files and folders in a given cloud path, relative to the app's root folder.
        
        Args:
            folder_path: The path relative to `self.root_folder_path`. Use "" or "." for the root itself.
            recursive: If True, recursively list contents of subfolders.

        Yields:
            CloudFileMetadata objects for each item in the folder.
        """
        # Example of how it might be structured in implementation:
        # full_path_to_list = self.get_full_cloud_path(folder_path)
        # # ... provider-specific API call to list full_path_to_list ...
        # # ... for item in response ...
        # #     yield self._map_provider_meta_to_cloudfilemetadata(item)
        # # Placeholder to make it a valid async generator:
        if False: # Ensure this is never actually hit in ABC
            yield # type: ignore 
        pass


    @abstractmethod
    async def download_file(self, cloud_file_path: str, local_target_path: Path) -> bool:
        """
        Downloads a file from the cloud to a local path.
        
        Args:
            cloud_file_path: Path to the file in the cloud, relative to `self.root_folder_path`.
            local_target_path: The local Path object where the file should be saved.
                               The parent directory of this path should exist.

        Returns:
            True if download was successful, False otherwise.
        """
        pass

    @abstractmethod
    async def download_file_content(self, cloud_file_path: str) -> Optional[bytes]:
        """
        Downloads a file's content directly into bytes.
        
        Args:
            cloud_file_path: Path to the file in the cloud, relative to `self.root_folder_path`.

        Returns:
            The file content as bytes if successful, otherwise None.
        """
        pass

    @abstractmethod
    async def upload_file(self, local_file_path: Path, cloud_target_folder: str, cloud_file_name: Optional[str] = None) -> Optional[CloudFileMetadata]:
        """
        Uploads a local file to the specified cloud folder.
        
        Args:
            local_file_path: Path object of the local file to upload.
            cloud_target_folder: The cloud folder path relative to `self.root_folder_path` where the file will be uploaded.
            cloud_file_name: Optional. If None, uses `local_file_path.name`. Otherwise, uses the provided name.

        Returns:
            CloudFileMetadata of the uploaded file if successful, otherwise None.
        """
        pass

    @abstractmethod
    async def upload_file_content(self, content_bytes: bytes, cloud_target_folder: str, cloud_file_name: str) -> Optional[CloudFileMetadata]:
        """
        Uploads bytes directly as a file to the specified cloud folder.
        
        Args:
            content_bytes: The content to upload as bytes.
            cloud_target_folder: The cloud folder path relative to `self.root_folder_path`.
            cloud_file_name: The name for the file in the cloud.

        Returns:
            CloudFileMetadata of the uploaded file if successful, otherwise None.
        """
        pass

    @abstractmethod
    async def delete_file(self, cloud_file_path: str) -> bool:
        """
        Deletes a file or folder from the cloud.
        
        Args:
            cloud_file_path: Path to the file or folder in the cloud, relative to `self.root_folder_path`.

        Returns:
            True if deletion was successful, False otherwise.
        """
        pass

    @abstractmethod
    async def create_folder(self, cloud_folder_path: str) -> bool:
        """
        Creates a folder in the cloud. If the folder already exists, typically should succeed.
        
        Args:
            cloud_folder_path: Path of the folder to create, relative to `self.root_folder_path`.
                               Implementations should handle nested folder creation if the API requires it
                               (e.g., creating intermediate parent folders).

        Returns:
            True if folder was created or already existed, False on error.
        """
        pass
    
    @abstractmethod
    async def get_file_metadata(self, cloud_file_path: str) -> Optional[CloudFileMetadata]:
        """
        Gets metadata for a specific file or folder in the cloud.
        
        Args:
            cloud_file_path: Path to the file or folder, relative to `self.root_folder_path`.

        Returns:
            CloudFileMetadata if the item exists, None if not found or on error.
        """
        pass

    @abstractmethod
    def _reinitialize_client_with_loaded_tokens(self) -> None:
        """
        Called after tokens are loaded from keyring or updated.
        Subclasses should use this method to re-initialize their specific HTTP client
        (e.g., self.dbx for Dropbox, self.creds for GoogleDrive) using the token
        attributes now set on the instance (self.access_token, self.refresh_token, etc.).
        """
        pass

    # --- Keyring Interaction Methods ---

    def _get_keyring_service_name(self) -> str:
        """Generates a unique service name for keyring based on provider and app ID."""
        # Assuming constants.APP_ID is available. If not, get 'app_id' from config_manager as fallback.
        # For robustness, check if constants module and APP_ID exist or handle gracefully.
        try:
            from purse.utils import constants as app_constants
            app_id_val = self.config_manager.get('app_id', app_constants.APP_ID)
        except (ImportError, AttributeError):
            app_id_val = self.config_manager.get('app_id', 'PurseAppGenericID') # Fallback if constants not found
            logger.warning("Could not import constants.APP_ID for keyring service name. Using configured or generic app_id.")
        return f"{app_id_val}_{self.PROVIDER_NAME}"

    def _load_tokens_from_keyring(self) -> None:
        """Loads tokens from keyring and sets them on the instance."""
        service_name = self._get_keyring_service_name()
        # Keyring username: use self.user_id if available, else a generic placeholder.
        # This is important because keyring stores passwords against a service/username pair.
        # If user_id is set *after* initial load (e.g. from first token exchange),
        # subsequent loads might use a different keyring_username if not handled.
        # For now, assume we might not have user_id on first load.
        keyring_username = self.user_id or f"{self.PROVIDER_NAME}_default_user" 
        
        try:
            token_bundle_str = keyring.get_password(service_name, keyring_username)
            if token_bundle_str:
                token_data = json.loads(token_bundle_str)
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                self.token_expiry_timestamp = token_data.get('token_expiry_timestamp')
                loaded_user_id = token_data.get('user_id')
                
                if loaded_user_id and not self.user_id:
                    self.user_id = loaded_user_id
                    # If user_id was just loaded, and it differs from the placeholder keyring_username,
                    # it implies tokens might have been saved under a more specific user_id later.
                    # This simple load won't find them. Complex multi-account handling is outside current scope.
                    # Assume for now that if user_id becomes known, it's consistent.
                
                logger.info(f"{self.PROVIDER_NAME}: Tokens loaded from keyring for service '{service_name}', user '{keyring_username}'.")
                # After loading, the specific service needs to re-initialize its client
                self._reinitialize_client_with_loaded_tokens()
            else:
                logger.info(f"{self.PROVIDER_NAME}: No tokens found in keyring for service '{service_name}', user '{keyring_username}'.")
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error loading tokens from keyring: {e}", exc_info=True)

    def _save_tokens_to_keyring(self, token_data_to_save: Dict[str, Any]) -> None:
        """Saves the provided token bundle to keyring."""
        service_name = self._get_keyring_service_name()
        # When saving, self.user_id should ideally be known (e.g. from token exchange).
        # If self.user_id was just set from token_data_to_save, use that.
        keyring_username = token_data_to_save.get('user_id', self.user_id) or f"{self.PROVIDER_NAME}_default_user"

        # Prepare bundle, ensuring all expected keys are present, even if None
        bundle_to_store = {
            'access_token': token_data_to_save.get('access_token'),
            'refresh_token': token_data_to_save.get('refresh_token'),
            'token_expiry_timestamp': token_data_to_save.get('token_expiry_timestamp'),
            'user_id': token_data_to_save.get('user_id') # Persist user_id with tokens
        }

        if not bundle_to_store['access_token']:
            logger.warning(f"{self.PROVIDER_NAME}: Attempted to save tokens to keyring, but access token is missing in provided data.")
            return

        try:
            keyring.set_password(service_name, keyring_username, json.dumps(bundle_to_store))
            logger.info(f"{self.PROVIDER_NAME}: Tokens saved to keyring for service '{service_name}', user '{keyring_username}'.")
            # Update current instance's tokens from the saved data
            self.access_token = bundle_to_store['access_token']
            self.refresh_token = bundle_to_store['refresh_token']
            self.token_expiry_timestamp = bundle_to_store['token_expiry_timestamp']
            if bundle_to_store['user_id'] and not self.user_id: # Update instance user_id if it was missing
                 self.user_id = bundle_to_store['user_id']
            elif bundle_to_store['user_id'] and self.user_id != bundle_to_store['user_id']:
                 logger.warning(f"{self.PROVIDER_NAME}: User ID changed during token save. Old: {self.user_id}, New: {bundle_to_store['user_id']}")
                 self.user_id = bundle_to_store['user_id']

        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error saving tokens to keyring: {e}", exc_info=True)
            
    def _delete_tokens_from_keyring(self) -> None:
        """Deletes tokens from keyring for the current user_id or default."""
        service_name = self._get_keyring_service_name()
        keyring_username = self.user_id or f"{self.PROVIDER_NAME}_default_user"
        try:
            keyring.delete_password(service_name, keyring_username)
            logger.info(f"{self.PROVIDER_NAME}: Tokens deleted from keyring for service '{service_name}', user '{keyring_username}'.")
        except keyring.errors.PasswordDeleteError: # Specific exception for password not found
            logger.info(f"{self.PROVIDER_NAME}: No tokens found in keyring to delete for service '{service_name}', user '{keyring_username}'.")
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error deleting tokens from keyring: {e}", exc_info=True)
        finally:
            # Clear tokens from current instance as well
            self.access_token = None
            self.refresh_token = None
            self.token_expiry_timestamp = None
            # Optionally clear self.user_id too, depending on logout strategy
            # self.user_id = None 

    # --- Concrete Methods ---

    def get_full_cloud_path(self, relative_path: str) -> str:
        """
        Combines the app's root folder path with a relative path to get an absolute cloud path.
        Ensures no double slashes and correct joining.
        Example: self.root_folder_path = "/Apps/Purse", relative_path = "MyFolder/file.txt"
                 Returns "/Apps/Purse/MyFolder/file.txt"
                 If relative_path is "" or ".", returns self.root_folder_path.
        """
        # Normalize root_folder_path: ensure it starts with '/' and doesn't end with '/' unless it's just '/'
        clean_root = self.root_folder_path.strip()
        if not clean_root.startswith('/'):
            clean_root = '/' + clean_root
        
        if clean_root != '/': # Avoid double slash if root is just '/'
            clean_root = clean_root.rstrip('/')

        # Normalize relative_path: remove leading '/'
        clean_relative = relative_path.strip().lstrip('/')
        
        if not clean_relative or clean_relative == '.':
            return clean_root if clean_root else "/" # Return root itself, or "/" if root was empty/invalid
        
        # Handle case where root is "/"
        if clean_root == "/":
            return "/" + clean_relative

        return f"{clean_root}/{clean_relative}"


    def set_root_folder_path(self, root_path: str) -> None:
        """
        Sets the user-defined root folder for the application in their cloud storage.
        The path should be an absolute path from the cloud provider's root.
        Example: "/MyCustomPurseFolder" or "/Apps/Purse" (default).
        """
        self.root_folder_path = root_path.strip()
        if not self.root_folder_path: # Cannot be empty
            self.root_folder_path = "/Apps/Purse" # Fallback to default
            logger.warning("Root folder path cannot be empty. Reset to default '/Apps/Purse'.")
        
        if not self.root_folder_path.startswith('/'):
            self.root_folder_path = '/' + self.root_folder_path
        
        logger.info(f"{self.PROVIDER_NAME}: Application cloud root folder set to '{self.root_folder_path}'")


    async def ensure_app_root_folder_exists(self) -> bool:
        """
        Checks if the application's root folder (self.root_folder_path) exists in the cloud.
        If not, attempts to create it. This method assumes self.root_folder_path is an
        absolute path from the true root of the cloud storage (e.g., "/Apps/Purse").
        The `create_folder` method is called with paths relative to the *true* cloud root
        if the provider API expects that, or relative to an implicit app root if the SDK handles it.
        This default implementation calls `self.create_folder` with segments of the path.
        """
        if not self.root_folder_path or self.root_folder_path == "/":
            logger.info(f"{self.PROVIDER_NAME}: App root folder is the cloud storage root ('/'). Assuming it exists.")
            return True

        # Check if the full path already exists
        # The path given to get_file_metadata is relative to self.root_folder_path.
        # So, to check self.root_folder_path itself, we need to adjust or use a different mechanism.
        # This default implementation will try to create it part by part.
        # A provider might have a more direct way (e.g. get metadata of the root folder itself).
        
        # For a path like "/Apps/Purse", we need to create "Apps", then "Purse" inside "Apps".
        # The paths passed to self.create_folder are relative to self.root_folder_path.
        # This is a bit circular for THIS specific method.
        # Let's assume self.create_folder in implementations takes path from true cloud root.
        # Or, this method should be mostly implemented by subclasses.

        # A simplified approach for this base method:
        # Try to get metadata of the parent of self.root_folder_path, then try to create self.root_folder_path.
        # This is still complex for a base method as "parent" logic varies.

        # For now, this method will try to create the full self.root_folder_path.
        # Subclasses should override if their `create_folder` cannot handle nested creation directly.
        # The path passed to `create_folder` is relative to `self.root_folder_path`.
        # This means to create `self.root_folder_path` itself, we need to call `create_folder`
        # with a path that, when prefixed by `self.root_folder_path`, results in `self.root_folder_path`.
        # This is not logical.
        
        # Redesign: `create_folder` should take a path that is absolute within the cloud provider's file system
        # if it's meant to be used by this method. Or, this method should be mostly abstract.
        
        # Let's assume `create_folder` in implementations can handle the full path from provider's root,
        # OR that `self.root_folder_path` is simple enough (e.g. not deeply nested) for a simple check.

        # Simpler logic: try to get metadata of the root folder. If it fails, try to create it.
        # The path for get_file_metadata is relative to self.root_folder_path.
        # To check the root folder itself, we'd pass "" or ".".
        logger.info(f"{self.PROVIDER_NAME}: Ensuring app root folder '{self.root_folder_path}' exists...")
        try:
            # This specific call needs to be handled carefully by implementations.
            # It's checking the root folder itself. Some APIs get metadata for path "" relative to app root.
            # For Dropbox, path "" to files_get_metadata with root set to App Folder is fine.
            # For others, might need to list parent of self.root_folder_path and check.
            # This is a common pattern, so providing a default.
            
            # We need to check the existence of self.root_folder_path from the *actual* cloud root.
            # The methods in this ABC are designed to work *within* self.root_folder_path.
            # So, this method is a bit of an exception.
            # The most straightforward way is if get_file_metadata can accept an absolute path
            # or if create_folder can.
            # Let's assume for this base implementation, we'll try a direct creation.
            # If it fails because parent doesn't exist, then specific implementation must override.

            # This path should be relative to the true cloud root, not self.root_folder_path.
            # So, we strip the leading '/' for some APIs.
            path_from_cloud_root = self.root_folder_path.lstrip('/')
            
            # Attempt to create the folder. If it exists, this should ideally be a no-op or succeed.
            # The `create_folder` method in the ABC takes a path relative to `self.root_folder_path`.
            # This is problematic for `ensure_app_root_folder_exists`.
            # The `create_folder` in `BaseCloudService` should take an *absolute* cloud path for this to work generally.
            # Re-evaluating the design of `create_folder`'s path argument for this specific use case.
            # For now, let's assume that the implementation of `create_folder` is smart enough or
            # this method `ensure_app_root_folder_exists` will be overridden.
            
            # A pragmatic approach: try to list the root folder. If it works, it exists.
            # If not, try to create it.
            try:
                # Try to get metadata of the folder. If it exists and is a folder, we are good.
                # This requires `get_file_metadata` to handle paths from the true cloud root if `cloud_file_path`
                # is constructed to be absolute.
                # Let's assume `get_file_metadata` takes path relative to `self.root_folder_path`.
                # So to check `self.root_folder_path` itself, we pass `""`.
                metadata = await self.get_file_metadata("") # Check current root_folder_path
                if metadata and metadata.is_folder:
                    logger.info(f"{self.PROVIDER_NAME}: App root folder '{self.root_folder_path}' already exists.")
                    return True
                elif metadata and not metadata.is_folder: # Exists but is a file
                    logger.error(f"{self.PROVIDER_NAME}: Path '{self.root_folder_path}' for app root exists but is a file, not a folder.")
                    return False
            except Exception: # Broadly catch if get_file_metadata fails (e.g. not found)
                pass

            # If not found or error, try to create it.
            # This `create_folder` call needs to be robust in implementations.
            # It must create `self.root_folder_path` from the *actual* cloud root.
            # The `cloud_folder_path` argument for `create_folder` is relative to `self.root_folder_path`.
            # This creates a conceptual issue.
            # Solution: `BaseCloudService.create_folder` should specify if path is relative to app root or absolute.
            # For `ensure_app_root_folder_exists`, we are operating on the app root itself.
            # This method should likely be implemented more specifically in subclasses.
            # For this ABC, we can only state intent.
            logger.info(f"{self.PROVIDER_NAME}: App root folder '{self.root_folder_path}' not found or not a folder. Attempting to create.")
            # This call is tricky due to path relativity. Subclass should implement this robustly.
            # A simple attempt:
            # This will call create_folder with path_from_cloud_root, assuming create_folder can handle absolute paths
            # if it detects them, or this method is overridden.
            # For now, this default implementation is a placeholder for subclass logic.
            # It cannot reliably use `self.create_folder("")` if `self.root_folder_path` is not yet valid.

            # If not found or error, try to create it using self.create_folder("").
            # This assumes self.create_folder implementations can correctly create the currently set
            # self.root_folder_path when called with an empty relative path, or that they have
            # a mechanism to handle root creation if it's special (e.g. Dropbox App Folder).
            logger.info(f"{self.PROVIDER_NAME}: App root folder '{self.root_folder_path}' not found or not a folder. Attempting to create via self.create_folder(\"\").")
            created_successfully = await self.create_folder("") # Attempt to create the root folder itself.
            if created_successfully:
                logger.info(f"{self.PROVIDER_NAME}: Successfully ensured app root folder '{self.root_folder_path}' (created or already existed).")
                return True
            else:
                logger.error(f"{self.PROVIDER_NAME}: Failed to create app root folder '{self.root_folder_path}'.")
                return False

        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error ensuring app root folder '{self.root_folder_path}' exists: {e}", exc_info=True)
            return False

```
