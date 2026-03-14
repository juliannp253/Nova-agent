import json
from pathlib import Path


class SettingsManager:
    """Gestiona la configuración persistente del usuario en ~/.nova/config.json"""

    CONFIG_DIR = Path.home() / ".nova" # /home/user/.nova
    CONFIG_FILE = CONFIG_DIR / "config.json" # /home/user/.nova/config.json

    @classmethod
    def get_keys(cls) -> str:
        """Lee todas las llaves del archivo de configuración local."""
        defaults = {
            "GOOGLE_API_KEY": "", 
            "SERPAPI_API_KEY": "",
            "MODEL_NAME": "gemini-3.1-flash-lite-preview",
            "USER_NAME": "Usuario"
            }
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, "r") as f:
                    return {**defaults, **json.load(f)} # Sobreescribir defaults con json.load file (si hay claves repetidas)
            except Exception:
                return defaults
        return defaults

    # cls permite la llamada de atributos u otros métodos de la clase ~= this en Java
    @classmethod
    def save_keys(cls, google_key: str, serp_key: str, model: str, name: str) -> None:
        """Persiste ambas llaves en el JSON local."""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True) # Crea directorio para guardar y evita lanzar error si ya existe
        data = {
            "GOOGLE_API_KEY": google_key,
            "SERPAPI_API_KEY": serp_key,
            "MODEL_NAME": model,
            "USER_NAME": name
        }
        with open(cls.CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)