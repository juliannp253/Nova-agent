import typer
from rich import print
from rich.panel import Panel
from rich.console import Console
from rich.prompt import Prompt
from nova_agent.config import Config
from nova_agent.brain import Brain
from nova_agent.executor import ToolExecutor
from nova_agent.memory import MemoryManager

console = Console()  # instancia correcta

app = typer.Typer(
    help="Nova",
    no_args_is_help=True
)

@app.command()
def status():
    """Verifica la salud del agente y sus conexiones."""
    print(Panel("[bold cyan]Nova Agent Status[/bold cyan]"))
    
    checks = Config.validate_config()
    
    if checks["google"]:
        print("[green]✓ Google API Key: Detectada[/green]")
    else:
        print("[red]✗ Google API Key: No encontrada[/red] (Necesaria para el cerebro)")

    if checks["serpapi"]:
        print("[green]✓ SerpApi Key: Detectada[/green]")
    else:
        print("[yellow]! SerpApi Key: No encontrada[/yellow] (Opcional para búsquedas web)")

    if all(checks.values()):
        print("\n[bold green]SISTEMA LISTO[/bold green]")
    else:
        print("\n[bold yellow]SISTEMA PARCIAL - Revisa tu archivo .env[/bold yellow]")

@app.command()
def chat(prompt: str):
    """Bucle de agente: Piensa, Actúa, Observa y Responde."""
    if not Config.GOOGLE_API_KEY:
        print("[red]Error: API Key no configurada.[/red]")
        return

    nova = Brain()

    with console.status("[bold blue]Nova está analizando...", spinner="dots"):
        response = nova.get_initial_response(prompt)
        
        if response.tool_calls:
            tool_call = response.tool_calls[0]
            print(f"[yellow]➔ Ejecutando herramienta:[/yellow] [bold]{tool_call['name']}[/bold]")
            
            result = ToolExecutor.execute(tool_call)
            
            response = nova.get_final_response(result, tool_call["id"])

    final_text = nova.clean_content(response.content)
    print(Panel(final_text, title="[bold cyan]Nova[/bold cyan]", border_style="cyan"))

@app.command()
def list_models():
    """Lista los modelos que Google te permite usar con tu API Key."""
    import google.generativeai as genai
    from nova_agent.config import Config
    
    if not Config.GOOGLE_API_KEY:
        print("[red]Error: No hay API Key en el .env[/red]")
        return

    genai.configure(api_key=Config.GOOGLE_API_KEY)
    print("[yellow]Modelos disponibles para generar contenido:[/yellow]")
    
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- [cyan]{m.name}[/cyan]")
    except Exception as e:
        print(f"[red]Error al listar modelos: {e}[/red]")

@app.command()
def interactive():
    """Inicia una sesión de chat persistente con Nova."""
    # Verificamos configuración antes de mover un solo dedo
    if not Config.GOOGLE_API_KEY:
        print("[red]Error: API Key no encontrada en el archivo .env[/red]")
        return

    # Inicializamos componentes
    memory = MemoryManager()
    nova = Brain()
    
    # Cargamos historial previo 
    saved_history = memory.load()
    if saved_history:
        nova.history = saved_history
        print("[dim]Historial recuperado correctamente.[/dim]")
    else:
        # Si no hay historial, inyectamos el System Prompt inicial
        from langchain_core.messages import SystemMessage
        nova.history = [SystemMessage(content=nova._get_system_prompt())]

    print(Panel("[bold cyan]NOVA: MODO INTERACTIVO INICIADO[/bold cyan]\n[dim]Escribe 'salir' para terminar la sesión.[/dim]", border_style="cyan"))

    while True:
        user_input = Prompt.ask("\n[bold green]Julian[/bold green]")
        
        if user_input.lower() in ["salir", "exit", "quit"]:
            memory.save(nova.history)
            break

        # FLAG para controlar el bucle de herramientas
        response = None
        
        # 1. EL CEREBRO PIENSA (Aquí sí usamos el spinner)
        with console.status("[bold blue]Nova pensando...", spinner="dots"):
            response = nova.process_query(user_input)
        
        # 2. BUCLE DE HERRAMIENTAS (Fuera del console.status)
        max_iterations = 5
        while response.tool_calls and max_iterations > 0:
            max_iterations -= 1
            
            for tool_call in response.tool_calls:
                console.print(f"  [yellow]➔ Nova requiere:[/yellow] [bold]{tool_call['name']}[/bold]")
                result = ToolExecutor.execute(tool_call)
                nova.add_tool_message(result, tool_call["id"])
            
            # Volvemos a activar el spinner SOLO para que la IA procese el resultado
            with console.status("[bold blue]Nova analizando resultados...", spinner="dots"):
                response = nova.ask_again()
        
        # 3. RESPUESTA FINAL
        final_text = nova.clean_content(response.content)
        print(Panel(final_text, title="[bold cyan]Nova[/bold cyan]", border_style="cyan"))
        memory.save(nova.history)

if __name__ == "__main__":
    app()