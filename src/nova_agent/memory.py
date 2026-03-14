import json
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

class MemoryManager:
    def __init__(self, file_name="history.json", max_messages=10):
        self.path = Path(__file__).parent / "prompts" / file_name
        self.max_messages = max_messages

    def save(self, messages):
        # Guardamos los últimos N mensajes para evitar el crecimiento infinito
        to_save = messages[-self.max_messages:]
        serializable = []
        for msg in to_save:
            # Convertimos objetos de LangChain a diccionarios simples
            m_type = "human" if isinstance(msg, HumanMessage) else "ai" if isinstance(msg, AIMessage) else "system" if isinstance(msg, SystemMessage) else "tool"
            serializable.append({"type": m_type, "content": msg.content})
        
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)

    def load(self):
        if not self.path.exists(): return []
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
            history = []
            for m in data:
                if m["type"] == "human": history.append(HumanMessage(content=m["content"]))
                elif m["type"] == "ai": history.append(AIMessage(content=m["content"]))
                elif m["type"] == "system": history.append(SystemMessage(content=m["content"]))
            return history