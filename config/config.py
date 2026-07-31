import re
from dotenv import load_dotenv
from config.secret_loader import get_secret_with_aliases, get_service_account_source

# Load environment variables
load_dotenv()

class Config:
    @staticmethod
    def get_env_var(var_name: str, *aliases: str) -> str:
        value = get_secret_with_aliases(var_name, *aliases)
        if not value:
            raise ValueError(f"Missing environment variable: {var_name}")
        return value

    @staticmethod
    def get_google_drive_folder_id() -> str:
        url = Config.get_env_var("GOOGLE_DRIVE_FOLDER_URL")
        # Extract ID from a URL like https://drive.google.com/drive/folders/XXXYYY
        match = re.search(r"folders/([a-zA-Z0-9_-]+)", url)
        if match:
            return match.group(1)
        # Direct ID in URL fallback if format differs
        if "id=" in url:
            match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
            if match:
                return match.group(1)
        # Assume it's an ID if no match and it's not a url
        if not url.startswith("http"):
            return url
        raise ValueError("Could not extract Google Drive Folder ID from URL.")

    @classmethod
    def load(cls):
        return {
            "email_address": cls.get_env_var("SMTP_USERNAME"),
            "email_password": cls.get_env_var("SMTP_PASSWORD"),
            "smtp_from_email": get_secret_with_aliases("SMTP_FROM_EMAIL", default=""),
            "smtp_from_name": get_secret_with_aliases("SMTP_FROM_NAME", default="AI Attendance"),
            "groq_api_key": cls.get_env_var("GROQ_API_KEY", "GORQ_API_KEY"),
            "groq_model": cls.get_env_var("GROQ_MODEL"),
            "google_drive_folder_id": cls.get_google_drive_folder_id(),
            "service_account_source": get_service_account_source(),
        }
