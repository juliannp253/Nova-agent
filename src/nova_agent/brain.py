import os
from datetime import datetime
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from nova_agent.tools import FileTools, SearchTools, SystemTools


class ModelNotAvailableError(Exception):
    """Se lanza cuando el modelo no existe o el usuario no tiene acceso."""
    pass


class Brain:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite-preview")

        if not api_key:
            raise ValueError("Error crítico: No hay API Key en el entorno.")

        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0
        )

        self.tools = [
            FileTools.list_files,
            FileTools.read_file,
            FileTools.write_file,
            FileTools.delete_file,
            FileTools.explore_project,
            SearchTools.web_search,
            SystemTools.run_command,
        ]

        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.history = []

    def _get_system_prompt(self):
        base_path = Path(__file__).parent
        prompt_path = base_path / "prompts" / "system_persona.md"

        persona = "Eres Nova, un asistente de IA avanzado integrado localmente."
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                persona = f.read()

        user_name = os.getenv("USER_NAME", "Usuario")
        now = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
        return f"{persona}\n\n## CONTEXTO DE SISTEMA\n- Fecha y hora: {now}\n- Usuario: {user_name}"

    def _handle_llm_error(self, e: Exception) -> None:
        """Clasifica el error y lanza una excepción apropiada."""
        msg = str(e).lower()
        is_model_error = any(keyword in msg for keyword in [
            "not found", "404", "permission", "403",
            "invalid model", "model not", "does not exist",
            "not supported", "quota", "resource_exhausted",
            "invalid argument", "not available",
        ])
        if is_model_error:
            raise ModelNotAvailableError(
                f"El modelo '[bold]{self.model_name}[/bold]' no está disponible o no tienes acceso.\n"
                f"Abre Configuración [bold](Ctrl+S)[/bold] y selecciona otro modelo."
            ) from e
        raise e

    def process_query(self, user_input: str):
        if not self.history:
            self.history.append(SystemMessage(content=self._get_system_prompt()))

        self.history.append(HumanMessage(content=user_input))
        try:
            response = self.llm_with_tools.invoke(self.history)
        except Exception as e:
            self._handle_llm_error(e)

        self.history.append(response)
        return response

    def add_tool_message(self, content, tool_call_id):
        self.history.append(ToolMessage(content=str(content), tool_call_id=tool_call_id))

    def ask_again(self):
        try:
            response = self.llm_with_tools.invoke(self.history)
        except Exception as e:
            self._handle_llm_error(e)

        self.history.append(response)
        return response

    def clean_content(self, content):
        if not content:
            return ""
        if isinstance(content, list):
            return "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in content])
        return str(content)