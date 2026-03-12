import os
from datetime import datetime
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

# Importamos tus herramientas
from nova_agent.tools import FileTools, SearchTools, SystemTools

class Brain:
    def __init__(self):
        """Inicializa el motor de IA de Nova."""
        
        api_key = os.getenv("GOOGLE_API_KEY")
        model_name = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite-preview")

        if not api_key:
            raise ValueError("Error crítico: No hay API Key en el entorno.")

        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0
        )
        
        # Registro de herramientas
        self.tools = [
            FileTools.list_files, 
            FileTools.read_file, 
            FileTools.write_file,
            FileTools.delete_file,
            FileTools.explore_project,
            SearchTools.web_search,
            SystemTools.run_command
        ]
        
        # Vinculamos las herramientas al modelo
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.history = []

    def _get_system_prompt(self):
        """Carga la personalidad de Nova y añade contexto temporal."""
        base_path = Path(__file__).parent
        prompt_path = base_path / "prompts" / "system_persona.md"
        
        persona = "Eres Nova, un asistente de IA avanzado integrado localmente."
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                persona = f.read()
        
        user_name = os.getenv("USER_NAME", "Usuario")
        now = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
        return f"{persona}\n\n## CONTEXTO DE SISTEMA\n- Fecha y hora: {now}\n- Usuario: {user_name}"

    def process_query(self, user_input: str):
        """Primer paso: recibe el input, inyecta el sistema si es necesario y decide acción."""
        if not self.history:
            self.history.append(SystemMessage(content=self._get_system_prompt()))
            
        self.history.append(HumanMessage(content=user_input))
        response = self.llm_with_tools.invoke(self.history)
        self.history.append(response)
        return response

    def add_tool_message(self, content, tool_call_id):
        """Agrega el resultado técnico de una herramienta al flujo de conversación."""
        self.history.append(ToolMessage(content=str(content), tool_call_id=tool_call_id))

    def ask_again(self):
        """Genera una nueva respuesta tras haber procesado resultados de herramientas."""
        response = self.llm_with_tools.invoke(self.history)
        self.history.append(response)
        return response

    def clean_content(self, content):
        """Limpia la respuesta del LLM para asegurar que es texto plano legible."""
        if not content: return ""
        if isinstance(content, list):
            return "".join([p.get('text', '') if isinstance(p, dict) else str(p) for p in content])
        return str(content)