import os
import subprocess
from langchain_core.tools import tool
from langchain_community.utilities import SerpAPIWrapper # Nueva importación
from nova_agent.config import Config

class SearchTools:
    """Herramientas de búsqueda en internet."""

    @tool
    def web_search(query: str):
        """
        SOLO para investigar documentación externa, errores desconocidos o información 
        que NO existe en el sistema local. NUNCA usar para obtener datos del sistema 
        del usuario (versiones instaladas, procesos, archivos, red). Para eso existe run_command.
        """
        search = SerpAPIWrapper()
        try:
            return search.run(query)
        except Exception as e:
            return f"Error en la búsqueda web: Verifique su SERPAPI_API_KEY. Detalle:"

class FileTools:
    """Colección de herramientas para que Nova manipule archivos."""

    @tool
    def list_files(directory: str = "."):
        """Lista todos los archivos y carpetas en un directorio específico."""
        try:
            items = os.listdir(directory)
            if not items:
                return f"El directorio '{directory}' está vacío."
            
            # Formateamos la salida para que sea explícita
            output = [f"Contenido del directorio '{directory}':"]
            for item in items:
                path = os.path.join(directory, item)
                tipo = "[DIR]" if os.path.isdir(path) else "[FILE]"
                output.append(f"- {tipo} {item}")
            
            return "\n".join(output)
        except Exception as e:
            return f"Error al leer el directorio '{directory}': {str(e)}"

    @tool
    def read_file(file_path: str):
        """Lee el contenido de un archivo de texto."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return f"Contenido de '{file_path}':\n\n{content}"
        except Exception as e:
            return f"No pude leer el archivo '{file_path}': {str(e)}"
        
    @tool
    def write_file(file_path: str, content: str):
        """Crea un archivo o sobrescribe uno existente. Crea carpetas automáticamente si no existen."""
        try:
            normalized_path = os.path.normpath(file_path)
            directory = os.path.dirname(normalized_path)
            
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            with open(normalized_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Éxito: Archivo '{normalized_path}' creado."
        except Exception as e:
            return f"Error al escribir {file_path}: {str(e)}"
        
    @tool
    def delete_file(file_path: str):
        """Elimina un archivo específico del sistema de forma permanente."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return f"Éxito: El archivo '{file_path}' ha sido eliminado."
            else:
                return f"Error: El archivo '{file_path}' no existe en la ruta especificada."
        except Exception as e:
            return f"Error técnico al intentar eliminar el archivo: {str(e)}"
        
    @tool
    def explore_project(directory: str = "."):
        """
        Escanea un proyecto completo de forma recursiva mostrando su estructura en árbol.
        Úsala cuando el usuario pida analizar, entender o explorar un proyecto entero.
        Ignora automáticamente carpetas de dependencias como node_modules, .git, __pycache__, etc.
        """
        IGNORED = {
            "node_modules", ".git", "__pycache__", ".venv", "venv", 
            "env", "dist", "build", ".next", ".cache", "target",
            "*.class", ".gradle", ".idea", ".vscode"
        }
        
        MAX_FILES = 200  # Límite para proyectos enormes
        file_count = 0
        output = []

        def walk(path: str, prefix: str = ""):
            nonlocal file_count
            if file_count >= MAX_FILES:
                output.append(f"{prefix}... (límite de {MAX_FILES} archivos alcanzado)")
                return
            try:
                entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name))
                for i, entry in enumerate(entries):
                    if entry.name in IGNORED or entry.name.startswith("."):
                        continue
                    connector = "└── " if i == len(entries) - 1 else "├── "
                    output.append(f"{prefix}{connector}{entry.name}")
                    file_count += 1
                    if entry.is_dir():
                        extension = "    " if i == len(entries) - 1 else "│   "
                        walk(entry.path, prefix + extension)
            except PermissionError:
                output.append(f"{prefix}[PERMISO DENEGADO]")

        output.append(f"Estructura del proyecto: {directory}\n")
        walk(directory)
        output.append(f"\nTotal de elementos escaneados: {file_count}")
        return "\n".join(output)

class SystemTools:
    @tool
    def run_command(command: str):
        """
        Ejecuta UN SOLO comando en PowerShell de Windows. 
        REGLAS CRÍTICAS:
        - Ejecuta solo UN comando por llamada. Si necesitas dos datos, llama esta tool DOS VECES.
        - Sintaxis PowerShell SIEMPRE. Nunca bash/linux (no uses &&, |, head, ps aux).
        - Para versión de Java: 'java -version'
        - Para procesos por RAM: 'Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 3 Name, @{N="RAM_MB";E={[math]::Round($_.WorkingSet64/1MB,1)}}'
        - Si el comando falla, NO reintentes más de 1 vez con una variante. Informa el error al usuario.
        """
        try:
            result = subprocess.run(
                ["powershell", "-Command", command],
                capture_output=True, text=True, timeout=15
            )
            output = result.stdout.strip()
            error = result.stderr.strip()

            if result.returncode != 0 or (not output and error):
                return f"COMANDO FALLIDO (código {result.returncode}): {error or 'Sin salida'}. No reintentar automáticamente."
            
            if not output:
                return "COMANDO EJECUTADO: Sin salida visible."
                
            return f"Salida:\n{output}"
        except subprocess.TimeoutExpired:
            return "TIMEOUT: El comando tardó más de 15 segundos. No reintentar."
        except Exception as e:
            return f"ERROR TÉCNICO: {str(e)}. No reintentar."