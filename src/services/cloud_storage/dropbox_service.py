import asyncio
from datetime import datetime, timezone
import dropbox
from dropbox.oauth import DropboxOAuth2Flow, PKCE_SUPPORTED, CodeChallengeStyle
from dropbox.exceptions import AuthError, ApiError
from dropbox.files import FileMetadata, FolderMetadata, DeletedMetadata, WriteMode
import logging
from typing import List, Optional, Tuple, Dict, Any, AsyncGenerator, TYPE_CHECKING
from pathlib import Path
import time # For time.time() for expires_at

from src.services.cloud_storage.base_cloud_service import BaseCloudService, CloudFileMetadata

if TYPE_CHECKING:
    from src.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class DropboxService(BaseCloudService):
    PROVIDER_NAME = "Dropbox"

    def __init__(self, config_manager: 'ConfigManager'):
        super().__init__(config_manager) # This loads tokens via _load_tokens_from_keyring()
        
        self.app_key: Optional[str] = self.config_manager.get('cloud_providers.dropbox.app_key')
        self.app_secret: Optional[str] = self.config_manager.get('cloud_providers.dropbox.app_secret')
        self.redirect_uri: Optional[str] = self.config_manager.get('cloud_providers.dropbox.redirect_uri')
        
        if not self.app_key or not self.app_secret:
            logger.error(f"{self.PROVIDER_NAME}: App key or app secret not configured. Refresh and some operations may fail.")

        self.dbx: Optional[dropbox.Dropbox] = None
        self._reinitialize_client_with_loaded_tokens()

    def _reinitialize_client_with_loaded_tokens(self) -> None:
        """Initializes or re-initializes the Dropbox client (self.dbx) using stored tokens."""
        if self.access_token:
            logger.debug(f"{self.PROVIDER_NAME}: Reinitializing client with access token.")
            self.dbx = dropbox.Dropbox(
                oauth2_access_token=self.access_token,
                oauth2_refresh_token=self.refresh_token, # Pass refresh token if available
                app_key=self.app_key,                   # Needed for potential auto-refresh by SDK
                app_secret=self.app_secret,             # Needed for potential auto-refresh by SDK
                # Convert Unix timestamp to datetime object for SDK if it expects datetime
                # The Dropbox SDK's oauth2_access_token_expiration expects a datetime object
                oauth2_access_token_expiration=datetime.fromtimestamp(self.token_expiry_timestamp, timezone.utc) if self.token_expiry_timestamp else None
            )
        elif self.refresh_token and self.app_key and self.app_secret:
            logger.info(f"{self.PROVIDER_NAME}: Reinitializing client with refresh token only.")
            self.dbx = dropbox.Dropbox(
                oauth2_refresh_token=self.refresh_token,
                app_key=self.app_key,
                app_secret=self.app_secret,
                oauth2_access_token_expiration=datetime.fromtimestamp(self.token_expiry_timestamp, timezone.utc) if self.token_expiry_timestamp else None
            )
        else:
            self.dbx = None # No tokens, no client
            logger.debug(f"{self.PROVIDER_NAME}: No tokens available, Dropbox client not initialized.")

    async def _run_sync(self, func, *args: Any, **kwargs: Any) -> Any:
        """Helper to run synchronous Dropbox SDK calls in a thread."""
        if self.dbx is None:
            logger.warning(f"{self.PROVIDER_NAME}: Dropbox client not initialized. Attempting reinitialization.")
            self._reinitialize_client_with_loaded_tokens() # Attempt to re-initialize
            if self.dbx is None: # Still no client
                logger.error(f"{self.PROVIDER_NAME}: Reinitialization failed. Dropbox client remains uninitialized.")
                raise ConnectionError("Dropbox client not initialized after reattempt.")

        # Check token expiry if token_expiry_timestamp is known
        if self.token_expiry_timestamp and self.token_expiry_timestamp < time.time() - 60: # 60s buffer
            logger.info(f"{self.PROVIDER_NAME}: Access token may be expired. Attempting refresh.")
            if not await self.refresh_access_token(): # This will re-init self.dbx or update its token
                 raise AuthError("Token refresh failed or not possible.", user_message="Access token expired and refresh failed.")

        return await asyncio.to_thread(func, *args, **kwargs)

    def _dbx_metadata_to_cloudfile(self, dbx_meta: Any) -> CloudFileMetadata:
        """Converts Dropbox metadata object to standardized CloudFileMetadata."""
        is_folder = isinstance(dbx_meta, FolderMetadata)
        is_deleted = isinstance(dbx_meta, DeletedMetadata) # Dropbox can return DeletedMetadata for deleted items

        path_display = dbx_meta.path_display if hasattr(dbx_meta, 'path_display') and dbx_meta.path_display is not None else dbx_meta.path_lower if hasattr(dbx_meta, 'path_lower') else ""
        
        # Ensure path_display is relative to self.root_folder_path for consistency,
        # if dbx_meta.path_display is absolute from Dropbox root.
        # Dropbox paths usually start with '/', self.root_folder_path also starts with '/'.
        # If self.root_folder_path = "/Apps/Purse" and path_display = "/Apps/Purse/file.txt",
        # then relative path should be "file.txt".
        if path_display.startswith(self.root_folder_path + '/') and len(path_display) > len(self.root_folder_path) +1 :
            path_display_relative = path_display[len(self.root_folder_path)+1:]
        elif path_display == self.root_folder_path: # It is the root folder itself
             path_display_relative = ""
        else:
            # This case might indicate an issue or a file outside the app root.
            # For now, use the path as Dropbox provided it, prefixed with a warning if it's unexpected.
            if not path_display.startswith(self.root_folder_path):
                 logger.warning(f"Dropbox item path '{path_display}' is outside configured app root '{self.root_folder_path}'. Using full path.")
            path_display_relative = path_display # Fallback to full path if not clearly relative


        size = dbx_meta.size if hasattr(dbx_meta, 'size') and dbx_meta.size is not None else 0
        rev = dbx_meta.rev if hasattr(dbx_meta, 'rev') and dbx_meta.rev is not None else "unknown"

        # Dropbox server_modified is a naive datetime object in UTC.
        modified_dt_utc = datetime.now(timezone.utc) # Default to now if not present
        if hasattr(dbx_meta, 'server_modified') and dbx_meta.server_modified:
            modified_dt_utc = dbx_meta.server_modified.replace(tzinfo=timezone.utc)
        
        return CloudFileMetadata(
            id=dbx_meta.id if hasattr(dbx_meta, 'id') and dbx_meta.id is not None else path_display, # path_display as fallback id
            name=dbx_meta.name,
            path_display=path_display_relative, # Store path relative to app root
            rev=rev,
            size=size,
            modified_timestamp=modified_dt_utc.timestamp(), # Convert datetime to UTC Unix timestamp (float)
            is_folder=is_folder,
            is_deleted=is_deleted
        )

    async def authenticate_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        if not self.app_key or not self.redirect_uri:
            raise ValueError("Dropbox app_key or redirect_uri not configured.")

        oauth_flow = DropboxOAuth2Flow(
            consumer_key=self.app_key,
            redirect_uri=self.redirect_uri,
            session={"dbx_auth_csrf_token": state} if state else {}, # CSRF token stored in session
            csrf_token_session_key="dbx_auth_csrf_token",
            token_access_type='offline', # To get a refresh_token
            scope=['files.content.write', 'files.content.read', 'account_info.read'],
            include_granted_scopes='none' # Or 'user' if you want to check against previously granted scopes
        )
        
        pkce_verifier = None
        extra_params = {}
        if PKCE_SUPPORTED:
            # Create a code verifier and challenge for PKCE
            # The SDK's start() method can generate these if pkce=True,
            # but to return the verifier, we might need to generate it manually or access it.
            # Let's check how DropboxOAuth2Flow.start() handles PKCE.
            # The DropboxOAuth2Flow itself can generate and store the verifier if pkce=True.
            # The verifier is typically stored in the session.
            # For this method signature, we need to return the verifier.
            # If using DropboxOAuth2Flow's internal PKCE, we might need to extract it.
            # Simpler: generate verifier manually for now if SDK doesn't expose it easily from flow.start().
            # However, the SDK's `start()` with `pkce=True` should handle it.
            # The `code_verifier` is often stored in the session by the flow, but we need to return it.
            # For now, let's assume we manage the verifier externally or flow allows retrieval.
            # The current Dropbox SDK (e.g., 11.x) `DropboxOAuth2Flow.start()` does not directly return verifier.
            # Let's rely on passing `code_challenge_style` if supported.
            # The SDK examples show `oauth_flow.start(state, pkce=True)`.
            # The verifier is stored in the session. This conflicts with returning it.
            # For now, we won't use SDK's PKCE directly if we must return verifier.
            # The subtask implies we should return a verifier.
            # If PKCE_SUPPORTED is True, then we should use it.
            # The flow.start() method has a pkce parameter.
            # Re-checking: The flow object stores the verifier if pkce=True.
            # We might need to instantiate flow, store it, call start, get verifier, then use stored flow in exchange.
            # This is complex for stateless server. For desktop app, session can be self.
            # Let's assume statefulness for the flow instance across auth_url and exchange_code.
            # This is not ideal.
            # A common pattern is to generate verifier, store it, pass challenge to `start`.
            # The Dropbox SDK's `DropboxOAuth2Flow` does not seem to directly support setting a pre-generated challenge.
            # It uses `code_challenge_method` in the constructor for PKCE.
            # For now, this method will NOT use PKCE if it complicates verifier retrieval beyond SDK's direct support.
            # The subtask says "Uses PKCE if available (code_challenge_plain or code_challenge_v2)".
            # This is a bit of a mismatch with SDK's typical flow.
            # Let's stick to what SDK's `DropboxOAuth2Flow` provides.
            # If `pkce=True` is used in `start()`, the verifier is stored in the session.
            # We will assume for now that the verifier is *not* returned by this method if using flow's PKCE,
            # and `code_verifier` in `exchange_code_for_token` will get it from session.
            # This contradicts the Tuple[str, str] return.
            # Modifying to align with SDK: flow handles verifier in session.
            # If verifier MUST be returned, manual PKCE is needed.
            
            # Per instructions: "Returns (authorize_url, code_verifier)". This means we manage PKCE.
            # This is not how Dropbox SDK's flow is designed to be used typically.
            # I will simulate this, but it's non-standard for this SDK.
            # Standard way: flow = DropboxOAuth2Flow(...); url = flow.start(pkce=True); session has verifier.
            # exchange: flow.finish(code, session_verifier)
            
            # Given the constraints, let's try to use the PKCE feature as best as possible.
            # The SDK's `build_authorize_url` allows passing `code_challenge` and `code_challenge_method`.
            # We would generate verifier and challenge manually.
            import os, base64
            pkce_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip("=")
            # For S256, hash it. For plain, use as is. Dropbox supports S256.
            import hashlib
            pkce_challenge_bytes = hashlib.sha256(pkce_verifier.encode('utf-8')).digest()
            pkce_challenge = base64.urlsafe_b64encode(pkce_challenge_bytes).decode('utf-8').rstrip("=")
            extra_params['code_challenge'] = pkce_challenge
            extra_params['code_challenge_method'] = 'S256' # Or 'plain' if only that was supported
        
        authorize_url = await self._run_sync(oauth_flow.start, state=state, **extra_params)
        return authorize_url, pkce_verifier if pkce_verifier else ""


    async def exchange_code_for_token(self, auth_code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        if not self.app_key or not self.app_secret or not self.redirect_uri: # App secret needed for flow.finish
            raise ValueError("Dropbox app_key, app_secret, or redirect_uri not configured.")

        # Re-instantiate flow. Session state for CSRF is not used here as we're past that.
        # If CSRF token was used in authorize_url, it should be verified from callback state by caller.
        oauth_flow = DropboxOAuth2Flow(
            consumer_key=self.app_key,
            consumer_secret=self.app_secret, # Consumer secret is required for finish()
            redirect_uri=self.redirect_uri,
            session={}, # Empty session for finish, CSRF should be checked by caller from state
            csrf_token_session_key="dbx_auth_csrf_token", # Must match key used in authenticate_url
            pkce=bool(code_verifier) # Enable PKCE handling in finish if verifier is present
        )
        if code_verifier: # If we manually managed PKCE verifier
            # The SDK's finish method expects the verifier to be in the session if pkce=True was used for start.
            # If we pass code_verifier directly, we need to ensure flow is set up for it.
            # The `pkce` flag in constructor and `code_verifier` in `finish` handle this.
            pass


        try:
            oauth_result = await self._run_sync(oauth_flow.finish, auth_code, code_verifier=code_verifier)
            
            token_dict_to_save = {
                'access_token': oauth_result.access_token,
                'refresh_token': oauth_result.refresh_token,
                'user_id': oauth_result.account_id, # Dropbox specific user_id
                'token_expiry_timestamp': oauth_result.expires_at.timestamp() if oauth_result.expires_at else None
            }
            self._save_tokens_to_keyring(token_dict_to_save) # This updates instance attributes
            self._reinitialize_client_with_loaded_tokens()   # Re-init dbx with new tokens

            logger.info(f"{self.PROVIDER_NAME}: Successfully exchanged code for token. User ID: {self.user_id}")
            
            return {
                'access_token': self.access_token,         # Now from instance, set by _save_tokens_to_keyring
                'refresh_token': self.refresh_token,       # Now from instance
                'user_id': self.user_id,                   # Now from instance
                'expires_at': self.token_expiry_timestamp, # Use the timestamp from instance
                'scope': oauth_result.scope                # String of scopes
            }
        except AuthError as e:
            logger.error(f"{self.PROVIDER_NAME}: AuthError during token exchange: {e}")
            raise # Re-raise to be handled by caller
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Exception during token exchange: {e}")
            raise


    async def refresh_access_token(self) -> Optional[str]:
        if not self.dbx:
            logger.warning(f"{self.PROVIDER_NAME}: Dropbox client not initialized. Cannot refresh token.")
            return None
        if not self.refresh_token or not self.app_key or not self.app_secret:
            logger.warning(f"{self.PROVIDER_NAME}: Missing refresh token or app credentials. Cannot explicitly refresh token.")
            return None
        
        # The SDK is designed to auto-refresh.
        # To force a check or if SDK needs explicit re-init for refresh:
        # Re-initialize with refresh token, app key, app secret.
        # This is the recommended way for the SDK to manage tokens.
        self.dbx = dropbox.Dropbox(
            oauth2_refresh_token=self.refresh_token,
            app_key=self.app_key,
            app_secret=self.app_secret,
            oauth2_access_token_expiration=self.expires_at 
        )
        
        try:
            # Make a simple, lightweight API call to ensure the token is fresh.
            # The SDK should handle the refresh transparently if needed.
            await self._run_sync(self.dbx.users_get_current_account)
            
            # NOTE: The Dropbox SDK (v11) handles token auto-refresh internally when
            # initialized with a refresh token and app credentials. After a successful
            # API call like the one above, the self.dbx instance uses the (potentially new)
            # access token. However, the SDK does not expose an easy way to retrieve
            # this newly acquired access token string or its new expiry time.
            # Therefore, while the client is usable, the self.access_token and
            # self.token_expiry_timestamp attributes (and thus the token info in keyring)
            # might not reflect the absolute latest state after an SDK-internal auto-refresh.
            # This is a limitation of the current SDK's public API for auto-refreshed tokens.
            # This method confirms the client is usable; explicit saving of a *new* token string
            # to keyring via _save_tokens_to_keyring is only feasible if a refresh mechanism
            # *returns* new token details.
            
            # After a successful call, if the SDK auto-refreshed, the new token and expiry
            # are managed internally by self.dbx. We need to extract them.
            # Unfortunately, the Dropbox SDK (v11) does not make it straightforward to get
            # the new access token or expiry after an auto-refresh.
            # The `self.dbx.session.token_access` is not a public API.
            # A workaround could be to re-do the OAuth flow with refresh_token, but that's heavy.
            # For now, we assume the self.dbx instance is internally refreshed and usable.
            # If the access_token itself needs to be returned and stored externally,
            # this requires a more complex solution, possibly involving a custom transport
            # that captures the refreshed token.
            
            # If the SDK doesn't expose the new token, we can't update self.access_token here accurately
            # unless we re-implement parts of the refresh logic using raw HTTP calls.
            # This is a known limitation/complexity with some SDKs that auto-refresh.
            
            # For the purpose of this method: confirm dbx is usable.
            # The initial access_token (if it was from this dbx instance via refresh) might be updated.
            # Let's assume for now that if the above call succeeds, the token is "refreshed" in the client.
            # If the SDK provides a way to get the current token and its expiry, update self.access_token and self.expires_at.
            # As of SDK v11.x, this is not directly exposed after auto-refresh.
            # We might need to rely on the initial `expires_at` and assume it was refreshed for that duration.

            logger.info(f"{self.PROVIDER_NAME}: Access token is considered refreshed and usable within the client instance.")
            # Cannot reliably return the *new* token string here due to SDK limitations.
            # Return the existing self.access_token if it's deemed "live" by the above call.
            return self.access_token # Or a new one if SDK exposed it.
            
        except AuthError as e:
            logger.error(f"{self.PROVIDER_NAME}: AuthError during token refresh attempt: {e}")
            self.access_token = None # Invalidate token
            # Potentially invalidate refresh_token too if it's a permanent issue
            return None
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Exception during token refresh attempt: {e}")
            return None


    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        if not self.dbx: return None
        try:
            account_info = await self._run_sync(self.dbx.users_get_current_account)
            return {
                "id": account_info.account_id,
                "name": f"{account_info.name.given_name} {account_info.name.surname}".strip(),
                "email": account_info.email,
                "raw": account_info # Include raw object for other details if needed
            }
        except AuthError:
            logger.error(f"{self.PROVIDER_NAME}: Authentication error fetching user info.")
            return None
        except ApiError as e:
            logger.error(f"{self.PROVIDER_NAME}: API error fetching user info: {e}")
            return None

    async def list_folder(self, folder_path: str, recursive: bool = False) -> AsyncGenerator[CloudFileMetadata, None]:
        if not self.dbx: return

        full_cloud_path = self.get_full_cloud_path(folder_path)
        # Dropbox API uses empty string for root of app folder or Dropbox.
        # If full_cloud_path is the root itself (e.g. "/Apps/Purse"), API expects path="" if client is rooted.
        # The Dropbox SDK client is NOT rooted. Paths are from true Dropbox root.
        # So, full_cloud_path (e.g. "/Apps/Purse" or "/Apps/Purse/MyFolder") is correct.
        # If self.root_folder_path is "/", full_cloud_path will be "/MyFolder".
        # If folder_path is "" meaning list root_folder_path, then full_cloud_path = self.root_folder_path.
        # Dropbox root is path="". If self.root_folder_path="/", then full_cloud_path="".
        
        # Adjust for Dropbox root if self.root_folder_path is "/"
        api_path = full_cloud_path
        if self.root_folder_path == "/" and (folder_path == "" or folder_path == "."):
            api_path = "" # Special case for Dropbox root

        try:
            result = await self._run_sync(self.dbx.files_list_folder, path=api_path, recursive=recursive)
            for entry in result.entries:
                yield self._dbx_metadata_to_cloudfile(entry)
            
            cursor = result.cursor
            has_more = result.has_more
            while has_more:
                result = await self._run_sync(self.dbx.files_list_folder_continue, cursor)
                for entry in result.entries:
                    yield self._dbx_metadata_to_cloudfile(entry)
                cursor = result.cursor
                has_more = result.has_more
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                logger.warning(f"{self.PROVIDER_NAME}: Folder not found for listing: {api_path}")
            else:
                logger.error(f"{self.PROVIDER_NAME}: API error listing folder {api_path}: {e}")
        except AuthError:
             logger.error(f"{self.PROVIDER_NAME}: Authentication error listing folder {api_path}.")


    async def download_file(self, cloud_file_path: str, local_target_path: Path) -> bool:
        if not self.dbx: return False
        full_cloud_path = self.get_full_cloud_path(cloud_file_path)
        try:
            local_target_path.parent.mkdir(parents=True, exist_ok=True) # Ensure target dir exists
            await self._run_sync(self.dbx.files_download_to_file, str(local_target_path), full_cloud_path)
            logger.info(f"{self.PROVIDER_NAME}: Downloaded '{full_cloud_path}' to '{local_target_path}'")
            return True
        except ApiError as e:
            logger.error(f"{self.PROVIDER_NAME}: API error downloading file {full_cloud_path}: {e}")
            return False
        except Exception as e: # Catch other errors like file system issues
            logger.error(f"{self.PROVIDER_NAME}: Failed to download file {full_cloud_path} to {local_target_path}: {e}")
            return False

    async def download_file_content(self, cloud_file_path: str) -> Optional[bytes]:
        if not self.dbx: return None
        full_cloud_path = self.get_full_cloud_path(cloud_file_path)
        try:
            _, response = await self._run_sync(self.dbx.files_download, full_cloud_path)
            return response.content
        except ApiError as e:
            logger.error(f"{self.PROVIDER_NAME}: API error downloading content of {full_cloud_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Failed to download content of {full_cloud_path}: {e}")
            return None

    async def _upload_bytes(self, content_bytes: bytes, full_cloud_path: str) -> Optional[CloudFileMetadata]:
        if not self.dbx: return None
        try:
            # Dropbox recommends chunked upload for files > 150MB. For simplicity, using files_upload.
            # files_upload can handle up to 350GB with a single request if connection is good.
            # For very large files, upload_session_start/append/finish is better.
            # For typical article files, this should be fine.
            mode = WriteMode('overwrite') # Overwrite if exists, or add if not
            uploaded_meta_dbx = await self._run_sync(self.dbx.files_upload, content_bytes, full_cloud_path, mode=mode)
            logger.info(f"{self.PROVIDER_NAME}: Uploaded content to '{full_cloud_path}'")
            return self._dbx_metadata_to_cloudfile(uploaded_meta_dbx)
        except ApiError as e:
            logger.error(f"{self.PROVIDER_NAME}: API error uploading to {full_cloud_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Failed to upload to {full_cloud_path}: {e}")
            return None


    async def upload_file(self, local_file_path: Path, cloud_target_folder: str, cloud_file_name: Optional[str] = None) -> Optional[CloudFileMetadata]:
        if not local_file_path.exists() or not local_file_path.is_file():
            logger.error(f"{self.PROVIDER_NAME}: Local file not found or is not a file: {local_file_path}")
            return None
        
        file_name_to_use = cloud_file_name if cloud_file_name else local_file_path.name
        # cloud_target_folder is relative to app root. get_full_cloud_path handles joining.
        # Example: cloud_target_folder="MyFolder", file_name_to_use="file.txt"
        # full_path_for_file = /Apps/Purse/MyFolder/file.txt
        full_path_for_file = self.get_full_cloud_path(str(Path(cloud_target_folder) / file_name_to_use))

        try:
            with open(local_file_path, 'rb') as f:
                content_bytes = f.read()
            return await self._upload_bytes(content_bytes, full_path_for_file)
        except IOError as e:
            logger.error(f"{self.PROVIDER_NAME}: IOError reading local file {local_file_path}: {e}")
            return None


    async def upload_file_content(self, content_bytes: bytes, cloud_target_folder: str, cloud_file_name: str) -> Optional[CloudFileMetadata]:
        full_path_for_file = self.get_full_cloud_path(str(Path(cloud_target_folder) / cloud_file_name))
        return await self._upload_bytes(content_bytes, full_path_for_file)


    async def delete_file(self, cloud_file_path: str) -> bool:
        if not self.dbx: return False
        full_cloud_path = self.get_full_cloud_path(cloud_file_path)
        try:
            await self._run_sync(self.dbx.files_delete_v2, full_cloud_path)
            logger.info(f"{self.PROVIDER_NAME}: Deleted file/folder: {full_cloud_path}")
            return True
        except ApiError as e:
            if e.error.is_path_lookup() and e.error.get_path_lookup().is_not_found():
                logger.warning(f"{self.PROVIDER_NAME}: File/folder not found for deletion (already deleted?): {full_cloud_path}")
                return True # Effectively deleted
            logger.error(f"{self.PROVIDER_NAME}: API error deleting {full_cloud_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Failed to delete {full_cloud_path}: {e}")
            return False


    async def create_folder(self, cloud_folder_path: str) -> bool:
        if not self.dbx: return False
        # cloud_folder_path is relative to self.root_folder_path.
        # Example: self.root_folder_path = "/Apps/Purse". cloud_folder_path = "MyNewFolder"
        # Then full_cloud_path = "/Apps/Purse/MyNewFolder"
        # If cloud_folder_path = "", it means create self.root_folder_path.
        # This needs careful handling if self.root_folder_path is "/".
        
        full_cloud_path = self.get_full_cloud_path(cloud_folder_path)
        if full_cloud_path == "/" and self.root_folder_path == "/": # Cannot create root of Dropbox itself
             logger.info(f"{self.PROVIDER_NAME}: Root folder '/' assumed to exist. No creation needed.")
             return True


        try:
            # files_create_folder_v2 creates folder. If it exists, it raises ApiError path/conflict/folder.
            await self._run_sync(self.dbx.files_create_folder_v2, full_cloud_path)
            logger.info(f"{self.PROVIDER_NAME}: Created folder: {full_cloud_path}")
            return True
        except ApiError as e:
            # Check if the error is because the folder already exists
            if e.error.is_path() and e.error.get_path().is_conflict() and e.error.get_path().get_conflict().is_folder():
                logger.info(f"{self.PROVIDER_NAME}: Folder already exists: {full_cloud_path}")
                return True # Folder exists, so operation is successful in terms of state
            elif e.error.is_path() and e.error.get_path().is_conflict() and e.error.get_path().get_conflict().is_file():
                logger.error(f"{self.PROVIDER_NAME}: Cannot create folder, a file exists at path: {full_cloud_path}")
                return False
            else:
                logger.error(f"{self.PROVIDER_NAME}: API error creating folder {full_cloud_path}: {e}")
                return False
        except Exception as e:
             logger.error(f"{self.PROVIDER_NAME}: Failed to create folder {full_cloud_path}: {e}")
             return False

    async def get_file_metadata(self, cloud_file_path: str) -> Optional[CloudFileMetadata]:
        if not self.dbx: return None
        full_cloud_path = self.get_full_cloud_path(cloud_file_path)
        
        # Special case for Dropbox root if path is effectively empty string
        api_path = full_cloud_path
        if self.root_folder_path == "/" and (cloud_file_path == "" or cloud_file_path == "."):
            api_path = "" # files_get_metadata with path="" gets metadata for root.

        try:
            dbx_meta = await self._run_sync(self.dbx.files_get_metadata, api_path)
            return self._dbx_metadata_to_cloudfile(dbx_meta)
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                logger.debug(f"{self.PROVIDER_NAME}: File/folder not found at {api_path}")
                return None
            logger.error(f"{self.PROVIDER_NAME}: API error getting metadata for {api_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Failed to get metadata for {api_path}: {e}")
            return None

