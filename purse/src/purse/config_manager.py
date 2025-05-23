import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
import logging # For internal logging of config loading issues

class ConfigManager:
    def __init__(self, base_config_path: Union[str, Path] = 'config.yml'):
        self.logger = logging.getLogger(__name__) # Basic logger for now
        self.base_config_path = Path(base_config_path)
        self.config: Dict[str, Any] = self._load_yaml(self.base_config_path)
        if not self.config:
            self.logger.critical(f"🛑 Base configuration '{self.base_config_path}' not found or empty. Application cannot start.")
            # In a real app, this might be a custom exception or sys.exit
            raise FileNotFoundError(f"Base configuration '{self.base_config_path}' not found or was empty.")

        self.settings: Dict[str, Any] = {} # To be loaded later by load_settings()
        self.settings_path: Optional[Path] = None

    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data is None: # File is empty
                    self.logger.warning(f"🟡 Configuration file is empty: {file_path}")
                    return {}
                if not isinstance(data, dict): # File content is not a dict
                    self.logger.error(f"🛑 Configuration file content is not a dictionary: {file_path}")
                    # Depending on strictness, could raise error or return empty dict
                    raise ValueError(f"Invalid format in {file_path}: Expected a dictionary.")
                return data
        except FileNotFoundError:
            # This is critical for base_config_path, handled in __init__
            # For settings_path, it's a warning as settings might not exist yet.
            if file_path == self.base_config_path:
                 # This log might be redundant due to check in __init__ but good for clarity
                self.logger.error(f"🛑 Base configuration file not found: {file_path}")
            else:
                self.logger.warning(f"🟡 Settings file not found (this may be normal): {file_path}")
            return {}
        except yaml.YAMLError as e:
            self.logger.error(f"🛑 Error parsing YAML file {file_path}: {e}")
            # Depending on strictness, could raise error or return empty dict
            if file_path == self.base_config_path:
                raise # Critical for base config
            return {}
        except Exception as e: # Catch other potential errors like permission issues
            self.logger.error(f"🛑 An unexpected error occurred while loading YAML file {file_path}: {e}")
            if file_path == self.base_config_path:
                raise # Critical for base config
            return {}


    def get(self, key_path: str, default: Optional[Any] = None) -> Any:
        """
        Get a configuration value.
        Searches settings first, then base config.
        Key_path uses dot notation, e.g., 'logging.log_level'.
        """
        # Try settings first
        value = self._get_value_from_dict(self.settings, key_path)
        if value is not None:
            return value

        # Try base config
        value = self._get_value_from_dict(self.config, key_path)
        if value is not None:
            return value

        return default

    def _get_value_from_dict(self, config_dict: Dict[str, Any], key_path: str) -> Optional[Any]:
        keys = key_path.split('.')
        value = config_dict
        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                # elif isinstance(value, list): # Example: handle list index access if needed, e.g. key[index]
                #     # This part is not in the workplan spec but could be an extension
                #     # For now, only dict navigation
                #     return None 
                else:
                    return None # Current key is not a dict, so cannot go deeper
            return value
        except (KeyError, TypeError): # KeyError for dict, TypeError if trying to index non-dict/list
            return None

    def load_settings(self, settings_file_path: Union[str, Path]) -> None:
        """Loads user-specific settings from settings.yml."""
        self.settings_path = Path(settings_file_path)
        self.settings = self._load_yaml(self.settings_path) # _load_yaml handles FileNotFoundError by returning {}
        if not self.settings:
            self.logger.info(f"🟢 User settings file '{self.settings_path}' not found or empty. Using defaults from base config or get() fallbacks.")
        else:
            self.logger.info(f"🟢 User settings loaded from '{self.settings_path}'.")

    def save_settings(self) -> None:
        """Saves current settings to settings.yml."""
        if not self.settings_path:
            self.logger.warning("🟡 Cannot save settings, path not set. Call load_settings first (even with a non-existent path to define it).")
            return

        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.settings, f, sort_keys=False, indent=2, allow_unicode=True)
            self.logger.info(f"🟢 Settings saved to '{self.settings_path}'.")
        except Exception as e:
            self.logger.error(f"🛑 Failed to save settings to '{self.settings_path}': {e}")

    def update_setting(self, key_path: str, value: Any) -> None:
        """Updates a setting in the self.settings dictionary and optionally saves."""
        keys = key_path.split('.')
        current_level = self.settings # Target self.settings for updates

        for i, key in enumerate(keys[:-1]):
            # If a key in the path doesn't exist or is not a dict, create/overwrite it as a dict
            if key not in current_level or not isinstance(current_level.get(key), dict):
                current_level[key] = {}
            current_level = current_level[key]
        
        # Set the final key's value
        current_level[keys[-1]] = value
        self.logger.debug(f"Updated setting '{key_path}' to '{value}' in memory.")
        # The workplan mentions: "Consider if auto-save is desired or should be explicit call"
        # For now, it's an explicit call to save_settings().
        # If auto-save is desired:
        # self.save_settings()

# The workplan notes:
# "The actual instantiation and loading of settings.yml will be handled in main.py or the Toga app setup,
# as the path to settings.yml depends on the synced cloud folder."
# "config_manager = ConfigManager()" is an example, not to be run here directly at module level usually.
# It's better if the main app creates the instance.
