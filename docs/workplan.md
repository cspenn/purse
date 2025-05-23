Okay, this is an excellent goal: creating a detailed, actionable workplan to address the identified issues and security recommendations.

Here's a Markdown workplan focusing on root causes, ordered by dependencies, with the level of detail requested.

```markdown
# Purse Application: Refinement and Security Hardening Workplan

**Overall Goal:** Enhance application security, robustness, and completeness by addressing audit feedback and incorporating best practices. This plan focuses on root cause fixes and detailed implementation steps.

---

## Phase 1: Core Enhancements & Security Foundations

### 1. `.gitignore`
*   **File Path**: `purse/.gitignore`
*   **Intent**: Specifies intentionally untracked files that Git should ignore to keep the repository clean and prevent accidental commits of sensitive or generated files.
*   **Upstream Dependencies**: None.
*   **Downstream Dependencies**: Git version control for the entire project.
*   **Changes Needed**:
    *   Create the file `purse/.gitignore`.
    *   Add the following content:

    ```gitignore
    # Byte-compiled / optimized / DLL files
    __pycache__/
    *.pyc
    *.pyo
    *.pyd

    # C extensions
    *.so

    # Distribution / packaging
    .Python
    build/
    develop-eggs/
    dist/
    downloads/
    eggs/
    .eggs/
    lib/
    lib64/
    parts/
    sdist/
    var/
    wheels/
    pip-wheel-metadata/
    share/python-wheels/
    *.egg-info/
    .installed.cfg
    *.egg
    MANIFEST

    # PyInstaller
    # Usually these files are written by a PyInstaller script; this is just an
    # example of what might be excluded if you choose to use PyInstaller
    # *.manifest
    # *.spec

    # Installer logs
    pip-log.txt
    pip-delete-this-directory.txt

    # Unit test / coverage reports
    htmlcov/
    .tox/
    .nox/
    .coverage
    .coverage.*
    .cache
    nosetests.xml
    coverage.xml
    *.cover
    *.py,cover
    .hypothesis/
    .pytest_cache/

    # Translations
    *.mo
    *.pot

    # Django stuff:
    *.log
    local_settings.py
    db.sqlite3
    db.sqlite3-journal

    # Flask stuff:
    instance/
    .webassets-cache

    # Scrapy stuff:
    .scrapy

    # Sphinx documentation
    docs/_build/

    # PyBuilder
    target/

    # Jupyter Notebook
    .ipynb_checkpoints

    # IPython
    profile_default/
    ipython_config.py

    # Environments
    .env
    .venv
    env/
    venv/
    ENV/
    env.bak/
    venv.bak/

    # Spyder project settings
    .spyderproject
    .spyderworkspace

    # Rope project settings
    .ropeproject

    # mkdocs documentation
    /site

    # mypy
    .mypy_cache/
    .dmypy.json
    dmypy.json

    # Pyre type checker
    .pyre/

    # OS generated files
    .DS_Store
    .DS_Store?
    ._*
    .Spotlight-V100
    .Trashes
    ehthumbs.db
    Thumbs.db

    # IDE specific files
    .idea/
    .vscode/
    *.swp
    *~
    *.sublime-project
    *.sublime-workspace

    # Purse specific
    logs/*.log                 # Application logs (files, not the directory itself)
    !logs/.gitkeep             # Allow keeping the logs directory if it's empty via .gitkeep
    temp_markdown_handler_test/ # Test directory for markdown_handler
    temp_logs_for_testing/     # Test directory for logger_setup
    *.test_results
    coverage.xml
    device_settings.yml        # Local, non-synced device settings
                               # (This was already handled by FileSystemManager pathing,
                               # but good to explicitly ignore if ever at project root by mistake)

    # Whoosh search index directory (assuming it's created under app_data_dir,
    # which should be outside the repo. If it were inside repo, it would be ignored)
    # search_index/ (if it was relative to project root)

    # OAuth tokens if ever accidentally stored in files (SHOULD USE KEYRING)
    *.token
    *_token.json
    client_secret*.json # Except if it's a template/example one
    !client_secret.example.json

    # If config.yml was user-specific and not a template (it IS a template in this project)
    # config.yml
    ```

---

### 2. Secure OAuth Token Management (`keyring` integration)
*   **Intent**: Modify cloud service classes and `main.py` to store and retrieve OAuth tokens using the `keyring` library instead of potentially storing them in `settings.yml`. This addresses a critical security gap.
*   **Upstream Dependencies**: `keyring` library (already in `pyproject.toml`).
*   **Downstream Dependencies**: Cloud service authentication logic, `main.py` token loading/saving.

#### 2.1. Update `src/purse/services/cloud_storage/base_cloud_service.py`
*   **File Path**: `src/purse/services/cloud_storage/base_cloud_service.py`
*   **Changes Needed**:
    *   Add methods for saving and loading tokens using `keyring`.
    *   Modify `__init__` to attempt loading tokens.
    *   Modify `exchange_code_for_token` to save tokens.
    *   Modify `refresh_access_token` to save updated tokens.

    ```python
    # src/purse/services/cloud_storage/base_cloud_service.py
    # ... (imports and CloudFileMetadata dataclass remain the same) ...
    import keyring # Add this import
    import json # For storing multiple token parts as a single string in keyring

    # ... (logger remains the same) ...

    class BaseCloudService(ABC):
        PROVIDER_NAME: str = "AbstractCloudProvider"

        def __init__(self, config_manager: 'ConfigManager', 
                     # Remove access_token, refresh_token from constructor, load them instead
                    ):
            self.config_manager = config_manager
            self.access_token: Optional[str] = None
            self.refresh_token: Optional[str] = None
            self.token_expiry_timestamp: Optional[float] = None # Store expiry as Unix timestamp
            
            self.root_folder_path: str = "/Apps/Purse" 
            self.user_id: Optional[str] = None # Cloud provider's user ID

            # Attempt to load tokens on initialization
            self._load_tokens_from_keyring()

        def _get_keyring_service_name(self) -> str:
            """Generates a unique service name for keyring based on provider and app ID."""
            app_id = self.config_manager.get('app_id', constants.APP_ID) # Get APP_ID from constants if not in config
            return f"{app_id}_{self.PROVIDER_NAME}"

        def _load_tokens_from_keyring(self) -> None:
            service_name = self._get_keyring_service_name()
            # Keyring stores username + password. We'll use user_id (or a placeholder) as username.
            # The "password" will be a JSON string containing access_token, refresh_token, expiry.
            # We need a way to get user_id if it's not yet known.
            # For initial load, if user_id is required to fetch tokens, this becomes tricky.
            # Let's assume we use a generic "token_bundle" as the username for keyring if user_id is not set.
            keyring_username = self.user_id or f"{self.PROVIDER_NAME}_tokens"
            
            try:
                token_bundle_str = keyring.get_password(service_name, keyring_username)
                if token_bundle_str:
                    token_data = json.loads(token_bundle_str)
                    self.access_token = token_data.get('access_token')
                    self.refresh_token = token_data.get('refresh_token')
                    self.token_expiry_timestamp = token_data.get('token_expiry_timestamp')
                    loaded_user_id = token_data.get('user_id')
                    if loaded_user_id and not self.user_id: # If user_id wasn't set but was in bundle
                        self.user_id = loaded_user_id
                    
                    logger.info(f"{self.PROVIDER_NAME}: Tokens loaded from keyring for user '{keyring_username}'.")
                    # Specific services might need to re-initialize their client here (e.g., self.dbx, self.creds)
                    self._reinitialize_client_with_loaded_tokens()
                else:
                    logger.info(f"{self.PROVIDER_NAME}: No tokens found in keyring for user '{keyring_username}'.")
            except Exception as e:
                logger.error(f"{self.PROVIDER_NAME}: Error loading tokens from keyring: {e}")

        def _save_tokens_to_keyring(self, token_data: Dict[str, Any]) -> None:
            """Saves token bundle to keyring."""
            service_name = self._get_keyring_service_name()
            keyring_username = self.user_id or f"{self.PROVIDER_NAME}_tokens"

            # Ensure essential tokens are present in token_data before overwriting keyring
            current_access = token_data.get('access_token', self.access_token)
            current_refresh = token_data.get('refresh_token', self.refresh_token)
            current_expiry = token_data.get('token_expiry_timestamp', self.token_expiry_timestamp)
            current_user_id = token_data.get('user_id', self.user_id)

            if not current_access: # Cannot save if no access token
                logger.warning(f"{self.PROVIDER_NAME}: Attempted to save tokens to keyring, but access token is missing.")
                return

            bundle_to_save = {
                'access_token': current_access,
                'refresh_token': current_refresh,
                'token_expiry_timestamp': current_expiry,
                'user_id': current_user_id # Persist user_id with tokens
            }
            try:
                keyring.set_password(service_name, keyring_username, json.dumps(bundle_to_save))
                logger.info(f"{self.PROVIDER_NAME}: Tokens saved to keyring for user '{keyring_username}'.")
                # Update current instance's tokens
                self.access_token = current_access
                self.refresh_token = current_refresh
                self.token_expiry_timestamp = current_expiry
                if current_user_id: self.user_id = current_user_id # Update self.user_id if provided
            except Exception as e:
                logger.error(f"{self.PROVIDER_NAME}: Error saving tokens to keyring: {e}")
        
        def _delete_tokens_from_keyring(self) -> None:
            """Deletes tokens from keyring, e.g., on logout or auth error."""
            service_name = self._get_keyring_service_name()
            keyring_username = self.user_id or f"{self.PROVIDER_NAME}_tokens"
            try:
                keyring.delete_password(service_name, keyring_username)
                logger.info(f"{self.PROVIDER_NAME}: Tokens deleted from keyring for user '{keyring_username}'.")
            except keyring.errors.PasswordDeleteError:
                logger.info(f"{self.PROVIDER_NAME}: No tokens found in keyring to delete for user '{keyring_username}'.")
            except Exception as e:
                logger.error(f"{self.PROVIDER_NAME}: Error deleting tokens from keyring: {e}")
            finally:
                # Clear tokens from current instance
                self.access_token = None
                self.refresh_token = None
                self.token_expiry_timestamp = None
                # self.user_id might be kept or cleared depending on logout strategy

        @abstractmethod
        def _reinitialize_client_with_loaded_tokens(self) -> None:
            """
            Called after tokens are loaded from keyring.
            Subclasses should re-initialize their specific HTTP client (e.g., self.dbx, self.creds)
            using self.access_token, self.refresh_token, etc.
            """
            pass

        # ... (authenticate_url remains the same) ...

        @abstractmethod
        async def exchange_code_for_token(self, auth_code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
            """
            Exchanges an authorization code for an access token and refresh token.
            IMPLEMENTATIONS MUST CALL self._save_tokens_to_keyring(token_dict) upon success.
            IMPLEMENTATIONS MUST set self.user_id from the token response if available.
            """
            pass

        @abstractmethod
        async def refresh_access_token(self) -> Optional[str]:
            """
            Refreshes the access token using the stored refresh token.
            IMPLEMENTATIONS MUST CALL self._save_tokens_to_keyring(new_token_dict) if tokens change.
            """
            pass
        
        # ... (other abstract methods and concrete methods remain the same) ...
    ```

#### 2.2. Update Cloud Service Implementations
*   **Files**:
    *   `src/purse/services/cloud_storage/dropbox_service.py`
    *   `src/purse/services/cloud_storage/google_drive_service.py`
    *   `src/purse/services/cloud_storage/onedrive_service.py`
*   **Changes Needed (General for each provider):**
    1.  **Modify `__init__`**:
        *   Remove `access_token`, `refresh_token`, etc. from constructor parameters.
        *   Call `super().__init__(config_manager)`. `_load_tokens_from_keyring()` will be called by base.
        *   The client initialization (`self.dbx`, `self.creds`, `self.msal_app`) should happen *after* `super().__init__` and potentially in `_reinitialize_client_with_loaded_tokens`.
    2.  **Implement `_reinitialize_client_with_loaded_tokens(self)`**:
        *   This method will contain the logic to set up the provider-specific client (`self.dbx`, `self.creds` + `_drive_service_instance=None`, or re-init `self.msal_app` with cache) using `self.access_token`, `self.refresh_token`, `self.token_expiry_timestamp`, and `self.user_id` (for MSAL's `home_account_id`).
    3.  **In `exchange_code_for_token(self, ...)`**:
        *   After successfully obtaining tokens from the provider, create a dictionary `token_dict` with `access_token`, `refresh_token`, `user_id` (provider's user ID), and `token_expiry_timestamp` (converted to Unix timestamp float).
        *   Call `self._save_tokens_to_keyring(token_dict)`.
        *   Ensure `self.user_id` is set on the instance.
        *   Call `self._reinitialize_client_with_loaded_tokens()` to setup the client with new tokens.
        *   Return the token dictionary (or a subset as per original signature).
    4.  **In `refresh_access_token(self)`**:
        *   After a successful token refresh by the provider's SDK or manual refresh logic:
            *   Update `self.access_token`, `self.refresh_token` (if it changed, rare), `self.token_expiry_timestamp`.
            *   Create `token_dict` with these new values.
            *   Call `self._save_tokens_to_keyring(token_dict)`.
            *   Call `self._reinitialize_client_with_loaded_tokens()`.
            *   Return the new `self.access_token`.
    5.  **Handle Token Expiry/Invalidity**: In methods that make API calls (like `_run_sync` for Dropbox, or before calls in GDrive/OneDrive):
        *   Check `self.token_expiry_timestamp` (if available) against `time.time()`.
        *   If expired or about to expire, or if an `AuthError` / 401 occurs, attempt `await self.refresh_access_token()`.
        *   If refresh fails, then fail the operation. This makes token refresh more proactive or reactive.

*   **Example Diff for `dropbox_service.py` `__init__` and `_reinitialize_client_with_loaded_tokens`**:
    ```diff
    # src/purse/services/cloud_storage/dropbox_service.py
    # ...
    class DropboxService(BaseCloudService):
        PROVIDER_NAME = "Dropbox"

        def __init__(self, 
                     config_manager: 'ConfigManager', 
-                    access_token: Optional[str] = None, 
-                    refresh_token: Optional[str] = None,
-                    expires_at: Optional[int] = None): # Unix timestamp for expiry
-            super().__init__(config_manager, access_token, refresh_token)
+                   ): 
+            super().__init__(config_manager) # This calls _load_tokens_from_keyring
            
            self.app_key: Optional[str] = self.config_manager.get('cloud_providers.dropbox.app_key')
            self.app_secret: Optional[str] = self.config_manager.get('cloud_providers.dropbox.app_secret')
            self.redirect_uri: Optional[str] = self.config_manager.get('cloud_providers.dropbox.redirect_uri')
            
-            self.expires_at = expires_at # Store when the current access_token expires
+            # self.token_expiry_timestamp is inherited from BaseCloudService and set by _load_tokens_from_keyring

            if not self.app_key or not self.app_secret: 
                logger.error(f"{self.PROVIDER_NAME}: App key or app secret not configured. Some operations may fail.")

            self.dbx: Optional[dropbox.Dropbox] = None
-            if self.access_token:
-                self.dbx = dropbox.Dropbox(oauth2_access_token=self.access_token)
-            elif self.refresh_token and self.app_key and self.app_secret:
-                logger.info(f"{self.PROVIDER_NAME}: Initializing with refresh token. Access token will be obtained on first call.")
-                self.dbx = dropbox.Dropbox(
-                    oauth2_refresh_token=self.refresh_token,
-                    app_key=self.app_key,
-                    app_secret=self.app_secret,
-                    oauth2_access_token_expiration=self.expires_at # Pass expiry if known
-                )
-            else:
-                logger.warning(f"{self.PROVIDER_NAME}: Not enough information to initialize Dropbox client (no access/refresh token or app credentials).")
+            self._reinitialize_client_with_loaded_tokens() # Initialize client if tokens were loaded

+        def _reinitialize_client_with_loaded_tokens(self) -> None:
+            if self.access_token:
+                logger.debug(f"{self.PROVIDER_NAME}: Reinitializing client with access token.")
+                self.dbx = dropbox.Dropbox(
+                    oauth2_access_token=self.access_token,
+                    oauth2_refresh_token=self.refresh_token, # Pass refresh token if available
+                    app_key=self.app_key,                   # Needed for potential auto-refresh
+                    app_secret=self.app_secret,             # Needed for potential auto-refresh
+                    oauth2_access_token_expiration=datetime.fromtimestamp(self.token_expiry_timestamp, tz=timezone.utc) if self.token_expiry_timestamp else None
+                )
+            elif self.refresh_token and self.app_key and self.app_secret:
+                logger.info(f"{self.PROVIDER_NAME}: Reinitializing client with refresh token only.")
+                self.dbx = dropbox.Dropbox(
+                    oauth2_refresh_token=self.refresh_token,
+                    app_key=self.app_key,
+                    app_secret=self.app_secret,
+                    oauth2_access_token_expiration=datetime.fromtimestamp(self.token_expiry_timestamp, tz=timezone.utc) if self.token_expiry_timestamp else None
+                )
+            else:
+                self.dbx = None # No tokens, no client
+                logger.debug(f"{self.PROVIDER_NAME}: No tokens available, Dropbox client not initialized.")

        async def _run_sync(self, func, *args: Any, **kwargs: Any) -> Any:
            if self.dbx is None:
                logger.error(f"{self.PROVIDER_NAME}: Dropbox client not initialized. Cannot run function.")
                # Attempt to reinitialize if tokens might have become available (e.g. after auth)
+                self._reinitialize_client_with_loaded_tokens()
+                if self.dbx is None: # Still no client
+                    raise ConnectionError("Dropbox client not initialized.")

-            if self.expires_at and self.expires_at < time.time() - 60: # 60s buffer
+            if self.token_expiry_timestamp and self.token_expiry_timestamp < time.time() - 60: # 60s buffer
                logger.info(f"{self.PROVIDER_NAME}: Access token may be expired. Attempting refresh.")
                if not await self.refresh_access_token():
                     raise AuthError("Token refresh failed or not possible.", user_message="Access token expired and refresh failed.")
    # ...
    ```
    *   **Dropbox `exchange_code_for_token` example addition:**
        ```python
        # Inside DropboxService.exchange_code_for_token, after getting oauth_result:
        # ...
            token_dict_to_save = {
                'access_token': oauth_result.access_token,
                'refresh_token': oauth_result.refresh_token,
                'user_id': oauth_result.account_id, # This is Dropbox specific user_id
                'token_expiry_timestamp': oauth_result.expires_at.timestamp() if oauth_result.expires_at else None
            }
            self._save_tokens_to_keyring(token_dict_to_save)
            self._reinitialize_client_with_loaded_tokens() # Setup self.dbx with new tokens

            return { # Return structure as per BaseCloudService (or original method if different)
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'user_id': self.user_id,
                'expires_at': self.token_expiry_timestamp,
                'scope': oauth_result.scope
            }
        # ...
        ```
    *   **Dropbox `refresh_access_token` example addition:**
        ```python
        # Inside DropboxService.refresh_access_token
        # ...
        # After successful SDK auto-refresh (which is tricky to detect new token string from)
        # For Dropbox, if SDK auto-refreshes, we may not get the new token string easily.
        # If we had a manual refresh that returned new token details:
        # new_token_details = # ... result of manual refresh
        # self.access_token = new_token_details['access_token']
        # self.token_expiry_timestamp = new_token_details['expires_at_timestamp']
        # if 'refresh_token' in new_token_details: self.refresh_token = new_token_details['refresh_token']
        # self._save_tokens_to_keyring({
        #     'access_token': self.access_token,
        #     'refresh_token': self.refresh_token,
        #     'user_id': self.user_id,
        #     'token_expiry_timestamp': self.token_expiry_timestamp
        # })
        # self._reinitialize_client_with_loaded_tokens()
        # return self.access_token
        # FOR NOW, with Dropbox SDK auto-refresh, we assume the current tokens in self.dbx are live.
        # We don't save back to keyring unless we explicitly performed a refresh that yields new token strings.
        # The current Dropbox implementation relies on SDK's internal refresh.
        # If we need to persist tokens after an SDK's *internal* refresh, that's much harder.
        # The current call to users_get_current_account in refresh_access_token tests if the client works.
        # It does NOT guarantee self.access_token string is the *newest* one if SDK auto-refreshed.
        # This is a limitation for persisting the *absolute latest* token from Dropbox auto-refresh.
        #
        # Revised logic for Dropbox `refresh_access_token`:
        # If a call like `self.dbx.users_get_current_account()` succeeds after an expiry,
        # it implies the SDK handled it. We don't get new token details to save back.
        # So, `_save_tokens_to_keyring` might not be called here unless we do a manual refresh.
        # The current design is okay for usability but not for persisting latest token from *implicit* SDK refresh.
        # For an *explicit* refresh (if SDK offered it cleanly returning new tokens), saving would be vital.
        #
        # Simplification: `refresh_access_token` is more about *ensuring the client is usable*.
        # Saving tokens to keyring is primarily after *explicit* user auth (`exchange_code`)
        # or if an explicit refresh mechanism *returns new token strings*.
        ```
        *Self-correction*: For Dropbox SDK, if initialized with `oauth2_refresh_token`, `app_key`, `app_secret`, and `oauth2_access_token_expiration`, it *will* attempt to auto-refresh. The `Dropbox` object itself will then use the new token internally. The challenge is getting that new token *out* of the SDK to save it to keyring. If the SDK doesn't expose it, then the token in keyring might become stale even if the app continues to work (until the refresh token itself becomes invalid). This is a common SDK design choice. For now, the priority is functional security; perfect token state persistence across implicit refreshes is a deeper SDK integration issue.

        *Apply similar constructor, `_reinitialize_client_with_loaded_tokens`, `exchange_code_for_token`, and `refresh_access_token` modifications to `GoogleDriveService` and `OneDriveService`*, ensuring their specific token attributes (`self.creds` for Google, MSAL cache for OneDrive) are handled correctly during reinitialization and saving. For Google, `self.creds.expiry` is a datetime, convert to timestamp for `token_expiry_timestamp`. For MSAL, saving involves serializing `self.msal_cache` and storing `self.home_account_id`.

#### 2.3. Update `src/purse/main.py`
*   **File Path**: `src/purse/main.py`
*   **Changes Needed**:
    *   Modify `_initialize_cloud_and_sync` to no longer pass tokens directly from `ConfigManager` to cloud service constructors. The services will load them from keyring.
    *   Remove token-related keys from `ConfigManager.get()` calls in `_initialize_cloud_and_sync`.
    *   The UI flow for initiating OAuth and handling the callback will eventually call `cloud_service.authenticate_url()` and `cloud_service.exchange_code_for_token()`. The latter will save tokens to keyring.

    ```diff
    # src/purse/main.py
    # ...
    class PurseApp(toga.App):
    # ...
        def _initialize_cloud_and_sync(self) -> None:
            logger.debug("Initializing cloud service and SyncManager...")
            provider_name = self.config_manager.get('cloud.provider_name') # From settings.yml
            
-            # These tokens and cache should ideally be loaded securely...
-            access_token = self.config_manager.get('cloud.tokens.access_token') 
-            refresh_token = self.config_manager.get('cloud.tokens.refresh_token')
-            dbx_expires_at = self.config_manager.get('cloud.tokens.dropbox.expires_at') 
-            msal_cache_str = self.config_manager.get('cloud.tokens.onedrive.msal_cache')
-            msal_home_account_id = self.config_manager.get('cloud.tokens.onedrive.home_account_id')
-            gdrive_token_uri = self.config_manager.get('cloud_providers.google_drive.token_uri') 
-            gdrive_client_id = self.config_manager.get('cloud_providers.google_drive.client_id')
-            gdrive_client_secret = self.config_manager.get('cloud_providers.google_drive.client_secret')
-            gdrive_scopes = self.config_manager.get('cloud_providers.google_drive.scopes')
-            gdrive_token_expiry_iso = self.config_manager.get('cloud.tokens.google_drive.token_expiry_iso')

            user_cloud_root_path = self.config_manager.get('cloud.user_root_folder_path', '/Apps/Purse')

            if provider_name:
                logger.info(f"Configured cloud provider: {provider_name}. Initializing client...")
                if provider_name == DropboxService.PROVIDER_NAME:
                    self.cloud_service = DropboxService(self.config_manager)
                elif provider_name == GoogleDriveService.PROVIDER_NAME:
                    # GoogleDriveService constructor now takes config_manager only.
                    # It will load specific GDrive client_id, secret, etc., from config_manager internally
                    # and tokens from keyring.
                    self.cloud_service = GoogleDriveService(self.config_manager)
                elif provider_name == OneDriveService.PROVIDER_NAME:
                    # OneDriveService constructor takes config_manager.
                    # It will load msal_cache_str and home_account_id from keyring bundle if stored there,
                    # or from its initial empty state.
                    self.cloud_service = OneDriveService(self.config_manager)
                else:
                    logger.error(f"Unsupported cloud provider configured: '{provider_name}'. Sync will be disabled.")
                    self.app_state.cloud_provider_name = f"Unsupported: {provider_name}"
                    return
    # ...
    ```
    *   **Note**: The `_initialize_cloud_and_sync` method is now simpler. The responsibility of loading/managing tokens is pushed down into the respective cloud service classes and the base class using `keyring`. The UI part of the application will be responsible for initiating the OAuth flow where the user authenticates, and `exchange_code_for_token` is called, which then saves tokens to the keyring. On subsequent app starts, the services will attempt to load from keyring.

---

### 3. Input Size Limits (DoS Mitigation for Parsers)
*   **Intent**: Add configurable limits to the size of content fetched and passed to parsers to prevent DoS attacks from excessively large files/pages.
*   **Upstream Dependencies**: `config.yml` for new limit settings.
*   **Downstream Dependencies**: `ContentParserService`, `HttpClient`.

#### 3.1. Update `purse/config.yml`
*   **File Path**: `purse/config.yml`
*   **Changes Needed**: Add new section for content size limits.

    ```diff
    # ... (previous config) ...
    # Pocket Importer settings
    pocket_importer:
      reparse_pocket_html: true

+   # Content processing limits
+   content_limits:
+     max_html_size_bytes: 10485760  # 10 MB
+     max_pdf_size_bytes: 52428800   # 50 MB
+     max_docx_size_bytes: 20971520  # 20 MB

    # Cloud Provider App Credentials
    # ... (rest of config) ...
    ```

#### 3.2. Update `src/purse/services/http_client.py`
*   **File Path**: `src/purse/services/http_client.py`
*   **Changes Needed**: Modify `get_url` to respect `max_html_size_bytes` and stream response if necessary to check size before reading all content. (Note: `httpx` default behavior might already load into memory for `response.text`. This needs careful handling for true streaming and size check before full load).
    *   For simplicity and given `httpx` patterns, we'll first check `Content-Length` header. If it's too large or absent, we might need to stream or reject. For now, header check is a pragmatic first step.

    ```diff
    # src/purse/services/http_client.py
    # ...
    class HttpClient:
        def __init__(self, config_manager: 'ConfigManager'):
            self.config_manager = config_manager
            default_timeout = 30.0
            self.client = httpx.AsyncClient( # ... as before ... )
            self.retry_config = common.get_retry_config(self.config_manager)
+           self.max_html_size_bytes = self.config_manager.get('content_limits.max_html_size_bytes', 10 * 1024 * 1024)

        async def get_url(
            self,
            url: str,
            headers: Optional[Dict[str, str]] = None,
            params: Optional[Dict[str, Any]] = None,
            timeout: Optional[float] = None,
+           is_html_content: bool = True # Flag to apply HTML size limit
        ) -> httpx.Response:
            # ... (decorator and _fetch_with_retry setup as before) ...
            @common.exponential_backoff_retry(
                # ... retry params ...
            )
            async def _fetch_with_retry() -> httpx.Response:
                # ... (effective_headers, effective_timeout setup) ...
                logger.debug(f"Fetching URL: {url} with params: {params}, timeout: {effective_timeout}")
            
                try:
+                   # For HTML content, first try a HEAD request if server supports to check Content-Length
+                   # This is an optimization and might not always work or be desirable.
+                   # A more robust way is to stream the GET response if size is a major concern.
+                   # For now, proceed with GET and check Content-Length if present on GET response.
+
                    response = await self.client.get( # ... as before ... )

+                   if is_html_content:
+                       content_length_str = response.headers.get('Content-Length')
+                       if content_length_str:
+                           try:
+                               content_length = int(content_length_str)
+                               if content_length > self.max_html_size_bytes:
+                                   logger.warning(f"Content-Length {content_length} for {url} exceeds limit {self.max_html_size_bytes}. Raising error.")
+                                   # Create a custom exception or use a generic one
+                                   raise httpx.HTTPError(f"Content too large: {content_length} bytes exceeds limit {self.max_html_size_bytes}.")
+                           except ValueError:
+                               logger.warning(f"Could not parse Content-Length header '{content_length_str}' for {url}.")
+                       # If Content-Length is missing, we proceed but Trafilatura might need to handle large data carefully.
+                       # True streaming and byte-counting before full .text access is more complex with httpx's .text.
+                       # response.content is bytes, response.text decodes.
+                       # For now, this header check is a best-effort.
+
                    response.raise_for_status() 
                    logger.info(f"🟢 Successfully fetched {url}, status: {response.status_code}")
                    return response
    # ... (rest of the class) ...
    ```
    *   **Note:** Truly enforcing size limits *before* downloading full content with `httpx` often requires streaming the response (`async with client.stream(...) as response:`) and manually counting bytes. The `Content-Length` header check is a good first pass. If `is_html_content` is True, the size limit is checked.

#### 3.3. Update `src/purse/services/content_parser.py`
*   **File Path**: `src/purse/services/content_parser.py`
*   **Changes Needed**:
    *   Pass `is_html_content=True` to `http_client.get_url`.
    *   For PDF and DOCX, the files are first downloaded (or passed as bytes). `FileSystemManager` or the UI layer that handles file selection should ideally perform size checks *before* passing bytes to `parse_pdf_from_bytes` or `parse_docx_from_bytes`.
    *   Add size checks within `parse_pdf_from_bytes` and `parse_docx_from_bytes` for the passed `bytes` arguments.

    ```diff
    # src/purse/services/content_parser.py
    # ...
    class ContentParserService:
        def __init__(self, http_client: HttpClient, config_manager: 'ConfigManager'):
            self.http_client = http_client
            self.config_manager = config_manager
            self.retry_config = common.get_retry_config(self.config_manager)
+           self.max_pdf_size_bytes = self.config_manager.get('content_limits.max_pdf_size_bytes', 50 * 1024 * 1024)
+           self.max_docx_size_bytes = self.config_manager.get('content_limits.max_docx_size_bytes', 20 * 1024 * 1024)

        async def parse_url(self, url: str, use_fallback: bool = True) -> Optional[Article]:
            # ...
            try:
-               response = await self.http_client.get_url(url)
+               response = await self.http_client.get_url(url, is_html_content=True)
                content_html = response.text
            except Exception as e: # This will now also catch the "Content too large" error from HttpClient
                logger.warning(f"🟡 Failed to fetch directly from {url}: {e}")
                # ... (fallback logic as before) ...
                if isinstance(e, httpx.HTTPError) and "Content too large" in str(e): # Specific handling
                    return self.create_bookmark_article(url, title=f"Bookmark (Content Too Large): {url}", notes=f"Content at {url} exceeded size limits.")
            # ...
            archive_template = self.config_manager.get('fallback_archive_service_url_template')
            if archive_template:
                # ...
                try:
-                   response = await self.http_client.get_url(archive_url, timeout=60.0)
+                   response = await self.http_client.get_url(archive_url, timeout=60.0, is_html_content=True)
                    content_html = response.text
                # ... (rest of fallback logic) ...
            # ... (rest of parse_url) ...

        def parse_pdf_from_bytes(self, pdf_bytes: bytes, original_url: str = "local.pdf") -> Optional[Article]:
+           if len(pdf_bytes) > self.max_pdf_size_bytes:
+               logger.warning(f"PDF content size {len(pdf_bytes)} for '{original_url}' exceeds limit {self.max_pdf_size_bytes}.")
+               return self.create_bookmark_article(
+                   url=original_url,
+                   title=f"PDF (File Too Large): {Path(original_url).name}",
+                   notes=f"PDF file '{original_url}' is too large to process (size: {len(pdf_bytes)} bytes)."
+               )
            logger.info(f"🟢 Attempting to parse PDF: {original_url}")
            # ... (rest of PDF parsing) ...

        def parse_docx_from_bytes(self, docx_bytes: bytes, original_url: str = "local.docx") -> Optional[Article]:
+           if len(docx_bytes) > self.max_docx_size_bytes:
+               logger.warning(f"DOCX content size {len(docx_bytes)} for '{original_url}' exceeds limit {self.max_docx_size_bytes}.")
+               return self.create_bookmark_article(
+                   url=original_url,
+                   title=f"DOCX (File Too Large): {Path(original_url).name}",
+                   notes=f"DOCX file '{original_url}' is too large to process (size: {len(docx_bytes)} bytes)."
+               )
            logger.info(f"🟢 Attempting to parse DOCX: {original_url}")
            # ... (rest of DOCX parsing) ...
    # ...
    ```

---

### 4. Mechanism for `ConfigManager` Reload After Settings Sync
*   **Intent**: Provide a way for the main application to detect that `settings.yml` has been updated by `SyncManager` and trigger a reload of configurations and apply them to the `AppState` and relevant services.
*   **Upstream Dependencies**: `SyncManager` downloading `settings.yml`.
*   **Downstream Dependencies**: `PurseApp` main logic, `ConfigManager`, `AppState`, potentially other services.

#### 4.1. Update `src/purse/services/sync_manager.py`
*   **File Path**: `src/purse/services/sync_manager.py`
*   **Changes Needed**: `_sync_settings_file` should return a flag if settings were downloaded/changed.

    ```diff
    # src/purse/services/sync_manager.py
    # ...
    class SyncManager:
    # ...
-       async def _sync_settings_file(self):
+       async def _sync_settings_file(self) -> bool:
+           """Synchronizes settings.yml. Returns True if local settings.yml was changed (downloaded)."""
            logger.info("Syncing settings.yml...")
+           settings_changed_locally = False
            # ... (existing logic for determining paths, getting cloud_meta, local_exists) ...

            if not local_settings_path:
                logger.error("🛑 Cannot sync settings: local settings path could not be determined (sync root not set?).")
-               return
+               return False

            # ... (existing logic for upload if local only) ...
            # ...
            elif not local_exists and cloud_meta: # Cloud only, download
                logger.info(f"Cloud '{cloud_settings_rel_path}' exists, not locally. Downloading.")
                local_settings_path.parent.mkdir(parents=True, exist_ok=True)
                download_success = await self.cloud_service.download_file(cloud_settings_rel_path, local_settings_path)
+               if download_success:
+                   settings_changed_locally = True
                logger.info(f"'{local_settings_path.name}' downloaded. Application may need to reload settings.")
            elif local_exists and local_mtime is not None and cloud_meta: # Exists in both
                if abs(local_mtime - cloud_meta.modified_timestamp) > 2.0: # Timestamp tolerance
                    if local_mtime > cloud_meta.modified_timestamp:
                        # ... (upload logic) ...
                    else: # Cloud is newer
                        self._log_conflict(f"Conflict for '{local_settings_path.name}'. Cloud is newer. Downloading.")
                        download_success = await self.cloud_service.download_file(cloud_settings_rel_path, local_settings_path)
+                       if download_success:
+                           settings_changed_locally = True
                        logger.info(f"'{local_settings_path.name}' downloaded due to conflict. Application may need to reload settings.")
            # ...
            logger.info("Settings.yml sync attempt complete.")
+           return settings_changed_locally

        async def synchronize_articles(self, force_full_rescan: bool = False) -> bool: # Changed return type
            """Performs a two-way sync. Returns True if synced settings.yml was changed locally."""
+           synced_settings_changed = False
            async with self._sync_lock:
                # ... (existing sync logic for articles) ...

-               await self._sync_settings_file() # Sync settings.yml
+               synced_settings_changed = await self._sync_settings_file() # Sync settings.yml

                # ... (logging sync completion) ...
                self._last_sync_time_utc = time.time()
+           return synced_settings_changed
    # ...
    ```

#### 4.2. Update `src/purse/main.py`
*   **File Path**: `src/purse/main.py`
*   **Changes Needed**: `PurseApp` needs a method to explicitly reload and apply settings. The background sync task should call this if `synchronize_articles` indicates settings changed.

    ```diff
    # src/purse/main.py
    # ...
    class PurseApp(toga.App):
        def startup(self):
            # ... (initialization as before) ...
            logger.info("Main window shown.")

            # 5. Initial background tasks
            self.add_background_task(self.run_initial_background_tasks) # Renamed for clarity

        def reload_and_apply_synced_settings(self):
            """Force reloads settings.yml and updates app state and services."""
            logger.info("Reloading and applying synced settings...")
            synced_settings_path = self.fs_manager.get_synced_settings_path()
            if synced_settings_path and synced_settings_path.exists():
                self.config_manager.load_settings(synced_settings_path)
                logger.info(f"Refreshed ConfigManager with settings from {synced_settings_path}.")
                self._update_app_state_from_synced_settings()
                # Potentially re-initialize or update parts of services if their config changed dramatically
                # For example, if cloud provider details changed (though less likely from settings.yml)
                # or if developer_notifications_url changed in NotificationService.
                # _update_app_state_from_synced_settings already updates NotificationService URL.
                
                # Re-initialize cloud service if provider details in settings changed
                # This might be too disruptive if not handled carefully (e.g. mid-operation)
                # For now, _update_app_state_from_synced_settings handles most settings updates.
                # A full re-init of cloud service might be needed if provider_name itself changes.
                # Let's call _initialize_cloud_and_sync again, it's designed to be somewhat idempotent
                # or at least re-evaluate based on current config.
                logger.info("Re-evaluating cloud service initialization after settings reload.")
                self._initialize_cloud_and_sync() # This will check current config and set up services

                # Update UI elements that depend on these settings if not automatically bound
                # Example: Update reading view fonts/theme if it's currently displayed.
                # This would involve calling refresh methods on relevant Toga widgets.
                # TODO: Add UI refresh calls here when UI is implemented.

                logger.info("Synced settings reloaded and applied.")
            else:
                logger.warning("Attempted to reload synced settings, but settings.yml not found or path unavailable.")


        async def run_initial_background_tasks(self, app_widget, **kwargs): # Renamed, app_widget is toga.App
            logger.info("Running initial background tasks...")
            
            # Example: Fetch developer notifications
            if self.notification_service:
                # Pass a callback to show notifications in UI when available
                # For now, just log. UI would handle display.
                logger.debug("Fetching developer notifications in background...")
                dev_notifications = await self.notification_service.fetch_developer_notifications()
                if dev_notifications:
                    logger.info(f"Fetched {len(dev_notifications)} new developer notifications.")
                    # In a real UI, you'd pass these to a UI component to display.
                    # Example: self.ui_controller.display_dev_notifications(dev_notifications)
                    # For now, maybe show the first one if Toga is up:
                    if self.main_window and dev_notifications.id not in self.notification_service.seen_notification_ids:
                         self.notification_service.show_system_notification(
                             f"Update: {dev_notifications.title}",
                             dev_notifications.message
                         )
                         self.notification_service.mark_notification_seen(dev_notifications.id)


            # Example: Trigger initial sync if configured
            if self.sync_manager:
                logger.info("Attempting initial background sync...")
                try:
                    settings_changed_by_sync = await self.sync_manager.synchronize_articles()
                    if settings_changed_by_sync:
                        logger.info("Settings.yml was updated during sync. Reloading configurations.")
                        self.reload_and_apply_synced_settings()
                    self.app_state.last_sync_status = "Success" # Update AppState
                    if self.app_state.status_label_widget:
                        self.app_state.status_label_widget.text = f"Sync complete: {datetime.now().strftime('%H:%M:%S')}"
                except Exception as e:
                    logger.error(f"Initial background sync failed: {e}", exc_info=True)
                    self.app_state.last_sync_status = f"Failed: {e}"
                    if self.app_state.status_label_widget:
                         self.app_state.status_label_widget.text = f"Sync failed: {datetime.now().strftime('%H:%M:%S')}"

            logger.info("Initial background tasks complete.")

    # ... (rest of PurseApp and main function) ...
    ```

---

## Phase 2: Security Hardening & Refinements

### 5. Thumbnail Image Fetching Orchestration
*   **Intent**: Implement the logic to actually download thumbnail images identified by `ContentParserService` and save them using `FileSystemManager`.
*   **Upstream Dependencies**: `ContentParserService` (identifies `potential_thumbnail_source_url`), `HttpClient` (to fetch), `FileSystemManager` (to save).
*   **Downstream Dependencies**: Article saving/import process.

#### 5.1. Add Orchestration Method (e.g., in `src/purse/main.py` or a new ArticleOps service)
*   **File Path**: `src/purse/main.py` (or a new `ArticleOperationsService`)
*   **Changes Needed**: Create an async helper function that's called after an `Article` object is successfully parsed and *before* or *just after* it's saved by `FileSystemManager`.

    ```python
    # src/purse/main.py (within PurseApp class or a new service)

    # Add this method to PurseApp or a relevant service
    async def _fetch_and_store_article_thumbnail(self, article: Article):
        """Fetches and stores thumbnail if a potential URL is available on the article."""
        if not article.potential_thumbnail_source_url:
            logger.debug(f"No potential thumbnail URL for article '{article.title}'. Skipping thumbnail fetch.")
            return

        if not self.http_client or not self.fs_manager:
            logger.error("HttpClient or FileSystemManager not available. Cannot fetch thumbnail.")
            return
        
        # Ensure article has a local_path or a prospective one for thumbnail saving logic
        if not article.local_path:
            prospective_path = self.fs_manager.get_article_filepath(article)
            if not prospective_path:
                logger.warning(f"Cannot determine path for article '{article.title}', cannot save thumbnail if fetched.")
                # We could proceed to fetch and then fail to save, or stop here.
                # Let's stop, as saving is the goal.
                return
            # We don't set article.local_path here, as the article file itself isn't saved yet.
            # FileSystemManager.get_thumbnail_path will use this prospective path.

        logger.info(f"Attempting to fetch thumbnail for '{article.title}' from: {article.potential_thumbnail_source_url}")
        try:
            # Fetch image (HttpClient's get_url with is_html_content=False to bypass HTML size limits)
            image_response = await self.http_client.get_url(
                article.potential_thumbnail_source_url, 
                is_html_content=False # This is an image, not HTML page
            )
            image_bytes = image_response.content

            # TODO (Optional Enhancement): Validate image_bytes (e.g., using Pillow to check if it's a valid image)
            # TODO (Optional Enhancement): Resize/reformat image using Pillow to a standard thumbnail size/format.

            relative_thumb_path = self.fs_manager.save_thumbnail(article, image_bytes)
            if relative_thumb_path:
                logger.info(f"Thumbnail saved for article '{article.title}' at relative path: {relative_thumb_path}")
                # The article object's thumbnail_url_local is updated by save_thumbnail.
                # If the article object is saved again after this, this new path will be in its YAML.
            else:
                logger.warning(f"Failed to save thumbnail for article '{article.title}'.")
        except Exception as e:
            logger.error(f"Error fetching or saving thumbnail for article '{article.title}' from '{article.potential_thumbnail_source_url}': {e}", exc_info=True)
        finally:
            # Clear the transient URL after attempting to fetch, regardless of success
            article.potential_thumbnail_source_url = None
    ```

*   **Integration Points:**
    *   **`ContentParserService.parse_url`**: After successfully creating an `Article` object and setting `potential_thumbnail_source_url`, *do not* call `_fetch_and_store_article_thumbnail` directly from here. `ContentParserService` should only parse.
    *   **`PocketImporterService.import_from_pocket_file`**: After `article = await self.content_parser.parse_url(url)` and *before* `self.fs_manager.save_article(article)` or *just after saving the main article*:
        ```python
        # Inside PocketImporterService.import_from_pocket_file loop:
        # ...
        if article:
            # ... (apply Pocket metadata to article) ...
            # Fetch thumbnail *before* saving article so thumbnail_url_local is in YAML
            # This assumes self has access to the main app's instance or necessary services like http_client.
            # If PocketImporterService is part of PurseApp, it can call app_instance._fetch_and_store_article_thumbnail.
            # For now, let's assume this service needs access to http_client for this.
            # Add http_client to PocketImporterService constructor if it's not there.
            # (Looking at existing code, PocketImporterService doesn't have http_client)
            # This implies the main app should orchestrate this.

            # Option 1: Orchestrate in main app after import returns article object
            # Option 2: Pass http_client to importer (less clean separation)
            # Option 3: Let `FileSystemManager.save_article` handle it if Article has potential_thumbnail_source_url (complexifies FSM)

            # Preferred: Orchestrate in the calling code (e.g., UI command handler for import, or main app logic)
            # For now, we'll modify main.py to call this after an article is newly added.
            # Example: If a UI "Add URL" command results in a new `article` object:
            #   app_instance.fs_manager.save_article(newly_parsed_article)
            #   await app_instance._fetch_and_store_article_thumbnail(newly_parsed_article)
            #   app_instance.fs_manager.save_article(newly_parsed_article) # Save again to include thumbnail path in YAML
            #   app_instance.search_manager.add_or_update_article(newly_parsed_article)
        ```
    *   **Refinement for `main.py` or a new `ArticleWorkflowService`**:
        When a new article is processed (e.g., from URL input, file import, Pocket import):
        1.  `article_obj = content_parser.parse_...()`
        2.  `if article_obj and article_obj.potential_thumbnail_source_url:`
            `await self._fetch_and_store_article_thumbnail(article_obj)` (self being `PurseApp` instance)
        3.  `saved_path = fs_manager.save_article(article_obj)` (this will now include `thumbnail_url_local` in YAML if fetched)
        4.  `if saved_path: search_manager.add_or_update_article(article_obj)`

---

### 6. Toga UI Markdown Rendering Security
*   **Intent**: Ensure that when Markdown content is rendered in the Toga UI (specifically in the article reader view), it is done securely, preventing XSS by not executing embedded scripts and by sanitizing or disabling raw HTML.
*   **Upstream Dependencies**: Markdown content from `Article.markdown_content`.
*   **Downstream Dependencies**: Toga UI component responsible for rendering articles (e.g., `src/purse/ui/reader_view.py`).
*   **Changes Needed**:
    *   This is primarily a **UI implementation detail** that needs to be addressed when `reader_view.py` is built.
    *   **Guidance for the UI Developer**:
        *   **Choose a Secure Markdown Renderer**: If Toga's built-in Markdown support (if any, e.g. via a WebView) is used, check its security features. If a Python Markdown library (like `markdown2` or `mistune`) is used to convert Markdown to HTML *before* passing to a Toga WebView:
            *   Configure the Python Markdown library to disable raw HTML or use a strict HTML sanitizer (like `bleach`) on its output.
            *   Example with `markdown2` and `bleach`:
                ```python
                # import markdown2
                # import bleach
                #
                # html_from_markdown = markdown2.markdown(article.markdown_content, extras=["fenced-code-blocks", "nofollow", ...])
                #
                # # Define allowed HTML tags and attributes for safe rendering
                # allowed_tags = ['p', 'strong', 'em', 'ul', 'ol', 'li', 'pre', 'code', 'blockquote', 'h1', 'h2', 'h3', 'a', 'img']
                # allowed_attributes = {'a': ['href', 'title'], 'img': ['src', 'alt', 'title']}
                #
                # safe_html = bleach.clean(html_from_markdown,
                #                          tags=allowed_tags,
                #                          attributes=allowed_attributes,
                #                          strip=True) # strip=True removes disallowed tags completely
                #
                # # Pass safe_html to Toga WebView
                ```
        *   **Toga WebView Security (if used)**:
            *   If rendering HTML in a `toga.WebView`, ensure its sandboxing attributes or Content Security Policy (CSP) mechanisms (if Toga exposes them) are used to prevent script execution and restrict resource loading.
            *   Example (conceptual, Toga API might differ):
                ```python
                # web_view = toga.WebView()
                # # web_view.set_sandbox_flags(...) # If available
                # # web_view.set_csp("script-src 'none'; object-src 'none'; ...") # If available
                # web_view.set_content("file://path_to_article.html", safe_html_content)
                ```
        *   **Avoid `eval()` or equivalent**: Never use functions that evaluate strings as code with content derived from articles.
    *   **No direct code changes to backend services are made in this step**, but the workplan task is to *ensure this guidance is followed during UI development*. This can be a checklist item for UI PRs.

---

## Phase 3: Final Polish and Documentation

### 7. Dependency Updates Review
*   **Intent**: Ensure all project dependencies are up-to-date with their latest secure versions.
*   **File Path**: `purse/pyproject.toml`
*   **Changes Needed**:
    1.  **Review `pyproject.toml`**: Check current version constraints (e.g., `^X.Y.Z`).
    2.  **Run `poetry show --outdated`**: Identify outdated dependencies.
    3.  **Research Updates**: For each outdated dependency, especially parsers (`Trafilatura`, `PyMuPDF`, `python-docx`, `BeautifulSoup4`, `PyYAML`) and network libraries (`httpx`), check their changelogs for security fixes and breaking changes.
    4.  **Update Dependencies**: Use `poetry update <package_name>` or `poetry update` to update to the latest compatible versions.
    5.  **Test Thoroughly**: After updates, run all existing tests (and ideally add more) to ensure no regressions.
    *   **Example (Conceptual - actual versions will vary):**
        If `PyMuPDF` is at `^1.24.1` and `1.24.5` is available with security fixes, update it.
*   **No specific code diff here**, as it depends on the state of dependencies at the time of execution. This is a procedural step.

---

### 8. (Optional but Recommended) `robots.txt` and Rate Limiting
*   **Intent**: Make the application a "better internet citizen" by optionally respecting `robots.txt` and implementing basic rate limiting for HTTP requests. This is more about ethics/politeness than direct app security for the *user*, but can prevent being blocked.
*   **Upstream Dependencies**: `httpx`, `reppy` (Python library for `robots.txt` parsing, would need to be added as a dependency).
*   **Downstream Dependencies**: `HttpClientService`, potentially `ContentParserService`.
*   **Changes Needed**: This is a significant feature addition. For now, consider it a lower priority than the core security fixes unless scraping issues become apparent. If implemented:
    *   **`pyproject.toml`**: Add `reppy` if chosen.
    *   **`HttpClientService`**:
        *   Before making a request to a new domain, fetch and parse its `robots.txt`.
        *   Store parsed `robots.txt` rules (e.g., in an LRU cache keyed by domain).
        *   Check if the target URL is disallowed for `constants.DEFAULT_USER_AGENT`. If so, skip or log.
        *   Implement a simple rate limiter (e.g., `asyncio.Semaphore` per domain, or time delay between requests to the same domain).
*   **Decision**: Defer this detailed implementation. The current focus is on user data security and app stability. This can be a future enhancement.

---

This detailed workplan provides actionable steps to improve the Purse application significantly. Remember to commit changes incrementally after each logical step or file modification.
```