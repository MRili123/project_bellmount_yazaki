"""
Encryption utilities for securing API URL and API key in desktop app
"""

from cryptography.fernet import Fernet
import json
import os
from pathlib import Path

class AppSecurityManager:
    """Manage encrypted configuration for desktop app"""

    # This key should be unique per installation
    # In production, derive it from system info or store it securely
    KEY_FILE = Path(__file__).parent / ".app_key"
    CONFIG_FILE = Path(__file__).parent / "config.json"

    @staticmethod
    def _get_or_create_key() -> bytes:
        """Get or create encryption key"""
        if AppSecurityManager.KEY_FILE.exists():
            return AppSecurityManager.KEY_FILE.read_bytes()

        # Generate new key
        key = Fernet.generate_key()
        AppSecurityManager.KEY_FILE.write_bytes(key)
        # Restrict permissions on Windows
        if os.name == 'nt':
            os.chmod(str(AppSecurityManager.KEY_FILE), 0o600)
        return key

    @staticmethod
    def encrypt_value(value: str) -> str:
        """Encrypt a value"""
        key = AppSecurityManager._get_or_create_key()
        cipher = Fernet(key)
        encrypted = cipher.encrypt(value.encode())
        return encrypted.decode()

    @staticmethod
    def decrypt_value(encrypted_value: str) -> str:
        """Decrypt a value"""
        key = AppSecurityManager._get_or_create_key()
        cipher = Fernet(key)
        try:
            decrypted = cipher.decrypt(encrypted_value.encode())
            return decrypted.decode()
        except Exception as e:
            print(f"⚠ Failed to decrypt: {str(e)}")
            return ""

    @staticmethod
    def save_config(api_url: str, api_key: str):
        """Save encrypted API configuration"""
        config = {
            "api_url_encrypted": AppSecurityManager.encrypt_value(api_url),
            "api_key_encrypted": AppSecurityManager.encrypt_value(api_key),
            "version": "1.0"
        }
        AppSecurityManager.CONFIG_FILE.write_text(json.dumps(config, indent=2))
        print(f"✓ Config saved: {AppSecurityManager.CONFIG_FILE}")

    @staticmethod
    def load_config() -> dict:
        """Load and decrypt API configuration"""
        if not AppSecurityManager.CONFIG_FILE.exists():
            return None

        try:
            config = json.loads(AppSecurityManager.CONFIG_FILE.read_text())
            return {
                "api_url": AppSecurityManager.decrypt_value(config.get("api_url_encrypted", "")),
                "api_key": AppSecurityManager.decrypt_value(config.get("api_key_encrypted", ""))
            }
        except Exception as e:
            print(f"⚠ Failed to load config: {str(e)}")
            return None

    @staticmethod
    def clear_config():
        """Clear saved configuration"""
        if AppSecurityManager.CONFIG_FILE.exists():
            AppSecurityManager.CONFIG_FILE.unlink()
            print("✓ Config cleared")


# Example usage in app.py:
"""
from crypto_utils import AppSecurityManager

# During setup, save encrypted credentials:
AppSecurityManager.save_config(
    api_url="https://your-api.azurewebsites.net",
    api_key="sk_live_abc123xyz789..."
)

# During app startup, load encrypted credentials:
config = AppSecurityManager.load_config()
if config:
    api_url = config["api_url"]
    api_key = config["api_key"]
else:
    # Prompt for setup
    setup_window = SetupWindow()
    ...
"""
