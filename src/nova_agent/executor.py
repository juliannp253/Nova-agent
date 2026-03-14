from rich.prompt import Confirm
from rich import print
from nova_agent.tools import FileTools, SearchTools, SystemTools


class ToolExecutor:
    """Mapea y ejecuta las herramientas solicitadas por la IA."""
    
    TOOL_MAP = {
        "list_files": FileTools.list_files,
        "read_file": FileTools.read_file,
        "write_file": FileTools.write_file,
        "delete_file": FileTools.delete_file,
        "web_search": SearchTools.web_search,
        "explore_project": FileTools.explore_project,
        "run_command": SystemTools.run_command
    }

    SENSITIVE_TOOLS = ["write_file", "run_command", "delete_file"]
    
    @staticmethod
    def execute_direct(tool_call: dict):
        """
        Ejecuta la herramienta solicitada sin pedir confirmación.
        La seguridad ahora se gestiona en la capa de la Interfaz (UI).
        """
        name = tool_call["name"]
        args = tool_call["args"]

        # Buscamos la función en nuestro mapa
        tool_func = ToolExecutor.TOOL_MAP.get(name)

        if not tool_func:
            return f"Error: La herramienta '{name}' no está registrada en el ejecutor."

        try:
            # Ejecutamos la función con sus argumentos desglosados (**args)
            return tool_func.invoke(args)
        except Exception as e:
            return f"Error al ejecutar {name}: {str(e)}"