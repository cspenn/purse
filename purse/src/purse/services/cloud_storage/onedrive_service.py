import asyncio
from datetime import datetime, timezone
import msal
import httpx
import json # For request bodies
import logging
from typing import List, Optional, Tuple, Dict, Any, AsyncGenerator, TYPE_CHECKING
from pathlib import Path
from urllib.parse import quote # For encoding path segments in URLs

from purse.services.cloud_storage.base_cloud_service import BaseCloudService, CloudFileMetadata

if TYPE_CHECKING:
    from purse.config_manager import ConfigManager

logger = logging.getLogger(__name__)

# Max size for simple PUT upload (Graph API recommends resumable for >4MB)
SIMPLE_UPLOAD_MAX_SIZE_BYTES = 4 * 1024 * 1024 

class OneDriveService(BaseCloudService):
    PROVIDER_NAME = "OneDrive"

    def __init__(self, 
                 config_manager: 'ConfigManager', 
                 access_token: Optional[str] = None, # Usually not passed directly, MSAL handles
                 refresh_token: Optional[str] = None, # Usually not passed directly, MSAL handles via cache
                 msal_cache_str: Optional[str] = None,
                 home_account_id: Optional[str] = None): # MSAL's home_account_id
        
        super().__init__(config_manager, access_token, refresh_token)
        self.user_id = home_account_id # Base class user_id can be MSAL home_account_id
        
        self.client_id: Optional[str] = self.config_manager.get('cloud_providers.onedrive.client_id')
        self.authority: Optional[str] = self.config_manager.get('cloud_providers.onedrive.authority')
        self.scopes: Optional[List[str]] = self.config_manager.get('cloud_providers.onedrive.scopes')
        self.redirect_uri: Optional[str] = self.config_manager.get('cloud_providers.onedrive.redirect_uri')
        self.graph_api_endpoint: str = self.config_manager.get('cloud_providers.onedrive.graph_api_endpoint_v1', 'https://graph.microsoft.com/v1.0')

        if not all([self.client_id, self.authority, self.scopes, self.redirect_uri]):
            logger.error(f"{self.PROVIDER_NAME}: Critical OAuth configuration missing. OneDrive service will be unavailable.")
            self._is_configured = False
        else:
            self._is_configured = True

        self.msal_cache = msal.SerializableTokenCache()
        if msal_cache_str:
            try:
                self.msal_cache.deserialize(msal_cache_str)
            except Exception as e:
                logger.warning(f"{self.PROVIDER_NAME}: Failed to deserialize MSAL cache: {e}. Starting with an empty cache.")
        
        if self._is_configured:
            self.msal_app = msal.PublicClientApplication(
                client_id=self.client_id, # type: ignore
                authority=self.authority, # type: ignore
                token_cache=self.msal_cache
            )
        else:
            self.msal_app = None # type: ignore

        self.home_account_id: Optional[str] = home_account_id
        self._pkce_verifier: Optional[str] = None

    async def _get_headers(self) -> Optional[Dict[str, str]]:
        if not self.msal_app or not self.scopes or not self._is_configured:
            logger.error(f"{self.PROVIDER_NAME}: MSAL app or OAuth parameters not configured. Cannot acquire token.")
            return None

        account_to_use = None
        if self.home_account_id:
            account_to_use = self.msal_app.get_account_by_home_id(self.home_account_id)
        
        if not account_to_use: # Fallback to any available account if specific one not found/set
            accounts = self.msal_app.get_accounts()
            if accounts:
                account_to_use = accounts[0]
                if not self.home_account_id : # If home_account_id was not set, use this one now
                    self.home_account_id = account_to_use.get("home_account_id")
                    self.user_id = self.home_account_id
            else:
                logger.info(f"{self.PROVIDER_NAME}: No cached accounts found. Interactive login required.")
                return None # No account, cannot get token silently

        token_result = None
        try:
            token_result = await asyncio.to_thread(
                self.msal_app.acquire_token_silent, self.scopes, account=account_to_use
            )
        except Exception as e:
            logger.warning(f"{self.PROVIDER_NAME}: Error during acquire_token_silent: {e}")

        if not token_result and self.refresh_token: # Unlikely to be used if MSAL cache is primary mechanism
            logger.info(f"{self.PROVIDER_NAME}: Trying with externally provided refresh_token.")
            try:
                token_result = await asyncio.to_thread(
                    self.msal_app.acquire_token_by_refresh_token, self.refresh_token, scopes=self.scopes
                )
            except Exception as e:
                logger.warning(f"{self.PROVIDER_NAME}: Error acquiring token by external refresh_token: {e}")

        if token_result and "access_token" in token_result:
            self.access_token = token_result["access_token"]
            if token_result.get("account") and not self.home_account_id: # Update home_account_id if newly acquired
                self.home_account_id = token_result["account"].get("home_account_id")
                self.user_id = self.home_account_id
            return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        else:
            logger.warning(f"{self.PROVIDER_NAME}: Failed to acquire token silently. Details: {token_result.get('error_description', 'No specific error description.') if token_result else 'No token result.'}")
            return None

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
        if not self._is_configured: return None
        
        base_headers = await self._get_headers()
        if not base_headers:
            logger.error(f"{self.PROVIDER_NAME}: Cannot make Graph API call, authentication failed.")
            return None
        
        effective_headers = {**base_headers, **(headers_extra or {})}
        
        full_url = f"{self.graph_api_endpoint}{url_suffix}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(method, full_url, headers=effective_headers, **kwargs)
            
            if 400 <= response.status_code < 600:
                 try: error_details = response.json()
                 except: error_details = response.text # type: ignore
                 logger.error(f"{self.PROVIDER_NAME}: Graph API error {response.status_code} for {method} {url_suffix}: {error_details}")
                 response.raise_for_status()
            return response
        except httpx.HTTPStatusError: raise 
        except httpx.RequestError as e:
            logger.error(f"{self.PROVIDER_NAME}: HTTP request error for {method} {url_suffix}: {e}")
            raise
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Unexpected error for {method} {url_suffix}: {e}", exc_info=True)
            raise

    async def authenticate_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        if not self.msal_app or not self.scopes or not self.redirect_uri:
            raise ValueError(f"{self.PROVIDER_NAME}: MSAL app or OAuth parameters not configured.")
        
        self._pkce_verifier = msal.oauth2cli.pkce.generate_code_verifier(43)
        code_challenge = msal.oauth2cli.pkce.generate_code_challenge(self._pkce_verifier, "S256")

        auth_url = self.msal_app.get_authorization_request_url(
            self.scopes, state=state, redirect_uri=self.redirect_uri,
            code_challenge=code_challenge, code_challenge_method="S256"
        )
        return auth_url, self._pkce_verifier

    async def exchange_code_for_token(self, auth_code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        if not self.msal_app or not self.scopes or not self.redirect_uri:
            raise ValueError(f"{self.PROVIDER_NAME}: MSAL app or OAuth parameters not configured.")

        effective_verifier = self._pkce_verifier if self._pkce_verifier else code_verifier
        self._pkce_verifier = None 

        try:
            token_result = await asyncio.to_thread(
                self.msal_app.acquire_token_by_authorization_code,
                auth_code, scopes=self.scopes, redirect_uri=self.redirect_uri,
                code_verifier=effective_verifier
            )
        except Exception as e:
            logger.error(f"{self.PROVIDER_NAME}: Error acquiring token by authorization code: {e}", exc_info=True)
            raise ValueError(f"Token acquisition failed: {e}")

        if "error" in token_result:
            err_msg = token_result.get('error_description', token_result['error'])
            logger.error(f"{self.PROVIDER_NAME}: Failed to acquire token: {err_msg}")
            raise ValueError(f"Token acquisition error: {err_msg}")

        self.access_token = token_result.get("access_token")
        # MSAL cache handles refresh_token persistence.
        self.refresh_token = token_result.get("refresh_token") 
        
        account = token_result.get("account")
        if account:
            self.home_account_id = account.get("home_account_id")
            self.user_id = self.home_account_id
        elif "id_token_claims" in token_result and "oid" in token_result["id_token_claims"]:
             self.user_id = token_result["id_token_claims"]["oid"] # Azure AD User Object ID
             self.home_account_id = self.user_id 

        logger.info(f"{self.PROVIDER_NAME}: Successfully exchanged code for token. User ID (HomeAccountID/OID): {self.user_id}")
        
        return {
            'access_token': self.access_token, 'refresh_token': self.refresh_token,
            'user_id': self.user_id, 'id_token': token_result.get('id_token'),
            'id_token_claims': token_result.get('id_token_claims'),
            'scopes': token_result.get('scope'), 'expires_in': token_result.get('expires_in'),
            'msal_cache_str': self.msal_cache.serialize()
        }

    async def refresh_access_token(self) -> Optional[str]:
        logger.info(f"{self.PROVIDER_NAME}: Attempting to refresh access token via silent acquisition...")
        headers = await self._get_headers()
        if headers and self.access_token:
            logger.info(f"{self.PROVIDER_NAME}: Access token refreshed/validated successfully.")
            return self.access_token
        else:
            logger.error(f"{self.PROVIDER_NAME}: Failed to refresh/validate access token.")
            return None

    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        try:
            response = await self._make_graph_api_call("GET", "/me?$select=id,displayName,mail,userPrincipalName")
            if response and response.status_code == 200:
                user_data = response.json()
                return {"id": user_data.get('id'), "name": user_data.get('displayName'),
                        "email": user_data.get('mail') or user_data.get('userPrincipalName'), "raw": user_data}
        except Exception: pass # Logged by _make_graph_api_call
        return None

    def _get_graph_path_suffix(self, path_relative_to_app_root: str) -> str:
        full_path_in_drive = self.get_full_cloud_path(path_relative_to_app_root)
        if not full_path_in_drive or full_path_in_drive == "/": # Addressing drive root
            return "" if not path_relative_to_app_root else f":/{quote(path_relative_to_app_root)}:"
        return f":{quote(full_path_in_drive.lstrip('/'))}:" # Path from root, e.g. :/Apps/Purse/file.txt:

    async def list_folder(self, folder_path: str, recursive: bool = False) -> AsyncGenerator[CloudFileMetadata, None]:
        graph_path_suffix = self._get_graph_path_suffix(folder_path)
        url_suffix = f"/me/drive/root{graph_path_suffix}/children?$select=id,name,folder,file,size,lastModifiedDateTime,eTag,deleted"
        next_link = None
        while True:
            current_url = next_link if next_link else f"{self.graph_api_endpoint}{url_suffix}"
            # _make_graph_api_call needs url_suffix relative to graph_api_endpoint
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
            except Exception: break # Logged by _make_graph_api_call

    async def get_file_metadata(self, cloud_file_path: str) -> Optional[CloudFileMetadata]:
        graph_path_suffix = self._get_graph_path_suffix(cloud_file_path)
        url_suffix = f"/me/drive/root{graph_path_suffix}?$select=id,name,folder,file,size,lastModifiedDateTime,eTag,deleted"
        if not graph_path_suffix: url_suffix = "/me/drive/root?$select=id,name,folder,file,size,lastModifiedDateTime,eTag,deleted" # Drive root itself
        try:
            response = await self._make_graph_api_call("GET", url_suffix)
            if response and response.status_code == 200:
                return self._graph_item_to_cloudfile(response.json(), cloud_file_path if cloud_file_path else "")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404: logger.debug(f"Metadata not found (404) for '{cloud_file_path}'.")
        return None

    async def create_folder(self, cloud_folder_path: str) -> bool:
        if not cloud_folder_path: # Request to ensure app root exists
            return await self.ensure_app_root_folder_exists()

        parent_path = str(Path(cloud_folder_path).parent)
        folder_name = Path(cloud_folder_path).name
        
        parent_graph_suffix = self._get_graph_path_suffix(parent_path if parent_path != "." else "")
        url_suffix = f"/me/drive/root{parent_graph_suffix}/children"
        
        request_body = {"name": folder_name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
        try:
            response = await self._make_graph_api_call("POST", url_suffix, json=request_body)
            return response is not None and response.status_code == 201
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409: # Conflict
                logger.info(f"Folder '{cloud_folder_path}' likely already exists.")
                meta = await self.get_file_metadata(cloud_folder_path) # Verify it's a folder
                return meta is not None and meta.is_folder
        return False

    async def ensure_app_root_folder_exists(self) -> bool:
        if not self._is_configured: return False
        if not self.root_folder_path or self.root_folder_path == "/":
            logger.info(f"{self.PROVIDER_NAME}: App root is drive root, assumed to exist.")
            return True

        logger.info(f"{self.PROVIDER_NAME}: Ensuring app root folder '{self.root_folder_path}' exists.")
        
        path_segments = [s for s in self.root_folder_path.strip("/").split("/") if s]
        current_abs_path_str = "" # Absolute path from drive root being built, e.g., "/Apps"
        parent_graph_api_path_suffix = "" # Graph API suffix for parent, e.g., "" or ":/Apps:"

        for segment_name in path_segments:
            current_abs_path_str = f"{current_abs_path_str}/{segment_name}"
            # Graph API path suffix for the current segment to check/create metadata, e.g. ":/Apps:" or ":/Apps/Purse:"
            segment_meta_graph_suffix = f":{current_abs_path_str.lstrip('/')}:"
            url_get_meta = f"/me/drive/root{segment_meta_graph_suffix}?$select=id,name,folder"
            
            item_exists_as_folder = False
            try:
                response = await self._make_graph_api_call("GET", url_get_meta)
                if response and response.status_code == 200:
                    item_data = response.json()
                    if 'folder' in item_data:
                        item_exists_as_folder = True
                        logger.debug(f"Segment '{segment_name}' at '{current_abs_path_str}' exists.")
                    else:
                        logger.error(f"Path '{current_abs_path_str}' exists but is a file.")
                        return False
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    logger.error(f"Error checking segment '{current_abs_path_str}': {e}")
                    return False # Not a 404, some other issue
            except Exception as e:
                logger.error(f"Unexpected error checking segment '{current_abs_path_str}': {e}")
                return False

            if not item_exists_as_folder:
                logger.info(f"Segment '{segment_name}' at '{current_abs_path_str}' not found. Creating.")
                create_in_url_suffix = f"/me/drive/root{parent_graph_api_path_suffix}/children"
                request_body = {"name": segment_name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
                try:
                    response_create = await self._make_graph_api_call("POST", create_in_url_suffix, json=request_body)
                    if not (response_create and response_create.status_code == 201):
                        err_text = response_create.text if response_create else "No response"
                        logger.error(f"Failed to create segment '{segment_name}'. Response: {err_text}")
                        return False
                    logger.info(f"Created segment '{segment_name}' at '{current_abs_path_str}'.")
                except Exception as e:
                    logger.error(f"Exception creating segment '{segment_name}': {e}")
                    return False
            
            parent_graph_api_path_suffix = segment_meta_graph_suffix # Update parent for next iteration

        logger.info(f"App root folder '{self.root_folder_path}' ensured.")
        return True

    async def download_file_content(self, cloud_file_path: str) -> Optional[bytes]:
        graph_path_suffix = self._get_graph_path_suffix(cloud_file_path)
        url_suffix = f"/me/drive/root{graph_path_suffix}/content"
        try:
            response = await self._make_graph_api_call("GET", url_suffix)
            if response and response.status_code == 200: return response.content
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404: logger.debug(f"File content not found (404) for '{cloud_file_path}'.")
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
        url_suffix = f"/me/drive/root{graph_path_suffix}/content?@microsoft.graph.conflictBehavior=replace" # replace, rename, or fail

        headers_override = {"Content-Type": "application/octet-stream"}
        if len(content_bytes) > SIMPLE_UPLOAD_MAX_SIZE_BYTES: # Basic Resumable Upload (not chunked)
            # 1. Create upload session
            session_url_suffix = f"/me/drive/root{graph_path_suffix}/createUploadSession"
            conflict_behavior = "replace" # or "rename", "fail"
            session_body = {"item": {"@microsoft.graph.conflictBehavior": conflict_behavior, "name": cloud_file_name}} # Name needed if path has special chars
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
                
                # 2. PUT to uploadUrl
                # For true resumable, this PUT would be chunked. For simplicity, one PUT.
                headers_upload = {"Content-Length": str(len(content_bytes)), "Content-Range": f"bytes 0-{len(content_bytes)-1}/{len(content_bytes)}"}
                # _make_graph_api_call uses self.graph_api_endpoint. We need to call upload_url directly.
                async with httpx.AsyncClient(timeout=None) as client: # Longer timeout for upload
                    response_upload = await client.put(upload_url, content=content_bytes, headers=headers_upload)
                
                if response_upload and (response_upload.status_code == 201 or response_upload.status_code == 200):
                    logger.info(f"Resumable upload successful for '{target_file_rel_path}'.")
                    return self._graph_item_to_cloudfile(response_upload.json(), target_file_rel_path)
                else:
                    logger.error(f"Resumable upload failed for '{target_file_rel_path}'. Status: {response_upload.status_code if response_upload else 'No response'}")
                    return None
            except Exception as e:
                logger.error(f"Exception during resumable upload for '{target_file_rel_path}': {e}", exc_info=True)
                return None
        else: # Simple PUT
            try:
                response = await self._make_graph_api_call("PUT", url_suffix, content=content_bytes, headers_extra=headers_override)
                if response and (response.status_code == 201 or response.status_code == 200):
                    return self._graph_item_to_cloudfile(response.json(), target_file_rel_path)
            except Exception: pass # Logged by helper
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
        url_suffix = f"/me/drive/root{graph_path_suffix}"
        try:
            response = await self._make_graph_api_call("DELETE", url_suffix)
            if response and (response.status_code == 204 or response.status_code == 404):
                if response.status_code == 404: logger.warning(f"Item '{cloud_file_path}' not found (already deleted?).")
                return True
        except httpx.HTTPStatusError as e:
             if e.response.status_code == 404: return True 
        return False
```
