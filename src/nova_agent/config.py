import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Manage the agent's settings and secrets."""
    
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

    @classmethod
    def validate_config(cls):
        """Check which keys are present."""
        status = {
            "google": bool(cls.GOOGLE_API_KEY),
            "serpapi": bool(cls.SERPAPI_API_KEY)
        }
        return status