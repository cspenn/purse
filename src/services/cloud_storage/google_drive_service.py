import asyncio
from datetime import datetime, timezone
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http
import google.auth.transport.requests
import google.auth.exceptions
import io
import logging
from typing import List, Optional, Tuple, Dict, Any, AsyncGenerator, TYPE_CHECKING
from pathlib import Path
import mimetypes # For guessing MIME type during upload

from purse.services.cloud_storage.base_cloud_service import BaseCloudService, CloudFileMetadata

if TYPE_CHECKING:
    from purse.config_manager import ConfigManager
    # Define Resource type alias for clarity, from googleapiclient.discovery.Resource
    Resource = Any 


logger = logging.getLogger(__name__)

# Google Drive's PKCE support is typically handled by the auth library by setting code_challenge_method.
# We don't need a separate PKCE_SUPPORTED flag like Dropbox.

class GoogleDriveService(BaseCloudService):
    PROVIDER_NAME = "GoogleDrive"

    def __init__(self, config_manager: 'ConfigManager'):
        super().__init__(config_manager) # This loads tokens via _load_tokens_from_keyring()

        # Load Google Drive specific configurations
        self.gdrive_client_id: Optional[str] = self.config_manager.get('cloud_providers.google_drive.client_id')
        self.gdrive_client_secret: Optional[str] = self.config_manager.get('cloud_providers.google_drive.client_secret')
        self.gdrive_token_uri: Optional[str] = self.config_manager.get('cloud_providers.google_drive.token_uri', 'https://oauth2.googleapis.com/token')
        self.gdrive_auth_uri: Optional[str] = self.config_manager.get('cloud_providers.google_drive.auth_uri', 'https://accounts.google.com/o/oauth2/auth')
        self.gdrive_redirect_uri: Optional[str] = self.config_manager.get('cloud_providers.google_drive.redirect_uri')
        self.gdrive_scopes: Optional[List[str]] = self.config_manager.get('cloud_providers.google_drive.scopes')

        if not all([self.gdrive_client_id, self.gdrive_client_secret, self.gdrive_redirect_uri, self.gdrive_scopes, self.gdrive_auth_uri, self.gdrive_token_uri]):
            logger.error(f"{self.PROVIDER_NAME}: Critical OAuth configuration missing (client_id, client_secret, redirect_uri, scopes, auth_uri, or token_uri).")
            # Consider raising an error or ensuring service methods fail gracefully.
        
        self.creds: Optional[google.oauth2.credentials.Credentials] = None
        self._drive_service_instance: Optional['Resource'] = None
        self._app_root_folder_id: Optional[str] = None # Cache for resolved app root folder ID
        self._current_oauth_flow_for_pkce: Optional[google_auth_oauthlib.flow.Flow] = None # For PKCE flow

        self._reinitialize_client_with_loaded_tokens()

    def _reinitialize_client_with_loaded_tokens(self) -> None:
        """Initializes or re-initializes self.creds and invalidates self._drive_service_instance based on loaded tokens."""
        if self.access_token: # self.access_token is now from keyring via BaseClass
            expiry_datetime = None
            if self.token_expiry_timestamp: # This is a float (Unix timestamp) from BaseClass
                try:
                    expiry_datetime = datetime.fromtimestamp(self.token_expiry_timestamp, timezone.utc)
                except ValueError:
                    logger.warning(f"{self.PROVIDER_NAME}: Could not parse token_expiry_timestamp: {self.token_expiry_timestamp}")

            # Ensure all necessary parts for Credentials object are available
            if not all([self.gdrive_client_id, self.gdrive_client_secret, self.gdrive_token_uri, self.gdrive_scopes]): # Added gdrive_scopes check
                 logger.error(f"{self.PROVIDER_NAME}: Cannot initialize credentials. OAuth client config (ID, secret, token URI, scopes) missing.")
                 self.creds = None
            else:
                try:
                    self.creds = google.oauth2.credentials.Credentials(
                        token=self.access_token,
                        refresh_token=self.refresh_token, # From BaseClass
                        token_uri=self.gdrive_token_uri, 
                        client_id=self.gdrive_client_id, 
                        client_secret=self.gdrive_client_secret, 
                        scopes=self.gdrive_scopes, 
                        expiry=expiry_datetime
                    )
                    logger.info(f"{self.PROVIDER_NAME}: Credentials object created/updated from loaded tokens.")
                except Exception as e: # Catch potential errors during Credentials creation
                    logger.error(f"{self.PROVIDER_NAME}: Error creating Credentials object: {e}", exc_info=True)
                    self.creds = None
        else:
            self.creds = None
            logger.info(f"{self.PROVIDER_NAME}: No access token found, credentials not configured.")

        self._drive_service_instance = None # Invalidate service client, will be rebuilt on demand by _get_drive_service()
        self._app_root_folder_id = None # Also invalidate cached app root ID as creds change might mean different user/root

    async def _get_drive_service(self) -> Optional['Resource']:
        if self._drive_service_instance:
            if self.creds and (self.creds.valid or (self.creds.expired and self.creds.refresh_token)):
                 pass 
            else: 
                logger.warning(f"{self.PROVIDER_NAME}: Credentials invalid or not refreshable. Service instance may be stale.")
                # Don't return None yet, let it try to rebuild if creds are bad.
            return self._drive_service_instance # Return cached instance if available, even if creds might be stale (will be checked below)

        # Try to ensure creds are valid before building service
        if not self.creds:
            logger.info(f"{self.PROVIDER_NAME}: No credentials object. Attempting to reinitialize.")
            self._reinitialize_client_with_loaded_tokens() # Try to build from keyring if possible
            if not self.creds:
                logger.error(f"{self.PROVIDER_NAME}: No credentials available after reinitialization attempt. Cannot build Drive service.")
                return None

        if not self.creds.valid:
            if self.creds.expired and self.creds.refresh_token:
                logger.info(f"{self.PROVIDER_NAME}: Credentials expired, attempting refresh.")
                if not await self.refresh_access_token(): # refresh_access_token now handles _save_tokens & _reinitialize_client
                    logger.error(f"{self.PROVIDER_NAME}: Token refresh failed. Cannot build Drive service.")
                    # self._delete_tokens_from_keyring() called by refresh_access_token on RefreshError
                    return None
                # After successful refresh, self.creds should be updated and valid by _reinitialize_client_with_loaded_tokens
                if not self.creds or not self.creds.valid: # Check again
                    logger.error(f"{self.PROVIDER_NAME}: Credentials still not valid after refresh attempt.")
                    return None
            else:
                logger.error(f"{self.PROVIDER_NAME}: Credentials not valid and no refresh token available. Cannot build Drive service.")
                # Potentially stale tokens if loaded from keyring but are invalid and not refreshable
                if not self.creds.refresh_token: # if no refresh token, these tokens are useless
                    self._delete_tokens_from_keyring()
                return None
        
        try:
            # Using static_discovery=False is recommended for dynamic environments / long-running apps.
            # cache_discovery=False is also good practice if not using Google's API discovery caching.
            # This is a synchronous call, so wrap it.
            self._drive_service_instance = await asyncio.to_thread(
                googleapiclient.discovery.build,
                'drive', 'v3', 
                credentials=self.creds, 
                cache_discovery=False, 
                static_discovery=False
            )
            logger.info(f"{self.PROVIDER_NAME}: Google Drive API service instance created/recreated.")
            return self._drive_service_instance
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Failed to build Google Drive service: {e}", exc_info=True)
            self._drive_service_instance = None # Ensure it's reset on error
            return None

    async def _get_id_for_path(self, path_relative_to_app_root: str, start_node_id: Optional[str] = None) -> Optional[str]:
        """
        Translates a path relative to the app's root folder in GDrive into a Google Drive file/folder ID.
        Example: if app root is folder ID 'XYZ123', and path_relative_to_app_root is "MyFolder/file.txt",
        this resolves IDs for "MyFolder" then "file.txt" within it.
        If path_relative_to_app_root is "" or ".", it returns start_node_id.
        """
        service = await self._get_drive_service()
        if not service:
            return None

        if start_node_id is None: # Determine the starting node ID (app root)
            if self._app_root_folder_id: # Use cached app root ID
                current_parent_id = self._app_root_folder_id
            else: # Resolve app root folder path to ID first
                # self.root_folder_path is absolute like "/Apps/Purse"
                # We need to resolve this path from the true GDrive 'root'
                if not self.root_folder_path or self.root_folder_path == "/":
                    self._app_root_folder_id = 'root' # Special ID for user's main Drive folder
                    current_parent_id = 'root'
                else:
                    # Iteratively find ID for self.root_folder_path from 'root'
                    resolved_app_root_id = 'root'
                    path_segments_for_app_root = [seg for seg in self.root_folder_path.strip('/').split('/') if seg]
                    for segment_name in path_segments_for_app_root:
                        query = f"'{resolved_app_root_id}' in parents and name='{segment_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                        try:
                            response = await asyncio.to_thread(
                                service.files().list(q=query, fields="files(id, name)", pageSize=1).execute
                            )
                            files = response.get('files', [])
                            if not files:
                                logger.warning(f"{self.PROVIDER_NAME}: App root path segment '{segment_name}' not found under parent ID '{resolved_app_root_id}'. Cannot resolve full app root: {self.root_folder_path}")
                                return None # App root path doesn't exist
                            resolved_app_root_id = files[0]['id']
                        except Exception as e:
                            logger.error(f"{self.PROVIDER_NAME}: API error resolving app root segment '{segment_name}': {e}")
                            return None
                    self._app_root_folder_id = resolved_app_root_id
                    current_parent_id = self._app_root_folder_id
        else: # start_node_id was provided (e.g. for recursive calls)
            current_parent_id = start_node_id

        if not path_relative_to_app_root or path_relative_to_app_root == ".":
            return current_parent_id # Path is effectively the app root itself

        path_segments = [seg for seg in Path(path_relative_to_app_root).parts if seg != '.']

        for i, segment_name in enumerate(path_segments):
            # Determine if we expect a folder or a file for the last segment
            # For now, assume any segment could be a folder if not last, last could be file/folder.
            # This helper primarily finds IDs, type checking is for caller.
            # If we need to distinguish, mimeType can be added to query.
            # query = f"'{current_parent_id}' in parents and name='{segment_name}' and trashed=false"
            # To be more specific (e.g. if creating a folder, ensure parent is a folder)
            # mime_type_check = "and mimeType='application/vnd.google-apps.folder'" if i < len(path_segments) - 1 else ""
            
            query = f"'{current_parent_id}' in parents and name='{segment_name}' and trashed=false" #removed mime_type_check for now

            try:
                response = await asyncio.to_thread(
                    service.files().list(q=query, fields="files(id, name)", pageSize=1).execute
                ) # pageSize=1 because names are unique within a GDrive folder
                
                found_files = response.get('files', [])
                if not found_files:
                    logger.debug(f"{self.PROVIDER_NAME}: Path segment '{segment_name}' not found under parent ID '{current_parent_id}'. Full path checked: {'/'.join(path_segments[:i+1])}")
                    return None # Path segment not found
                current_parent_id = found_files[0]['id'] # This is now the ID of the current segment
            except Exception as e:
                logger.error(f"{self.PROVIDER_NAME}: API error resolving path segment '{segment_name}': {e}")
                return None
        
        return current_parent_id # This is the ID of the final segment in the path

    def _gdrive_file_to_cloudfile(self, gdrive_file: Dict[str, Any], path_display_override: Optional[str] = None) -> CloudFileMetadata:
        """Converts a Google Drive API file resource (dict) to CloudFileMetadata."""
        file_id = gdrive_file['id']
        name = gdrive_file.get('name', 'Untitled')
        is_folder = gdrive_file.get('mimeType') == 'application/vnd.google-apps.folder'
        
        # Path display: GDrive API doesn't easily give full path.
        # `path_display_override` is crucial if we built the path during traversal.
        # If not provided, this will be just the name.
        # `parents` field in gdrive_file lists parent IDs, could be used to reconstruct path but is slow.
        path_display = path_display_override if path_display_override else name

        # Revision ID for files (not folders)
        rev = gdrive_file.get('version', 'unknown') # 'version' for GDrive is a monotonically increasing number
        if 'md5Checksum' in gdrive_file: # md5Checksum is often available for files
            rev = gdrive_file['md5Checksum']
        elif 'headRevisionId' in gdrive_file: # For Google Docs, Sheets etc.
            rev = gdrive_file['headRevisionId']

        size = int(gdrive_file.get('size', 0)) if not is_folder else 0 # Size is string for GDrive
        
        modified_time_str = gdrive_file.get('modifiedTime') # RFC3339 timestamp e.g. "2023-01-01T12:00:00.000Z"
        modified_timestamp = datetime.now(timezone.utc).timestamp() # Default to now
        if modified_time_str:
            try:
                # Convert RFC3339 string to datetime object, then to UTC Unix timestamp
                dt_obj = datetime.fromisoformat(modified_time_str.replace('Z', '+00:00'))
                modified_timestamp = dt_obj.timestamp()
            except ValueError:
                logger.warning(f"Could not parse modifiedTime '{modified_time_str}' for item '{name}'. Using current time.")

        return CloudFileMetadata(
            id=file_id,
            name=name,
            path_display=path_display, # This should be relative to app root for consistency
            rev=str(rev),
            size=size,
            modified_timestamp=modified_timestamp,
            is_folder=is_folder,
            is_deleted=gdrive_file.get('trashed', False)
        )

    async def authenticate_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        if not all([self.gdrive_client_id, self.gdrive_client_secret, self.gdrive_redirect_uri, self.gdrive_scopes, self.gdrive_auth_uri, self.gdrive_token_uri]):
            raise ValueError(f"{self.PROVIDER_NAME}: OAuth client configuration incomplete.")

        # Client config for from_client_config
        client_config = {
            "web": { # or "installed" if that's the app type
                "client_id": self.gdrive_client_id,
                "client_secret": self.gdrive_client_secret,
                "auth_uri": self.gdrive_auth_uri,
                "token_uri": self.gdrive_token_uri,
                "redirect_uris": [self.gdrive_redirect_uri],
            }
        }
        
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config=client_config,
            scopes=self.gdrive_scopes,
            state=state
        )
        flow.redirect_uri = self.gdrive_redirect_uri # Ensure it's set on the flow instance

        # PKCE is handled by the library if code_challenge_method is specified or by default for installed apps.
        # For installed apps, it's often implicit. For web apps, explicit.
        # Flow.authorization_url can accept code_challenge_method.
        auth_url, _ = await asyncio.to_thread(
            flow.authorization_url,
            access_type='offline', # To get a refresh_token
            prompt='consent',      # To ensure user always sees consent screen for refresh token
            # code_challenge_method='S256' # Enable PKCE if supported by client type
        )
        # The google-auth-oauthlib library stores the code_verifier in flow.code_verifier
        # if PKCE is used (e.g. by specifying code_challenge_method or if it's default for app type).
        # If not using PKCE or library handles it internally without exposing verifier until finish, this might be empty.
        # For Google, PKCE is often implicit for installed apps.
        # The flow object needs to be preserved for exchange_code_for_token if it holds the verifier.
        # This is a challenge for statelessness.
        # For now, let's assume if flow.code_verifier exists, we return it.
        
        # To ensure verifier is always generated if PKCE is intended:
        # We might need to manually trigger PKCE verifier generation if library doesn't do it by default for "web"
        # or ensure our client_config implies an "installed" app flow where PKCE is default.
        # For now, let's assume the library handles it.
        # If flow.code_verifier is None, it means PKCE might not have been engaged by default for this flow type.
        # To force PKCE for a web flow, we'd need to pass code_challenge and code_challenge_method to build_authorize_url
        # similar to Dropbox, but google-auth-library aims to simplify this.
        # For now, we'll return flow.code_verifier if it's set by the library.
        
        # Store this flow instance if it's needed for `exchange_code_for_token` to access `code_verifier`.
        # This is problematic for statelessness. A common pattern is to store verifier in user session.
        # For a desktop app, `self` can be the session.
        self._current_oauth_flow_for_pkce = flow # Temporary storage for PKCE

        return auth_url, getattr(flow, 'code_verifier', "") or ""


    async def exchange_code_for_token(self, auth_code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        # Use the stored flow from authenticate_url if PKCE verifier was managed by it.
        flow = getattr(self, '_current_oauth_flow_for_pkce', None)
        if flow:
            delattr(self, '_current_oauth_flow_for_pkce') # Clean up
        else: # Reconstruct flow if not stored (e.g. if PKCE verifier passed externally or not used)
            client_config = { "web": { "client_id": self.gdrive_client_id, "client_secret": self.gdrive_client_secret,
                                       "auth_uri": self.gdrive_auth_uri, "token_uri": self.gdrive_token_uri, 
                                       "redirect_uris": [self.gdrive_redirect_uri] }}
            flow = google_auth_oauthlib.flow.Flow.from_client_config(client_config=client_config, scopes=self.gdrive_scopes)
            flow.redirect_uri = self.gdrive_redirect_uri
            if code_verifier: # If verifier was managed externally and passed in
                 setattr(flow, 'code_verifier', code_verifier)

        try:
            await asyncio.to_thread(flow.fetch_token, code=auth_code)
            
            current_creds = flow.credentials
            
            access_token_val = current_creds.token
            refresh_token_val = current_creds.refresh_token
            user_id_val = current_creds.id_token.get('sub') if hasattr(current_creds, 'id_token') and current_creds.id_token else None
            expiry_timestamp_val = current_creds.expiry.timestamp() if current_creds.expiry else None
            id_token_val = current_creds.id_token if hasattr(current_creds, 'id_token') else None
            scopes_val = current_creds.scopes

            token_dict_to_save = {
                'access_token': access_token_val,
                'refresh_token': refresh_token_val,
                'user_id': user_id_val,
                'token_expiry_timestamp': expiry_timestamp_val,
            }
            
            self._save_tokens_to_keyring(token_dict_to_save)
            self._reinitialize_client_with_loaded_tokens()

            logger.info(f"{self.PROVIDER_NAME}: Successfully exchanged code for token. User ID: {self.user_id or 'Not Provided'}")
            
            return {
                'access_token': self.access_token, 
                'refresh_token': self.refresh_token, 
                'user_id': self.user_id, 
                'expires_at': self.token_expiry_timestamp, 
                'id_token': id_token_val, 
                'scopes': scopes_val     
            }
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Exception during token exchange: {e}", exc_info=True)
            raise # Re-raise to be handled by caller


    async def refresh_access_token(self) -> Optional[str]:
        if not self.creds or not self.creds.refresh_token:
            logger.warning(f"{self.PROVIDER_NAME}: No credentials or refresh token available for token refresh.")
            return None
        
        try:
            # refresh is synchronous
            await asyncio.to_thread(self.creds.refresh, google.auth.transport.requests.Request())
            
            new_access_token = self.creds.token
            new_refresh_token = self.creds.refresh_token 
            new_expiry_timestamp = self.creds.expiry.timestamp() if self.creds.expiry else None

            token_dict_to_save = {
                'access_token': new_access_token,
                'refresh_token': new_refresh_token, 
                'user_id': self.user_id, # Preserve existing user_id
                'token_expiry_timestamp': new_expiry_timestamp
            }
            
            self._save_tokens_to_keyring(token_dict_to_save)
            self._reinitialize_client_with_loaded_tokens() 

            logger.info(f"{self.PROVIDER_NAME}: Access token refreshed successfully.")
            return self.access_token # Return the new access token from the instance
            
        except google.auth.exceptions.RefreshError as e:
            logger.error(f"{self.PROVIDER_NAME}: Failed to refresh access token: {e}. Deleting tokens.", exc_info=True)
            self._delete_tokens_from_keyring()
            self.creds = None # Explicitly clear credentials
            self._drive_service_instance = None # Invalidate service
            return None
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Unexpected error during token refresh: {e}", exc_info=True)
            # For unexpected errors, ensure creds are None so service rebuild fails cleanly.
            self.creds = None
            self._drive_service_instance = None
            return None


    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        service = await self._get_drive_service()
        if not service: return None
        try:
            # 'user' field contains kind, displayName, photoLink, me, permissionId, emailAddress
            user_info_gdrive = await asyncio.to_thread(service.about().get(fields="user").execute)
            user_data = user_info_gdrive.get('user', {})
            # Map to a more standard format if needed, or return as is.
            # Example mapping:
            return {
                "id": user_data.get('permissionId'), # permissionId is specific to this user for Drive items
                "name": user_data.get('displayName'),
                "email": user_data.get('emailAddress'),
                "raw": user_data
            }
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: API error fetching user info: {e}", exc_info=True)
            return None

    # --- File and Folder Operations ---
    # These methods will use _get_id_for_path to resolve string paths to GDrive IDs.
    # Note: self.get_full_cloud_path(relative_path) gives path from true GDrive root.
    # _get_id_for_path then takes this full GDrive path and resolves it.

    async def list_folder(self, folder_path: str, recursive: bool = False) -> AsyncGenerator[CloudFileMetadata, None]:
        # folder_path is relative to app's root folder (e.g. self.root_folder_path like "/Apps/Purse")
        # So, first get the ID of this folder_path.
        # `self.get_full_cloud_path(folder_path)` gives absolute path from GDrive root.
        # `_get_id_for_path` then takes this absolute GDrive path.

        # The `_get_id_for_path` helper needs to take the full path from GDrive root.
        # `self.get_full_cloud_path()` is designed to give this.
        # Let's adjust `_get_id_for_path` to take full path from root ('/foo/bar')
        # and iterate from 'root' GDrive ID.

        # Correction: `_get_id_for_path` should take path relative to its `parent_id` argument.
        # For `list_folder`, the `folder_path` is relative to `self.root_folder_path`.
        # First, get ID of `self.root_folder_path`. Then, get ID of `folder_path` relative to app root ID.
        
        # Simpler: `_get_id_for_path` resolves a path starting from the main GDrive 'root' ID
        # down to the target. So, `self.get_full_cloud_path(folder_path)` is the correct input for it.
        
        # Redefined understanding for _get_id_for_path:
        # It takes a path that is ALREADY relative to the GDrive 'root' if parent_id='root'.
        # Or relative to a given parent_id.
        # `self.get_full_cloud_path(folder_path)` gives the absolute path from GDrive root.
        # This absolute path is what `_get_id_for_path` should process from 'root'.
        
        # Let's refine `_get_id_for_path` to always start from 'root' and take full path.
        # And cache `self._app_root_folder_id` if `self.root_folder_path` is not just '/'.
        
        # The provided folder_path is relative to app root.
        # We need the ID of this folder.
        # First, ensure app root ID is known/resolved.
        if self._app_root_folder_id is None and self.root_folder_path != "/": # If app root is not GDrive root
            resolved_app_root_id = await self._get_id_for_path(self.root_folder_path.strip('/')) # Pass path from GDrive root
            if not resolved_app_root_id:
                logger.error(f"{self.PROVIDER_NAME}: App root folder '{self.root_folder_path}' could not be resolved to an ID. Cannot list.")
                return
            self._app_root_folder_id = resolved_app_root_id
        
        # Determine the actual parent ID for listing
        parent_id_for_listing: str
        if folder_path == "" or folder_path == ".": # Listing the app root itself
            parent_id_for_listing = self._app_root_folder_id if self._app_root_folder_id else 'root'
        else: # Listing a subfolder within the app root
            start_node = self._app_root_folder_id if self._app_root_folder_id else 'root'
            # _get_id_for_path now takes path relative to start_node
            resolved_list_folder_id = await self._get_id_for_path(folder_path, start_node_id=start_node)
            if not resolved_list_folder_id:
                logger.warning(f"{self.PROVIDER_NAME}: Folder '{folder_path}' not found within app root. Cannot list.")
                return
            parent_id_for_listing = resolved_list_folder_id


        service = await self._get_drive_service()
        if not service: yield # type: ignore # Should not happen if above checks pass

        page_token = None
        while True:
            try:
                response = await asyncio.to_thread(
                    service.files().list(
                        q=f"'{parent_id_for_listing}' in parents and trashed=false",
                        fields="nextPageToken, files(id, name, mimeType, version, md5Checksum, headRevisionId, size, modifiedTime, parents, trashed)", # Add parents to help reconstruct path if needed
                        pageSize=100, # Adjust as needed
                        pageToken=page_token
                    ).execute
                )
                for gdrive_file_meta in response.get('files', []):
                    # Construct path_display relative to the listed folder_path (which is relative to app root)
                    # Example: folder_path = "MySubFolder", gdrive_file_meta.name = "file.txt"
                    # Then, path_display_for_cloudfile = "MySubFolder/file.txt"
                    # If folder_path is "", then path_display_for_cloudfile = "file.txt"
                    path_display_val = str(Path(folder_path) / gdrive_file_meta['name'])
                    yield self._gdrive_file_to_cloudfile(gdrive_file_meta, path_display_override=path_display_val)

                    if recursive and gdrive_file_meta.get('mimeType') == 'application/vnd.google-apps.folder':
                        # Path for recursive call is path_display_val, already relative to app root
                        async for item in self.list_folder(path_display_val, recursive=True):
                            yield item
                
                page_token = response.get('nextPageToken', None)
                if not page_token:
                    break
            except Exception as e:
                logger.error(f"{self.PROVIDER_NAME}: API error listing folder ID '{parent_id_for_listing}' (path '{folder_path}'): {e}", exc_info=True)
                break

    async def download_file(self, cloud_file_path: str, local_target_path: Path) -> bool:
        # cloud_file_path is relative to app root.
        # Resolve its ID first.
        start_node = self._app_root_folder_id if self._app_root_folder_id else 'root'
        file_id = await self._get_id_for_path(cloud_file_path, start_node_id=start_node)
        if not file_id:
            logger.error(f"{self.PROVIDER_NAME}: File not found at '{cloud_file_path}' for download.")
            return False

        service = await self._get_drive_service()
        if not service: return False

        try:
            local_target_path.parent.mkdir(parents=True, exist_ok=True)
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO() # In-memory buffer
            downloader = googleapiclient.http.MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                # status, done = downloader.next_chunk() # sync
                status, done = await asyncio.to_thread(downloader.next_chunk)
                if status: logger.debug(f"Download {cloud_file_path} progress: {int(status.progress() * 100)}%")
            
            with open(local_target_path, 'wb') as f:
                f.write(fh.getvalue())
            logger.info(f"{self.PROVIDER_NAME}: Downloaded file ID '{file_id}' ('{cloud_file_path}') to '{local_target_path}'")
            return True
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error downloading file ID '{file_id}' ('{cloud_file_path}'): {e}", exc_info=True)
            return False


    async def download_file_content(self, cloud_file_path: str) -> Optional[bytes]:
        start_node = self._app_root_folder_id if self._app_root_folder_id else 'root'
        file_id = await self._get_id_for_path(cloud_file_path, start_node_id=start_node)
        if not file_id:
            logger.error(f"{self.PROVIDER_NAME}: File not found at '{cloud_file_path}' for content download.")
            return None

        service = await self._get_drive_service()
        if not service: return None
        try:
            request = service.files().get_media(fileId=file_id)
            content = await asyncio.to_thread(request.execute) # For direct download of small files
            return content
        except Exception as e: # More specific error handling for HttpError needed
            logger.error(f"{self.PROVIDER_NAME}: Error downloading content for file ID '{file_id}' ('{cloud_file_path}'): {e}", exc_info=True)
            return None


    async def upload_file(self, local_file_path: Path, cloud_target_folder: str, cloud_file_name: Optional[str] = None) -> Optional[CloudFileMetadata]:
        if not local_file_path.exists() or not local_file_path.is_file():
            logger.error(f"{self.PROVIDER_NAME}: Local file for upload not found: {local_file_path}")
            return None

        # Determine parent folder ID for upload
        start_node = self._app_root_folder_id if self._app_root_folder_id else 'root'
        parent_folder_id = await self._get_id_for_path(cloud_target_folder, start_node_id=start_node)
        if not parent_folder_id:
            logger.error(f"{self.PROVIDER_NAME}: Target cloud folder '{cloud_target_folder}' not found for upload.")
            return None

        service = await self._get_drive_service()
        if not service: return None

        file_name_to_use = cloud_file_name if cloud_file_name else local_file_path.name
        
        # Check if file already exists to get its ID for update, or None for create
        # This is to implement overwrite behavior. GDrive create doesn't overwrite by default.
        existing_file_id = await self._get_id_for_path(str(Path(cloud_target_folder) / file_name_to_use), start_node_id=start_node)

        file_metadata = {'name': file_name_to_use}
        if not existing_file_id: # Only add parents if creating new file
             file_metadata['parents'] = [parent_folder_id]

        mime_type, _ = mimetypes.guess_type(str(local_file_path))
        mime_type = mime_type or 'application/octet-stream'

        media = googleapiclient.http.MediaFileUpload(str(local_file_path), mimetype=mime_type, resumable=True)
        
        try:
            if existing_file_id: # Update existing file
                gdrive_file = await asyncio.to_thread(
                    service.files().update(fileId=existing_file_id, media_body=media, fields='*').execute # fields='*' to get all fields back
                )
                logger.info(f"{self.PROVIDER_NAME}: Updated file ID '{existing_file_id}' with content from '{local_file_path}'")
            else: # Create new file
                gdrive_file = await asyncio.to_thread(
                    service.files().create(body=file_metadata, media_body=media, fields='*').execute
                )
                logger.info(f"{self.PROVIDER_NAME}: Uploaded '{local_file_path}' to cloud folder ID '{parent_folder_id}' as '{file_name_to_use}' (ID: {gdrive_file['id']})")
            
            # Construct path_display for the CloudFileMetadata object
            path_display_val = str(Path(cloud_target_folder) / file_name_to_use)
            return self._gdrive_file_to_cloudfile(gdrive_file, path_display_override=path_display_val)
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error uploading '{local_file_path}': {e}", exc_info=True)
            return None


    async def upload_file_content(self, content_bytes: bytes, cloud_target_folder: str, cloud_file_name: str) -> Optional[CloudFileMetadata]:
        start_node = self._app_root_folder_id if self._app_root_folder_id else 'root'
        parent_folder_id = await self._get_id_for_path(cloud_target_folder, start_node_id=start_node)
        if not parent_folder_id:
            logger.error(f"{self.PROVIDER_NAME}: Target cloud folder '{cloud_target_folder}' not found for content upload.")
            return None

        service = await self._get_drive_service()
        if not service: return None
        
        existing_file_id = await self._get_id_for_path(str(Path(cloud_target_folder) / cloud_file_name), start_node_id=start_node)

        file_metadata = {'name': cloud_file_name}
        if not existing_file_id:
            file_metadata['parents'] = [parent_folder_id]

        # Assuming generic bytes, use application/octet-stream
        media = googleapiclient.http.MediaIoBaseUpload(io.BytesIO(content_bytes), mimetype='application/octet-stream', resumable=True)

        try:
            if existing_file_id:
                 gdrive_file = await asyncio.to_thread(
                    service.files().update(fileId=existing_file_id, media_body=media, fields='*').execute
                )
                 logger.info(f"{self.PROVIDER_NAME}: Updated file ID '{existing_file_id}' with new content as '{cloud_file_name}'")
            else:
                gdrive_file = await asyncio.to_thread(
                    service.files().create(body=file_metadata, media_body=media, fields='*').execute
                )
                logger.info(f"{self.PROVIDER_NAME}: Uploaded content to cloud folder ID '{parent_folder_id}' as '{cloud_file_name}' (ID: {gdrive_file['id']})")
            
            path_display_val = str(Path(cloud_target_folder) / cloud_file_name)
            return self._gdrive_file_to_cloudfile(gdrive_file, path_display_override=path_display_val)
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error uploading content as '{cloud_file_name}': {e}", exc_info=True)
            return None


    async def delete_file(self, cloud_file_path: str) -> bool:
        start_node = self._app_root_folder_id if self._app_root_folder_id else 'root'
        file_id = await self._get_id_for_path(cloud_file_path, start_node_id=start_node)
        if not file_id:
            logger.warning(f"{self.PROVIDER_NAME}: File/folder not found at '{cloud_file_path}' for deletion (already deleted?).")
            return True # Consider not found as successfully deleted state

        service = await self._get_drive_service()
        if not service: return False
        try:
            await asyncio.to_thread(service.files().delete(fileId=file_id).execute)
            logger.info(f"{self.PROVIDER_NAME}: Deleted file/folder ID '{file_id}' ('{cloud_file_path}')")
            return True
        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 404: # Not found
                logger.warning(f"{self.PROVIDER_NAME}: File/folder ID '{file_id}' ('{cloud_file_path}') not found for deletion (already deleted?).")
                return True
            logger.error(f"{self.PROVIDER_NAME}: API error deleting ID '{file_id}' ('{cloud_file_path}'): {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error deleting ID '{file_id}' ('{cloud_file_path}'): {e}", exc_info=True)
            return False


    async def create_folder(self, cloud_folder_path: str) -> bool:
        # cloud_folder_path is relative to app root.
        # If cloud_folder_path is "" or ".", it refers to the app root itself.
        # This method should ensure that this folder exists.
        
        # Ensure app root ID is resolved first
        if self._app_root_folder_id is None and self.root_folder_path != "/":
            resolved_app_root_id = await self._get_id_for_path(self.root_folder_path.strip('/')) # Path from GDrive root
            if not resolved_app_root_id:
                logger.error(f"{self.PROVIDER_NAME}: App root folder '{self.root_folder_path}' could not be resolved. Cannot create subfolder '{cloud_folder_path}'.")
                return False
            self._app_root_folder_id = resolved_app_root_id
        
        start_node_id = self._app_root_folder_id if self._app_root_folder_id else 'root'

        if not cloud_folder_path or cloud_folder_path == ".": # Ensuring the app root itself
            # If start_node_id is 'root' and self.root_folder_path was '/', it's fine.
            # If start_node_id is a resolved ID, it means it exists.
            if start_node_id:
                logger.info(f"{self.PROVIDER_NAME}: App root folder (ID: {start_node_id}) confirmed to exist for path '{cloud_folder_path}'.")
                return True
            else: # Should not happen if logic above is correct
                logger.error(f"{self.PROVIDER_NAME}: Could not confirm app root for path '{cloud_folder_path}'.")
                return False

        # Path is relative to app root. We need to create it segment by segment under start_node_id.
        current_parent_id = start_node_id
        full_path_being_created = Path() # Tracks the path being created relative to app root

        for segment_name in Path(cloud_folder_path).parts:
            if not segment_name or segment_name == '.': continue

            full_path_being_created /= segment_name
            # Check if this segment already exists under current_parent_id
            existing_segment_id = await self._get_id_for_path(segment_name, start_node_id=current_parent_id)
            
            if existing_segment_id:
                # Need to check if it's a folder
                meta = await self.get_file_metadata(str(full_path_being_created)) # This path is relative to app root
                if meta and meta.is_folder:
                    current_parent_id = existing_segment_id
                    logger.debug(f"{self.PROVIDER_NAME}: Subfolder segment '{segment_name}' already exists (ID: {current_parent_id}).")
                elif meta and not meta.is_folder:
                    logger.error(f"{self.PROVIDER_NAME}: Cannot create folder '{segment_name}', a file with this name exists in parent ID '{current_parent_id}'.")
                    return False
                else: # Should not happen if _get_id_for_path worked
                    logger.error(f"{self.PROVIDER_NAME}: Could not get metadata for existing segment '{segment_name}' (ID: {existing_segment_id}).")
                    return False
            else: # Segment does not exist, create it
                service = await self._get_drive_service()
                if not service: return False
                
                folder_metadata = {
                    'name': segment_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [current_parent_id]
                }
                try:
                    created_folder = await asyncio.to_thread(
                        service.files().create(body=folder_metadata, fields='id').execute
                    )
                    current_parent_id = created_folder['id']
                    logger.info(f"{self.PROVIDER_NAME}: Created subfolder segment '{segment_name}' (ID: {current_parent_id}) in parent ID '{folder_metadata['parents'][0]}'.")
                except Exception as e:
                    logger.error(f"{self.PROVIDER_NAME}: Error creating subfolder segment '{segment_name}' in parent ID '{current_parent_id}': {e}", exc_info=True)
                    return False
        return True


    async def get_file_metadata(self, cloud_file_path: str) -> Optional[CloudFileMetadata]:
        # cloud_file_path is relative to app root.
        start_node = self._app_root_folder_id if self._app_root_folder_id else 'root'
        file_id = await self._get_id_for_path(cloud_file_path, start_node_id=start_node)
        
        if not file_id:
            logger.debug(f"{self.PROVIDER_NAME}: File/folder not found at '{cloud_file_path}' when trying to get metadata.")
            return None

        service = await self._get_drive_service()
        if not service: return None
        try:
            # Get all relevant fields for CloudFileMetadata
            fields_to_get = "id, name, mimeType, version, md5Checksum, headRevisionId, size, modifiedTime, parents, trashed"
            gdrive_file_meta = await asyncio.to_thread(service.files().get(fileId=file_id, fields=fields_to_get).execute)
            # Pass the original cloud_file_path as path_display_override because it's relative to app root.
            return self._gdrive_file_to_cloudfile(gdrive_file_meta, path_display_override=cloud_file_path)
        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 404:
                logger.debug(f"{self.PROVIDER_NAME}: File/folder ID '{file_id}' ('{cloud_file_path}') not found by API.")
                return None
            logger.error(f"{self.PROVIDER_NAME}: API error getting metadata for ID '{file_id}' ('{cloud_file_path}'): {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error getting metadata for ID '{file_id}' ('{cloud_file_path}'): {e}", exc_info=True)
            return None
            
    async def ensure_app_root_folder_exists(self) -> bool:
        # This method is called to ensure self.root_folder_path (e.g., "/Apps/Purse") exists.
        # It will resolve self.root_folder_path from the true GDrive 'root'.
        if self._app_root_folder_id: # Already resolved and cached
            logger.info(f"{self.PROVIDER_NAME}: App root folder ID '{self._app_root_folder_id}' previously resolved. Assuming it exists.")
            return True

        if not self.root_folder_path or self.root_folder_path == "/":
            self._app_root_folder_id = 'root' # Special ID for user's main Drive folder
            logger.info(f"{self.PROVIDER_NAME}: App root folder is GDrive 'root'. Assuming it exists.")
            return True

        # Resolve path like "/Apps/Purse" segment by segment from GDrive 'root'
        current_parent_id = 'root'
        path_segments_for_app_root = [seg for seg in self.root_folder_path.strip('/').split('/') if seg]
        
        for i, segment_name in enumerate(path_segments_for_app_root):
            # Check if this segment exists under current_parent_id
            # _get_id_for_path(segment_name, current_parent_id) would do this
            # This is effectively what create_folder(path_segment, parent_id) does.
            # Let's use a simplified version of create_folder's logic here for each segment.
            
            # Path to check/create is just the current segment name, relative to current_parent_id
            existing_segment_id = await self._get_id_for_path(segment_name, start_node_id=current_parent_id)

            if existing_segment_id:
                # Verify it's a folder
                # This requires getting metadata of existing_segment_id.
                # For simplicity, assume if ID exists by name query, it's the one we want.
                # A full check would involve getting metadata and checking mimeType.
                current_parent_id = existing_segment_id
                logger.debug(f"{self.PROVIDER_NAME}: App root segment '{segment_name}' already exists (ID: {current_parent_id}).")
            else: # Segment does not exist, create it
                service = await self._get_drive_service()
                if not service: return False
                
                folder_metadata_body = {
                    'name': segment_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [current_parent_id]
                }
                try:
                    created_folder = await asyncio.to_thread(
                        service.files().create(body=folder_metadata_body, fields='id').execute
                    )
                    current_parent_id = created_folder['id']
                    logger.info(f"{self.PROVIDER_NAME}: Created app root segment '{segment_name}' (ID: {current_parent_id}) in parent ID '{folder_metadata_body['parents'][0]}'.")
                except Exception as e:
                    logger.error(f"{self.PROVIDER_NAME}: Error creating app root segment '{segment_name}' in parent ID '{current_parent_id}': {e}", exc_info=True)
                    return False
        
        self._app_root_folder_id = current_parent_id # Cache the final app root folder ID
        logger.info(f"{self.PROVIDER_NAME}: App root folder '{self.root_folder_path}' ensured (final ID: {self._app_root_folder_id}).")
        return True

```
