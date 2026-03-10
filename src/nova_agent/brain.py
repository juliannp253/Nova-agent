from datetime import datetime
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from nova_agent.config import Config
from nova_agent.tools import FileTools, SearchTools, SystemTools

class Brain:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite-preview", 
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=0
        )
        self.tools = [
            FileTools.list_files, 
            FileTools.read_file, 
            FileTools.write_file,
            FileTools.delete_file,
            FileTools.explore_project,
            SearchTools.web_search,
            SystemTools.run_command
        ]
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.history = []

    def _get_system_prompt(self):
        base_path = Path(__file__).parent
        prompt_path = base_path / "prompts" / "system_persona.md"
        persona = "Eres Nova, un asistente de IA."
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                persona = f.read()
        
        now = datetime.now().strftime("%A, %d de %B de %Y")
        return f"{persona}\n\n## TIEMPO REAL\n- Fecha actual: {now}"

    def process_query(self, user_input: str):
        """Primer paso: recibe el input y decide qué hacer."""
        self.history.append(HumanMessage(content=user_input))
        response = self.llm_with_tools.invoke(self.history)
        self.history.append(response) # Guardamos la respuesta (o tool_call)
        return response

    def add_tool_message(self, content, tool_call_id):
        """NUEVO: Agrega el resultado de la herramienta al historial."""
        self.history.append(ToolMessage(content=str(content), tool_call_id=tool_call_id))

    def ask_again(self):
        """NUEVO: Vuelve a consultar al modelo tras procesar herramientas."""
        response = self.llm_with_tools.invoke(self.history)
        self.history.append(response)
        return response

    def clean_content(self, content):
        if not content: return ""
        if isinstance(content, list):
            return "".join([p.get('text', '') if isinstance(p, dict) else str(p) for p in content])
        return str(content)