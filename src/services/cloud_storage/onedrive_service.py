import asyncio
from datetime import datetime, timezone
import msal
import httpx
import json # For request bodies
import logging
from typing import List, Optional, Tuple, Dict, Any, AsyncGenerator, TYPE_CHECKING
from pathlib import Path
from urllib.parse import quote # For encoding path segments in URLs
import time # Needed for expires_at calculation in exchange_code_for_token

from src.services.cloud_storage.base_cloud_service import BaseCloudService, CloudFileMetadata
from src.services.cloud_storage.exceptions import AuthError, ConfigurationError, ServiceError


if TYPE_CHECKING:
    from src.config_manager import ConfigManager

logger = logging.getLogger(__name__)

# Max size for simple PUT upload (Graph API recommends resumable for >4MB)
SIMPLE_UPLOAD_MAX_SIZE_BYTES = 4 * 1024 * 1024 

class OneDriveService(BaseCloudService):
    PROVIDER_NAME = "OneDrive"

    def __init__(self, config_manager: 'ConfigManager'):
        super().__init__(config_manager) # Base class __init__ loads tokens from keyring.
                                        # For OneDrive: self.access_token = serialized MSAL cache string
                                        #              self.user_id = home_account_id (MSAL's home_account_id)
        
        # Load OneDrive/MSAL specific configurations
        self.onedrive_client_id: Optional[str] = self.config_manager.get('cloud_providers.onedrive.client_id')
        self.onedrive_authority: Optional[str] = self.config_manager.get('cloud_providers.onedrive.authority')
        self.onedrive_scopes: Optional[List[str]] = self.config_manager.get('cloud_providers.onedrive.scopes')
        self.onedrive_redirect_uri: Optional[str] = self.config_manager.get('cloud_providers.onedrive.redirect_uri')
        self.graph_api_endpoint: str = self.config_manager.get('cloud_providers.onedrive.graph_api_endpoint_v1', 'https://graph.microsoft.com/v1.0')

        if not all([self.onedrive_client_id, self.onedrive_authority, self.onedrive_scopes, self.onedrive_redirect_uri]):
            logger.error(f"{self.PROVIDER_NAME}: Critical OAuth configuration missing. OneDrive service will be unavailable.")
            self._is_configured = False
        else:
            self._is_configured = True
        
        self.msal_cache = msal.SerializableTokenCache() # Always create a new cache object instance for this service instance
        self.msal_app: Optional[msal.PublicClientApplication] = None # Will be set by _reinitialize_client_with_loaded_tokens
        
        self._pkce_verifier: Optional[str] = None 
        
        self._reinitialize_client_with_loaded_tokens() # This will use self.access_token (cache string) and self.user_id

    def _reinitialize_client_with_loaded_tokens(self) -> None:
        """Initializes or re-initializes the MSAL app and its cache using loaded tokens."""
        # self.msal_cache is already a fresh instance from __init__ or previous calls.
        # Deserialize into this instance's msal_cache object.
        if self.access_token: # self.access_token from base class IS the serialized MSAL cache string.
            try:
                self.msal_cache.deserialize(self.access_token)
                logger.info(f"{self.PROVIDER_NAME}: MSAL cache deserialized successfully for user {self.user_id}.")
            except Exception as e:
                logger.warning(f"{self.PROVIDER_NAME}: Failed to deserialize MSAL cache from keyring for user {self.user_id}: {e}. Starting with an empty cache.", exc_info=True)
                self.msal_cache = msal.SerializableTokenCache() # Ensure it's empty if deserialization fails
        else:
            logger.info(f"{self.PROVIDER_NAME}: No MSAL cache string found in keyring (user: {self.user_id}). Initializing with empty cache.")

        if self._is_configured: 
            try:
                self.msal_app = msal.PublicClientApplication(
                    client_id=self.onedrive_client_id, 
                    authority=self.onedrive_authority, 
                    token_cache=self.msal_cache # Use the msal_cache object associated with this OneDriveService instance
                )
                logger.debug(f"{self.PROVIDER_NAME}: MSAL PublicClientApplication initialized/reinitialized for user {self.user_id}.")
            except Exception as e: 
                logger.error(f"{self.PROVIDER_NAME}: Failed to initialize MSAL PublicClientApplication for user {self.user_id}: {e}", exc_info=True)
                self.msal_app = None
        else:
            self.msal_app = None
            logger.error(f"{self.PROVIDER_NAME}: MSAL app cannot be initialized because service is not configured.")

    async def _get_headers(self) -> Optional[Dict[str, str]]:
        if not self.msal_app or not self.onedrive_scopes or not self._is_configured:
            logger.error(f"{self.PROVIDER_NAME}: MSAL app or OAuth parameters not configured. Cannot acquire token.")
            return None

        account_to_use = None
        # self.user_id from base class is the home_account_id loaded from keyring
        if self.user_id: 
            account_to_use = self.msal_app.get_account_by_home_id(self.user_id)
        
        if not account_to_use: 
            accounts = self.msal_app.get_accounts()
            if accounts:
                account_to_use = accounts[0]
                logger.info(f"{self.PROVIDER_NAME}: Using first account found in cache (Home Account ID: {account_to_use.get('home_account_id')}) as specified user_id '{self.user_id}' was not found or not set.")
            else:
                logger.info(f"{self.PROVIDER_NAME}: No cached accounts found. Interactive login required.")
                return None 

        token_result = None
        try:
            token_result = await asyncio.to_thread(
                self.msal_app.acquire_token_silent, self.onedrive_scopes, account=account_to_use
            )
        except Exception as e: # MSAL can raise various errors, catch broadly
            logger.warning(f"{self.PROVIDER_NAME}: Error during acquire_token_silent for user {self.user_id}: {e}", exc_info=True)
        
        if token_result and "access_token" in token_result:
            bearer_token = token_result["access_token"] # This is the live bearer token
            # The MSAL cache (self.msal_cache which is self.msal_app.token_cache) is automatically updated by acquire_token_silent.
            # The base class self.access_token attribute is for storing the serialized cache string in keyring,
            # it should NOT be set to the bearer_token here.
            return {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
        else:
            logger.warning(f"{self.PROVIDER_NAME}: Failed to acquire token silently for user {self.user_id}. Details: {token_result.get('error_description', 'No specific error description.') if token_result else 'No token result.'}")
            return None

    async def authenticate_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        if not self.msal_app or not self.onedrive_scopes or not self.onedrive_redirect_uri:
            self._reinitialize_client_with_loaded_tokens() # Attempt to build msal_app if not already
            if not self.msal_app or not self.onedrive_scopes or not self.onedrive_redirect_uri: # Check again
                 raise ConfigurationError(f"{self.PROVIDER_NAME}: MSAL app or OAuth parameters not configured after reinitialization attempt.")
        
        self._pkce_verifier = msal.oauth2cli.pkce.generate_code_verifier(43) 
        code_challenge = msal.oauth2cli.pkce.generate_code_challenge(self._pkce_verifier, "S256")

        auth_url = self.msal_app.get_authorization_request_url(
            self.onedrive_scopes, state=state, redirect_uri=self.onedrive_redirect_uri,
            code_challenge=code_challenge, code_challenge_method="S256"
        )
        return auth_url, self._pkce_verifier

    async def exchange_code_for_token(self, auth_code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        if not self.msal_app or not self.onedrive_scopes or not self.onedrive_redirect_uri:
            self._reinitialize_client_with_loaded_tokens()
            if not self.msal_app or not self.onedrive_scopes or not self.onedrive_redirect_uri:
                raise ConfigurationError(f"{self.PROVIDER_NAME}: MSAL app or OAuth parameters not configured after reinitialization attempt.")

        effective_verifier = self._pkce_verifier if self._pkce_verifier else code_verifier
        if not effective_verifier:
             raise ValueError("PKCE code_verifier is missing. It must be provided or generated by authenticate_url.")
        self._pkce_verifier = None 

        try:
            token_result = await asyncio.to_thread(
                self.msal_app.acquire_token_by_authorization_code,
                auth_code, scopes=self.onedrive_scopes, redirect_uri=self.onedrive_redirect_uri,
                code_verifier=effective_verifier
            )
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error acquiring token by authorization code: {e}", exc_info=True)
            raise AuthError(f"Token acquisition failed: {e}", user_message="Authentication with OneDrive failed.")

        if "error" in token_result: 
            err_msg = token_result.get('error_description', token_result['error'])
            logger.error(f"{self.PROVIDER_NAME}: Failed to acquire token: {err_msg}")
            raise AuthError(f"Token acquisition error: {err_msg}", user_message=f"Could not get OneDrive token: {err_msg}")

        acquired_bearer_token = token_result.get("access_token") 
        msal_cache_string_to_save = self.msal_cache.serialize() 
        
        account = token_result.get("account")
        user_id_val = None
        if account:
            user_id_val = account.get("home_account_id")
        elif "id_token_claims" in token_result and "oid" in token_result["id_token_claims"]: 
             user_id_val = token_result["id_token_claims"]["oid"]
        
        expires_in = token_result.get('expires_in')
        expiry_timestamp_val = (time.time() + expires_in) if expires_in else None 

        token_dict_to_save = {
            'access_token': msal_cache_string_to_save, 
            'refresh_token': None, 
            'user_id': user_id_val, 
            'token_expiry_timestamp': None 
        }
        
        self._save_tokens_to_keyring(token_dict_to_save) 
        self._reinitialize_client_with_loaded_tokens() 

        current_refresh_token_available = token_result.get("refresh_token") 

        logger.info(f"{self.PROVIDER_NAME}: Successfully exchanged code for token. User ID (HomeAccountID/OID): {self.user_id}")
        
        return {
            'access_token': acquired_bearer_token, 
            'refresh_token': current_refresh_token_available, 
            'user_id': self.user_id, 
            'id_token': token_result.get('id_token'),
            'id_token_claims': token_result.get('id_token_claims'),
            'scopes': token_result.get('scope'), 
            'expires_at': expiry_timestamp_val, 
        }

    async def refresh_access_token(self) -> Optional[str]:
        if not self.msal_app or not self.onedrive_scopes or not self._is_configured: 
            logger.warning(f"{self.PROVIDER_NAME}: MSAL app/config not ready for token refresh attempt.")
            # Try to reinitialize if critical components are missing
            self._reinitialize_client_with_loaded_tokens()
            if not self.msal_app or not self.onedrive_scopes or not self._is_configured:
                logger.error(f"{self.PROVIDER_NAME}: Reinitialization failed, cannot refresh token.")
                return None


        account_to_use = self.msal_app.get_account_by_home_id(self.user_id) if self.user_id else None
        if not account_to_use:
            accounts = self.msal_app.get_accounts()
            if accounts: 
                account_to_use = accounts[0]
                logger.info(f"{self.PROVIDER_NAME}: No specific user_id ('{self.user_id}') for refresh, using first account: {account_to_use.get('home_account_id') if account_to_use else 'N/A'}")
            else:
                logger.warning(f"{self.PROVIDER_NAME}: No accounts in cache to refresh token for.")
                return None 

        token_result = None
        try:
            logger.debug(f"Attempting silent token acquisition for user: {account_to_use.get('home_account_id') if account_to_use else 'Unknown'}, scopes: {self.onedrive_scopes}")
            token_result = await asyncio.to_thread(
                self.msal_app.acquire_token_silent, self.onedrive_scopes, account=account_to_use
            )
        except Exception as e: 
            logger.error(f"{self.PROVIDER_NAME}: Error during silent token acquisition for refresh for user {self.user_id}: {e}", exc_info=True)
            if "AADSTS700082" in str(e) or "invalid_grant" in str(e).lower() or "interaction_required" in str(e).lower():
                logger.warning(f"{self.PROVIDER_NAME}: Refresh token likely expired, revoked, or requires interaction for user {self.user_id}. Deleting tokens from keyring.")
                self._delete_tokens_from_keyring() 
                self._reinitialize_client_with_loaded_tokens() 
            return None

        if token_result and "access_token" in token_result:
            bearer_access_token = token_result["access_token"]
            updated_msal_cache_string = self.msal_cache.serialize()
            
            refreshed_account_home_id = account_to_use.get("home_account_id") if account_to_use else self.user_id

            token_dict_to_save = {
                'access_token': updated_msal_cache_string, 
                'refresh_token': None, 
                'user_id': refreshed_account_home_id, 
                'token_expiry_timestamp': None 
            }
            self._save_tokens_to_keyring(token_dict_to_save)
            
            if self.user_id != refreshed_account_home_id : # If user_id was updated by _save_tokens_to_keyring
                 logger.warning(f"{self.PROVIDER_NAME}: User ID changed during refresh from initial '{self.user_id}' to '{refreshed_account_home_id}'. Keyring updated.")
                 self._reinitialize_client_with_loaded_tokens() 
            
            logger.info(f"{self.PROVIDER_NAME}: Access token refreshed/validated silently for user '{self.user_id}'.")
            return bearer_access_token
        
        logger.warning(f"{self.PROVIDER_NAME}: Failed to refresh/validate token silently for user '{self.user_id}', no new access token obtained. Result: {token_result}")
        return None

    async def disconnect(self) -> None:
        """Disconnects the service, removes account from MSAL cache, and clears keyring tokens."""
        if self.msal_app and self.user_id: 
            account = self.msal_app.get_account_by_home_id(self.user_id)
            if account:
                try:
                    logger.info(f"{self.PROVIDER_NAME}: Removing account {self.user_id} from MSAL cache.")
                    await asyncio.to_thread(self.msal_app.remove_account, account)
                except Exception as e: 
                    logger.error(f"{self.PROVIDER_NAME}: Error removing account from MSAL cache: {e}", exc_info=True)
            else:
                logger.info(f"{self.PROVIDER_NAME}: No account found in MSAL cache for home_account_id {self.user_id} to remove.")
        
        self.msal_cache = msal.SerializableTokenCache() 
        if self.msal_app:
            self.msal_app.token_cache = self.msal_cache
        
        self._delete_tokens_from_keyring() 
        
        logger.info(f"{self.PROVIDER_NAME}: Disconnected. MSAL cache and keyring tokens cleared.")
        self.msal_app = None # Ensure msal_app is None after disconnect

    # --- Graph API specific methods (largely unchanged but rely on updated auth) ---

    def _graph_item_to_cloudfile(self, graph_item: Dict[str, Any], path_display_relative_to_app_root: str) -> CloudFileMetadata:
        is_folder = 'folder' in graph_item
        is_deleted = 'deleted' in graph_item

        item_id = graph_item['id']
        name = graph_item['name']
        rev = graph_item.get('eTag', 'unknown')
        size = graph_item.get('size', 0) if not is_folder else 0
        
        modified_time_str = graph_item.get('lastModifiedDateTime')
        modified_timestamp = datetime.now(timezone.utc).timestamp()
        if modified_time_str:
            try:
                dt_obj = datetime.fromisoformat(modified_time_str.replace('Z', '+00:00'))
                modified_timestamp = dt_obj.timestamp()
            except ValueError:
                logger.warning(f"Could not parse lastModifiedDateTime '{modified_time_str}' for item '{name}'. Using current time.")
        
        return CloudFileMetadata(
            id=item_id, name=name, path_display=path_display_relative_to_app_root,
            rev=str(rev), size=size, modified_timestamp=modified_timestamp,
            is_folder=is_folder, is_deleted=is_deleted
        )
    
    async def _make_graph_api_call(self, method: str, url_suffix: str, headers_extra: Optional[Dict[str,str]] = None, **kwargs) -> Optional[httpx.Response]:
        if not self._is_configured: 
            logger.error(f"{self.PROVIDER_NAME}: Service not configured. Cannot make Graph API call.")
            return None
        
        base_headers = await self._get_headers()
        if not base_headers:
            logger.error(f"{self.PROVIDER_NAME}: Cannot make Graph API call, authentication failed or token unavailable.")
            return None # AuthError should be raised by caller if this is critical path
        
        effective_headers = {**base_headers, **(headers_extra or {})}
        
        full_url = f"{self.graph_api_endpoint}{url_suffix}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client: # Default timeout for operations
                response = await client.request(method, full_url, headers=effective_headers, **kwargs)
            
            if 400 <= response.status_code < 600:
                 try: error_details = response.json()
                 except: error_details = response.text 
                 logger.error(f"{self.PROVIDER_NAME}: Graph API error {response.status_code} for {method} {url_suffix}: {error_details}")
                 # Consider raising specific exceptions for common errors like 401, 403, 404
                 if response.status_code == 401:
                     raise AuthError(f"Graph API Unauthorized (401): {error_details}", user_message="Your OneDrive session is invalid or expired. Please log in again.")
                 elif response.status_code == 403:
                     raise AuthError(f"Graph API Forbidden (403): {error_details}", user_message="You don't have permission for this OneDrive operation.")
                 response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx
            return response
        except httpx.HTTPStatusError as e: 
            # Logged above, re-raise if specific handling isn't done
            raise ServiceError(f"Graph API HTTP error: {e}", user_message="A OneDrive operation failed due to an HTTP error.") from e
        except httpx.RequestError as e:
            logger.error(f"{self.PROVIDER_NAME}: HTTP request error for {method} {url_suffix}: {e}", exc_info=True)
            raise ServiceError(f"OneDrive connection error: {e}", user_message="Could not connect to OneDrive. Please check your internet connection.") from e
        except Exception as e: # Catch-all for other unexpected errors
            logger.error(f"{self.PROVIDER_NAME}: Unexpected error for {method} {url_suffix}: {e}", exc_info=True)
            raise ServiceError(f"An unexpected error occurred with OneDrive: {e}", user_message="An unexpected error occurred with OneDrive.") from e


    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        try:
            response = await self._make_graph_api_call("GET", "/me?$select=id,displayName,mail,userPrincipalName")
            if response and response.status_code == 200:
                user_data = response.json()
                return {"id": user_data.get('id'), "name": user_data.get('displayName'),
                        "email": user_data.get('mail') or user_data.get('userPrincipalName'), "raw": user_data}
        except ServiceError as e: # Catch errors raised by _make_graph_api_call
             logger.error(f"{self.PROVIDER_NAME}: ServiceError fetching user info: {e.message}") # Use .message for user_message
        except Exception: pass # Already logged by _make_graph_api_call for unexpected
        return None

    def _get_graph_path_suffix(self, path_relative_to_app_root: str) -> str:
        full_path_in_drive = self.get_full_cloud_path(path_relative_to_app_root)
        if not full_path_in_drive or full_path_in_drive == "/": 
            # If full_path_in_drive is effectively root, suffix should be empty for /me/drive/root
            # or ":/" for /me/drive/root:/ (which means root content)
            # For /children, an empty suffix for root is fine.
            # For specific item at root, it's /me/drive/root (no suffix)
            # Let's make it so that empty path_relative_to_app_root -> "" for /me/drive/root
            # and "foo" -> ":/foo:"
            return "" if not path_relative_to_app_root.strip('/') else f":/{quote(full_path_in_drive.lstrip('/'))}:"
        return f":/{quote(full_path_in_drive.lstrip('/'))}:" 

    async def list_folder(self, folder_path: str, recursive: bool = False) -> AsyncGenerator[CloudFileMetadata, None]:
        graph_path_suffix = self._get_graph_path_suffix(folder_path)
        # If graph_path_suffix is empty, it means list root. If it ends with ':', it's a folder path.
        url_suffix = f"/me/drive/root{graph_path_suffix}/children?$select=id,name,folder,file,size,lastModifiedDateTime,eTag,deleted"
        next_link = None
        while True:
            current_url = next_link if next_link else f"{self.graph_api_endpoint}{url_suffix}"
            api_call_url_suffix = current_url.replace(self.graph_api_endpoint, "")
            try:
                response = await self._make_graph_api_call("GET", api_call_url_suffix)
                if not response or response.status_code != 200: break
                data = response.json()
                for item in data.get('value', []):
                    item_rel_path = str(Path(folder_path) / item['name'])
                    yield self._graph_item_to_cloudfile(item, item_rel_path)
                    if recursive and 'folder' in item:
                        async for sub_item in self.list_folder(item_rel_path, recursive=True): yield sub_item
                next_link = data.get('@odata.nextLink')
                if not next_link: break
            except ServiceError as e:
                logger.error(f"{self.PROVIDER_NAME}: ServiceError listing folder '{folder_path}': {e.message}")
                break
            except Exception as e: # Catch any other unexpected error from _make_graph_api_call
                logger.error(f"{self.PROVIDER_NAME}: Unexpected error listing folder '{folder_path}': {e}", exc_info=True)
                break


    async def get_file_metadata(self, cloud_file_path: str) -> Optional[CloudFileMetadata]:
        graph_path_suffix = self._get_graph_path_suffix(cloud_file_path)
        # If graph_path_suffix is empty, it means get metadata for root.
        url_suffix = f"/me/drive/root{graph_path_suffix}?$select=id,name,folder,file,size,lastModifiedDateTime,eTag,deleted"
        
        try:
            response = await self._make_graph_api_call("GET", url_suffix)
            if response and response.status_code == 200:
                # If cloud_file_path was empty or "/", it's the root. Display name might be from response.
                # For consistency, use the provided cloud_file_path for path_display if it was given.
                path_display = cloud_file_path if cloud_file_path else response.json().get('name', '') # Fallback to item name if path is empty (root)
                return self._graph_item_to_cloudfile(response.json(), path_display)
        except httpx.HTTPStatusError as e: # Raised by _make_graph_api_call for 4xx/5xx
            if e.response.status_code == 404: 
                logger.debug(f"{self.PROVIDER_NAME}: Metadata not found (404) for '{cloud_file_path}'. Graph path: {graph_path_suffix}")
            # Other errors already logged by _make_graph_api_call
        except ServiceError as e:
            logger.error(f"{self.PROVIDER_NAME}: ServiceError getting metadata for '{cloud_file_path}': {e.message}")
        except Exception: pass # Already logged by _make_graph_api_call for unexpected
        return None

    async def create_folder(self, cloud_folder_path: str) -> bool:
        if not cloud_folder_path or cloud_folder_path == ".": 
            return await self.ensure_app_root_folder_exists()

        parent_path = str(Path(cloud_folder_path).parent)
        folder_name = Path(cloud_folder_path).name
        
        # Determine parent graph suffix. If parent_path is "." or "", it's the app root.
        # _get_graph_path_suffix handles empty path correctly for app root.
        parent_graph_suffix = self._get_graph_path_suffix(parent_path if parent_path != "." else "")
        url_suffix = f"/me/drive/root{parent_graph_suffix}/children"
        
        request_body = {"name": folder_name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
        try:
            response = await self._make_graph_api_call("POST", url_suffix, json=request_body)
            return response is not None and response.status_code == 201
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409: 
                logger.info(f"{self.PROVIDER_NAME}: Folder '{cloud_folder_path}' likely already exists (conflict 409). Verifying.")
                meta = await self.get_file_metadata(cloud_folder_path) 
                return meta is not None and meta.is_folder
            # Other errors already logged by _make_graph_api_call
        except ServiceError as e:
            logger.error(f"{self.PROVIDER_NAME}: ServiceError creating folder '{cloud_folder_path}': {e.message}")
        except Exception: pass # Already logged
        return False

    async def ensure_app_root_folder_exists(self) -> bool:
        if not self._is_configured : 
            logger.error(f"{self.PROVIDER_NAME}: Cannot ensure app root folder, service not configured.")
            return False
        if not self.root_folder_path or self.root_folder_path == "/": # Root is "/"
            logger.info(f"{self.PROVIDER_NAME}: App root is drive root ('/'), assumed to exist.")
            return True

        logger.info(f"{self.PROVIDER_NAME}: Ensuring app root folder '{self.root_folder_path}' exists.")
        
        path_segments = [s for s in self.root_folder_path.strip("/").split("/") if s]
        current_path_from_root = "" 
        parent_graph_api_path_suffix = "" 

        for segment_name in path_segments:
            current_path_from_root = f"{current_path_from_root}/{segment_name}" if current_path_from_root else segment_name
            segment_graph_suffix = f":/{quote(current_path_from_root)}:"
            
            url_get_meta = f"/me/drive/root{segment_graph_suffix}?$select=id,name,folder"
            
            item_exists_as_folder = False
            try:
                response = await self._make_graph_api_call("GET", url_get_meta)
                if response and response.status_code == 200:
                    item_data = response.json()
                    if 'folder' in item_data:
                        item_exists_as_folder = True
                        logger.debug(f"Segment '{segment_name}' at '{current_path_from_root}' exists.")
                    else:
                        logger.error(f"Path '{current_path_from_root}' exists but is a file, cannot create app root.")
                        return False
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404: # Not a "not found" error
                    logger.error(f"Error checking segment '{current_path_from_root}': {e}") # Already logged by _make_graph_api_call
                    return False 
            except ServiceError as e: # Catch ServiceErrors from _make_graph_api_call
                logger.error(f"ServiceError checking segment '{current_path_from_root}': {e.message}")
                return False
            except Exception as e: 
                logger.error(f"Unexpected error checking segment '{current_path_from_root}': {e}") # Already logged by _make_graph_api_call
                return False

            if not item_exists_as_folder:
                logger.info(f"Segment '{segment_name}' at path '{current_path_from_root}' not found. Creating.")
                create_in_url_suffix = f"/me/drive/root{parent_graph_api_path_suffix}/children"
                request_body = {"name": segment_name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
                try:
                    response_create = await self._make_graph_api_call("POST", create_in_url_suffix, json=request_body)
                    if not (response_create and response_create.status_code == 201):
                        # Error already logged by _make_graph_api_call
                        return False
                    logger.info(f"Created segment '{segment_name}' at path '{current_path_from_root}'.")
                except ServiceError as e: # Catch ServiceErrors from _make_graph_api_call
                    logger.error(f"ServiceError creating segment '{segment_name}': {e.message}")
                    return False
                except Exception as e:
                    logger.error(f"Exception creating segment '{segment_name}': {e}") # Already logged
                    return False
            
            parent_graph_api_path_suffix = segment_graph_suffix

        logger.info(f"App root folder '{self.root_folder_path}' ensured.")
        return True

    async def download_file_content(self, cloud_file_path: str) -> Optional[bytes]:
        graph_path_suffix = self._get_graph_path_suffix(cloud_file_path)
        url_suffix = f"/me/drive/root{graph_path_suffix}/content"
        try:
            response = await self._make_graph_api_call("GET", url_suffix)
            if response and response.status_code == 200: return response.content
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404: logger.debug(f"{self.PROVIDER_NAME}: File content not found (404) for '{cloud_file_path}'.")
        except ServiceError as e:
             logger.error(f"{self.PROVIDER_NAME}: ServiceError downloading file content for '{cloud_file_path}': {e.message}")
        return None

    async def download_file(self, cloud_file_path: str, local_target_path: Path) -> bool:
        content = await self.download_file_content(cloud_file_path)
        if content is None: return False
        try:
            local_target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_target_path, 'wb') as f: f.write(content)
            logger.info(f"Downloaded '{cloud_file_path}' to '{local_target_path}'")
            return True
        except IOError as e:
            logger.error(f"Failed to write to {local_target_path}: {e}")
            return False

    async def upload_file_content(self, content_bytes: bytes, cloud_target_folder: str, cloud_file_name: str) -> Optional[CloudFileMetadata]:
        target_file_rel_path = str(Path(cloud_target_folder) / cloud_file_name)
        graph_path_suffix = self._get_graph_path_suffix(target_file_rel_path)
        
        headers_override = {"Content-Type": "application/octet-stream"}
        if len(content_bytes) > SIMPLE_UPLOAD_MAX_SIZE_BYTES: 
            session_url_suffix = f"/me/drive/root{graph_path_suffix}/createUploadSession"
            conflict_behavior = "replace" 
            session_body = {"item": {"@microsoft.graph.conflictBehavior": conflict_behavior, "name": cloud_file_name}} 
            try:
                session_response = await self._make_graph_api_call("POST", session_url_suffix, json=session_body)
                if not (session_response and session_response.status_code == 200):
                    logger.error(f"Failed to create upload session for '{target_file_rel_path}'.")
                    return None
                upload_session_data = session_response.json()
                upload_url = upload_session_data.get("uploadUrl")
                if not upload_url:
                    logger.error(f"No uploadUrl in session response for '{target_file_rel_path}'.")
                    return None
                
                headers_upload = {"Content-Length": str(len(content_bytes)), "Content-Range": f"bytes 0-{len(content_bytes)-1}/{len(content_bytes)}"}
                async with httpx.AsyncClient(timeout=None) as client: 
                    response_upload = await client.put(upload_url, content=content_bytes, headers=headers_upload)
                
                if response_upload and (response_upload.status_code == 201 or response_upload.status_code == 200):
                    logger.info(f"Resumable upload successful for '{target_file_rel_path}'.")
                    return self._graph_item_to_cloudfile(response_upload.json(), target_file_rel_path)
                else:
                    logger.error(f"Resumable upload failed for '{target_file_rel_path}'. Status: {response_upload.status_code if response_upload else 'No response'}")
                    return None
            except ServiceError as e:
                logger.error(f"ServiceError during resumable upload for '{target_file_rel_path}': {e.message}", exc_info=True)
            except Exception as e:
                logger.error(f"Exception during resumable upload for '{target_file_rel_path}': {e}", exc_info=True)
            return None
        else: # Simple PUT
            url_suffix = f"/me/drive/root{graph_path_suffix}/content?@microsoft.graph.conflictBehavior=replace"
            try:
                response = await self._make_graph_api_call("PUT", url_suffix, content=content_bytes, headers_extra=headers_override)
                if response and (response.status_code == 201 or response.status_code == 200):
                    return self._graph_item_to_cloudfile(response.json(), target_file_rel_path)
            except ServiceError as e:
                logger.error(f"{self.PROVIDER_NAME}: ServiceError uploading content as '{cloud_file_name}': {e.message}")
            except Exception: pass 
        return None
        
    async def upload_file(self, local_file_path: Path, cloud_target_folder: str, cloud_file_name: Optional[str] = None) -> Optional[CloudFileMetadata]:
        if not local_file_path.is_file(): 
            logger.error(f"Local file {local_file_path} not found for upload.")
            return None
        file_name_to_use = cloud_file_name or local_file_path.name
        try:
            with open(local_file_path, 'rb') as f: content_bytes = f.read()
            return await self.upload_file_content(content_bytes, cloud_target_folder, file_name_to_use)
        except IOError as e:
            logger.error(f"Error reading local file {local_file_path}: {e}")
            return None

    async def delete_file(self, cloud_file_path: str) -> bool:
        graph_path_suffix = self._get_graph_path_suffix(cloud_file_path)
        
        if not graph_path_suffix.strip(':/') and (not cloud_file_path or cloud_file_path == "." or cloud_file_path == "/"):
            if self.root_folder_path == "/" and (not cloud_file_path or cloud_file_path == "." or cloud_file_path == "/"):
                 logger.error(f"{self.PROVIDER_NAME}: Deleting the drive root ('/') is not allowed. Path: '{cloud_file_path}'")
                 return False
            
        url_suffix = f"/me/drive/root{graph_path_suffix}"
        try:
            response = await self._make_graph_api_call("DELETE", url_suffix)
            if response and (response.status_code == 204 or response.status_code == 404):
                if response.status_code == 404: 
                    logger.warning(f"{self.PROVIDER_NAME}: Item '{cloud_file_path}' (Graph path {graph_path_suffix}) not found (already deleted?).")
                else:
                    logger.info(f"{self.PROVIDER_NAME}: Successfully deleted item '{cloud_file_path}' (Graph path {graph_path_suffix}).")
                return True
            return False 
        except httpx.HTTPStatusError as e: 
             if e.response.status_code == 404: 
                 logger.warning(f"{self.PROVIDER_NAME}: Item '{cloud_file_path}' (Graph path {graph_path_suffix}) not found on delete (404 via exception).")
                 return True 
        except ServiceError as e:
            logger.error(f"{self.PROVIDER_NAME}: ServiceError deleting item '{cloud_file_path}' (Graph path {graph_path_suffix}): {e.message}")
        except Exception as e: 
            logger.error(f"{self.PROVIDER_NAME}: Unexpected error deleting item '{cloud_file_path}' (Graph path {graph_path_suffix}): {e}", exc_info=True)
        return False
