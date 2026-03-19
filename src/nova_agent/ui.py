import asyncio
import os
import psutil
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Button, Label, Static
from textual import work
from textual.screen import ModalScreen
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Select
from rich.panel import Panel


from nova_agent.brain import Brain
from nova_agent.executor import ToolExecutor
from nova_agent.memory import MemoryManager
from nova_agent.settings import SettingsManager

# ── Modal: Setup inicial ───────────────────────────────────────────────────

class SetupModal(ModalScreen[str]):
    """Pantalla de primera ejecución para configurar la API Key."""

    FALLBACK_MODELS = [
        ("gemini-3.1-flash-lite (recomendado)", "gemini-3.1-flash-lite-preview"),
        ("gemini-2.0-flash", "gemini-2.0-flash"),
        ("gemini-1.5-flash", "gemini-1.5-flash"),
        ("gemini-1.5-pro", "gemini-1.5-pro"),
        ("gemini-2.5-flash-preview", "gemini-2.5-flash-preview-04-17"),
    ]

    def compose(self) -> ComposeResult:
        keys = SettingsManager.get_keys()
 
        with Grid(id="setup_grid"):
            yield Label("[ NOVA — GESTIÓN DE LLAVES API ]", id="setup_title")
 
            yield Label("Google AI Studio Key:", classes="metric-key")
            yield Input(
                value=keys["GOOGLE_API_KEY"],
                placeholder="AIza...",
                id="google_input",
                password=True,
            )
 
            yield Label("SerpApi Key (Buscador):", classes="metric-key")
            yield Input(
                value=keys["SERPAPI_API_KEY"],
                placeholder="SERPAPI KEY (optional)",
                id="serp_input",
                password=True,
            )
 
            yield Label("Modelo Gemini:", classes="metric-key")
            current_model = keys.get("MODEL_NAME", "gemini-3.1-flash-lite-preview")

            fallback_values = [v for _, v in self.FALLBACK_MODELS]
            safe_value = current_model if current_model in fallback_values else "gemini-2.0-flash"
            yield Select(
                options=self.FALLBACK_MODELS,
                value=safe_value,
                id="model_select",
            )

            yield Static(
                "[dim]Ingresa tu Google Key y presiona Tab para cargar modelos disponibles[/dim]",
                id="model_hint",
            )
 
            yield Label("Tu Nombre / Nickname:", classes="metric-key")
            yield Input(
                value=keys.get("USER_NAME", ""),
                placeholder="¿Cómo quieres que te llame?",
                id="name_input",
            )
 
            yield Button(label="ACTIVAR SISTEMA", variant="success", id="save_btn")
 
    def on_input_changed(self, event: Input.Changed) -> None:
        """Cuando el usuario termina de escribir la Google Key, intenta cargar modelos reales."""
        if event.input.id != "google_input":
            return
        key = event.value.strip()
        if key.startswith("AIza") and len(key) > 20:
            self._load_models(key)
 
    @work(thread=True)
    def _load_models(self, api_key: str) -> None:
        """Carga modelos desde la API de Google en un hilo separado."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            raw = genai.list_models()
            models = [
                m.name.replace("models/", "")
                for m in raw
                if "generateContent" in m.supported_generation_methods
                and "gemini" in m.name
            ]
            # Ordenar: primero los que no son preview/experimental
            stable = sorted([m for m in models if "preview" not in m and "exp" not in m])
            preview = sorted([m for m in models if "preview" in m or "exp" in m])
            ordered = stable + preview
 
            if ordered:
                options = [(m, m) for m in ordered]
                # Actualizar el Select en el hilo principal
                self.app.call_from_thread(self._update_model_select, options)
        except Exception:
            # Si falla, los modelos fallback siguen ahí, no pasa nada
            pass
 
    def _update_model_select(self, options: list) -> None:
        """Actualiza el widget Select con los modelos obtenidos."""
        select = self.query_one("#model_select", Select)
        current = select.value
        select.set_options(options)
        # Mantener selección actual si sigue disponible
        if any(v == current for _, v in options):
            select.value = current
        self.query_one("#model_hint").update(
            f"[#00d4aa]✓ {len(options)} modelos cargados[/#00d4aa]"
        )
 
    def on_button_pressed(self, event: Button.Pressed) -> None:
        google_key = self.query_one("#google_input").value.strip()
        serpapi_key = self.query_one("#serp_input").value.strip()
        model = str(self.query_one("#model_select", Select).value)
        name = self.query_one("#name_input").value.strip() or "Usuario"

        if not google_key.startswith("AIza"):
            self.notify("La llave de Google es obligatoria y debe comenzar con 'AIza'", severity="error")
            return

        SettingsManager.save_keys(google_key, serpapi_key, model, name)

        os.environ["GOOGLE_API_KEY"] = google_key
        os.environ["SERPAPI_API_KEY"] = serpapi_key
        os.environ["MODEL_NAME"] = model
        os.environ["USER_NAME"] = name

        self.notify("Configuración guardada")
        self.dismiss({"google": google_key, "serp": serpapi_key, "model": model, "name": name})
# ── Modal: Autorización de seguridad ───────────────────────────────────────────────────

class SecurityModal(ModalScreen[bool]):
    """Modal de confirmación para acciones sensibles."""

    # Constructor inicial para recibir los datos externos
    def __init__(self, tool_name: str, args: dict):
        super().__init__()
        self.tool_name = tool_name
        self.args = args

    def compose(self) -> ComposeResult:
        with Grid(id="modal_grid"):
            yield Label("[ AUTORIZACIÓN REQUERIDA ]", id="modal_title")
            yield Static(
                f"[cyan]COMANDO:[/cyan] [bold white]{self.tool_name}[/bold white]\n\n"
                f"[cyan]ARGS:[/cyan]    [white]{self.args}[/white]",
                id="modal_body",
            )
            yield Button("PERMITIR", variant="success", id="allow")
            yield Button("DENEGAR", variant="error", id="deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Cierra modal y retorna el valor booleano
        self.dismiss(event.button.id == "allow") # event.button.id obtiene el id del boton presionado y hace la comparación


# ── App principal ──────────────────────────────────────────────────────────

class NovaTUI(App): # App es la clase principal (main) de Textual
    """Nova Agent — Terminal UI."""

    TITLE = "NOVA"

    CSS = """
    /* ── Base ─────────────────────────────────────────────── */
    Screen {
        background: #0a0a0a;
    }

    Header {
        background: #0a0a0a;
        color: #00d4aa;
        text-style: bold;
        border-bottom: solid #1a1a1a;
        height: 1;
    }

    Footer {
        background: #0a0a0a;
        color: #333333;
        border-top: solid #1a1a1a;
        height: 1;
    }

    /* ── Layout principal ─────────────────────────────────── */
    #main_layout {
        height: 1fr;
    }

    #chat_section {
        width: 3fr;
        height: 1fr;
    }

    /* ── Chat log ─────────────────────────────────────────── */
    #chat_log {
        background: #0a0a0a;
        color: #cccccc;
        border: solid #1e1e1e;
        margin: 1 1 0 1;
        padding: 0 1;
        height: 1fr;
    }

    /* ── Input ────────────────────────────────────────────── */
    #user_input {
        background: #0a0a0a;
        color: #ffffff;
        border: solid #2a2a2a;
        border-top: solid #00d4aa;
        margin: 0 1 1 1;
        padding: 0 1;
    }

    #user_input:focus {
        border: solid #2a2a2a;
        border-top: solid #00ffcc;
    }

    /* ── Sidebar ──────────────────────────────────────────── */
    #sidebar {
        width: 22;
        height: 1fr;
        border-left: solid #1a1a1a;
        background: #080808;
        padding: 1;
    }

    #sidebar_header {
        color: #00d4aa;
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
    }

    #sidebar_divider {
        color: #1e1e1e;
        margin: 0;
    }

    .metric-key {
        color: #444444;
        text-style: bold;
        margin-top: 1;
    }

    .metric-val {
        color: #00d4aa;
        margin-bottom: 0;
        padding-left: 1;
    }

    #status_val {
        color: #00d4aa;
        padding-left: 1;
    }

    #last_tool_val {
        color: #888888;
        padding-left: 1;
    }

    #iter_val {
        color: #888888;
        padding-left: 1;
    }

    #session_val {
        color: #444444;
        padding-left: 1;
    }

    /* ── Modal: Autorización ─────────────────────────── */
    #modal_grid {
        grid-size: 2;
        grid-gutter: 1;
        grid-rows: 2 7 3; 
        padding: 1 2;
        background: #0d0d0d;
        border: solid #00d4aa;
        width: 60;
        height: 18;
        align: center middle;
    }

    #modal_title {
        column-span: 2;
        text-align: center;
        color: #ff4444;
        text-style: bold;
        height: 1;
        margin-top: 1;
    }

    #modal_body {
        column-span: 2;
        color: #aaaaaa;
        border-top: solid #1e1e1e;
        border-bottom: solid #1e1e1e;
        padding: 1;
        /* Permitimos scroll si los argumentos son muy largos */
        overflow: auto;
    }

    #allow {
        width: 100%;
        background: #003322;
        color: #00d4aa;
        border: solid #00d4aa;
        text-style: bold;
        height: 3;
    }

    #deny {
        width: 100%;
        background: #220000;
        color: #ff4444;
        border: solid #ff4444;
        text-style: bold;
        height: 3;
    }

    #deny:hover {
        background: #330000;
    }

    /* ── Modal: Setup ─────────────────────────── */
    #setup_grid {
        grid-size: 1;
        grid-rows: 2 1 3 1 3 1 3 1 3 3; 
        grid-gutter: 0;
        padding: 1 3;
        background: #0d0d0d;
        border: solid #00d4aa;
        width: 65;
        height: auto;
        align: center middle;
    }

    .setup-label {
        color: #00d4aa;
        text-style: bold;
        margin-top: 1;
        width: 100%;
    }

    #setup_title {
        color: #00d4aa;
        text-align: center;
        text-style: bold italic;
        background: #1a1a1a;
        width: 100%;
        margin-bottom: 1;
    }

    #google_input, #serp_input, #model_input, #name_input {
        background: #111111;
        color: #ffffff;
        border: solid #2a2a2a;
        height: 3;
    }

    #save_btn {
        width: 100%;
        background: #00d4aa;
        color: #000000; /* Texto negro sobre fondo cyan para máximo contraste */
        text-style: bold;
        margin-top: 1;
        border: none;
    }

    #save_btn:hover {
        background: #00ffcc;
    }
    """

    # Cuando el usuario presiona Ctrl+K, Textual llama 
    # automáticamente al método cuyo nombre sea action_ + el segundo elemento de la tupla.
    BINDINGS = [("ctrl+k", "manage_keys", "Keys")] 

    # Función que responde al comando 'CTRL+k'
    @work # Hilo separado para no bloquear la UI
    async def action_manage_keys(self) -> None: # async def = esperar sin congelar todo
        """Acción disparada por Ctrl+K."""
        # Abre SetupModal y pausa la ejecución hasta que el Modal se cierre
        # result = el diccionario de keys
        result = await self.push_screen_wait(SetupModal()) 
        
        if result:
            SettingsManager.save_keys(result["google"], result["serp"], result["model"], result["name"])
            os.environ["GOOGLE_API_KEY"] = result["google"]
            os.environ["SERPAPI_API_KEY"] = result["serp"]
            os.environ["MODEL_NAME"] = result["model"]
            os.environ["USER_NAME"] = result["name"]
            
            self.notify("Configuración actualizada. Reiniciando motor...")
            # Reemplaza la instancia actual del agente con una nueva, usando las nuevas keys
            self.nova = Brain()
    
    
    # Renderizado de panel lateral con estadísticas
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main_layout"):
            with Vertical(id="chat_section"):
                yield RichLog(highlight=True, markup=True, id="chat_log")
                yield Input(placeholder="  > ", id="user_input")
            with Vertical(id="sidebar"):
                yield Label("NOVA  SYS", id="sidebar_header")
                yield Static("─" * 18, id="sidebar_divider")
                yield Label("CPU", classes="metric-key")
                yield Label("─", id="cpu_val", classes="metric-val")
                yield Label("RAM", classes="metric-key")
                yield Label("─", id="ram_val", classes="metric-val")
                yield Label("UPTIME", classes="metric-key")
                yield Label("─", id="uptime_val", classes="metric-val")
                yield Static("─" * 18, classes="metric-key")
                yield Label("STATUS", classes="metric-key")
                yield Label("IDLE", id="status_val")
                yield Label("LAST TOOL", classes="metric-key")
                yield Label("─", id="last_tool_val")
                yield Label("ITERACIÓN", classes="metric-key")
                yield Label("─", id="iter_val")
                yield Static("─" * 18, classes="metric-key")
                yield Label("SESSION", classes="metric-key")
                yield Label("─", id="session_val")
        yield Footer()

    # ── Montaje ────────────────────────────────────────────────────────────

    # Método que Textual llama automaticamente al terminar de renderizar y cargar la UI
    async def on_mount(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._nova_start_time = datetime.now()
        self._max_iter = 15
        self.chat_log = self.query_one("#chat_log", RichLog)
        self.set_interval(2.0, self._tick_stats)
        self._initialize()

    @work(exclusive=True)
    async def _initialize(self) -> None:
        """Inicialización completa en worker."""
        keys = SettingsManager.get_keys()

        if not keys["GOOGLE_API_KEY"]:
            keys_data = await self.push_screen_wait(SetupModal())
            SettingsManager.save_keys(keys_data["google"], keys_data["serp"], keys_data["model"], keys_data["name"])
            keys = SettingsManager.get_keys()

        os.environ["USER_NAME"] = keys["USER_NAME"]
        os.environ["GOOGLE_API_KEY"] = keys["GOOGLE_API_KEY"]
        os.environ["SERPAPI_API_KEY"] = keys["SERPAPI_API_KEY"]
        os.environ["MODEL_NAME"] = keys["MODEL_NAME"]

        self.nova = Brain()
        self.memory = MemoryManager()

        history = self.memory.load()
        if history:
            self.nova.history = history
            self.chat_log.write("[dim]// memoria recuperada[/dim]")
        else:
            from langchain_core.messages import SystemMessage
            self.nova.history = [SystemMessage(content=self.nova._get_system_prompt())]

        self._print_banner()

    def _print_banner(self) -> None:
        self.chat_log.write("")
        self.chat_log.write(
            "[bold #00d4aa]"
            "  ███╗   ██╗ ██████╗ ██╗   ██╗ █████╗ \n"
            "  ████╗  ██║██╔═══██╗██║   ██║██╔══██╗\n"
            "  ██╔██╗ ██║██║   ██║██║   ██║███████║\n"
            "  ██║╚██╗██║██║   ██║╚██╗ ██╔╝██╔══██║\n"
            "  ██║ ╚████║╚██████╔╝ ╚████╔╝ ██║  ██║\n"
            "  ╚═╝  ╚═══╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝"
            "[/bold #00d4aa]"
        )
        self.chat_log.write("")
        self.chat_log.write("[dim]  Autonomous System Agent  //  v1.0[/dim]")
        self.chat_log.write("[dim]  " + "─" * 38 + "[/dim]")
        self.chat_log.write("")

    # ── Stats sidebar ──────────────────────────────────────────────────────

    def _tick_stats(self) -> None:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        delta = str(datetime.now() - self._nova_start_time).split(".")[0]
        session = datetime.now().strftime("%H:%M")

        cpu_color = "#00d4aa" if cpu < 70 else "#ff9900" if cpu < 90 else "#ff4444"
        ram_color = "#00d4aa" if ram < 70 else "#ff9900" if ram < 90 else "#ff4444"

        self.query_one("#cpu_val").update(f"[{cpu_color}]{cpu:.1f}%[/{cpu_color}]")
        self.query_one("#ram_val").update(f"[{ram_color}]{ram:.1f}%[/{ram_color}]")
        self.query_one("#uptime_val").update(f"[#888888]{delta}[/#888888]")
        self.query_one("#session_val").update(f"[#444444]{session}[/#444444]")

    def _set_status(self, status: str, tool: str = None) -> None:
        color_map = {
            "IDLE":       "#00d4aa",
            "PENSANDO":   "#00aaff",
            "EJECUTANDO": "#ffaa00",
            "ERROR":      "#ff4444",
        }
        color = color_map.get(status, "#888888")
        self.query_one("#status_val").update(f"[{color}]{status}[/{color}]")
        if tool:
            self.query_one("#last_tool_val").update(f"[#666666]{tool}[/#666666]")

    def _set_iter(self, current: int, total: int) -> None:
        pct = int((current / total) * 10)
        bar = "█" * pct + "░" * (10 - pct)
        self.query_one("#iter_val").update(
            f"[#555555]{bar}[/#555555] [dim]{current}/{total}[/dim]"
        )

    # ── Input ──────────────────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return
        if user_text.lower() in ["salir", "exit", "quit"]:
            self.memory.save(self.nova.history)
            self.exit()

        self.query_one("#user_input").value = "" # Después de recibir el input, se limpia el campo
        self.chat_log.write("")
        self.chat_log.write(f"[bold white]>[/bold white] [white]{user_text}[/white]")
        self.process_nova_query(user_text)

    # ── Procesamiento ──────────────────────────────────────────────────────
    async def _request_authorization(self, tool_name: str, args: dict) -> bool:
        return await self.push_screen_wait(SecurityModal(tool_name, args))

    @work(exclusive=True)
    async def process_nova_query(self, user_input: str) -> None:
        self.chat_log.write("[dim]// procesando...[/dim]")
        self._set_status("PENSANDO")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.nova.process_query, user_input)

            max_iterations = self._max_iter # copia local a decrementar (para no modificar la original)
            current_iter = 0

            while response.tool_calls and max_iterations > 0:
                max_iterations -= 1
                current_iter += 1
                self._set_iter(current_iter, self._max_iter)

                for tool_call in response.tool_calls:
                    name = tool_call["name"]
                    args = tool_call["args"]

                    self._set_status("EJECUTANDO", name)

                    if name in ToolExecutor.SENSITIVE_TOOLS:
                        self.chat_log.write(
                            f"[dim]//[/dim] [yellow]auth?[/yellow] [bold white]{name}[/bold white]"
                        )
                        authorized = await self._request_authorization(name, args)
                        if not authorized:
                            self.nova.add_tool_message(
                                "STATUS: 403_FORBIDDEN. El usuario denegó la ejecución.",
                                tool_call["id"],
                            )
                            self.chat_log.write(
                                f"[dim]//[/dim] [red]denegado →[/red] [dim]{name}[/dim]"
                            )
                            continue

                    self.chat_log.write(
                        f"[dim]//[/dim] [#00d4aa]exec →[/#00d4aa] [bold]{name}[/bold]"
                    )
                    result = await loop.run_in_executor(
                        None, ToolExecutor.execute_direct, tool_call
                    )
                    self.nova.add_tool_message(result, tool_call["id"])

                self._set_status("PENSANDO")
                response = await loop.run_in_executor(None, self.nova.ask_again)

            # Respuesta final
            final_text = self.nova.clean_content(response.content)

            # Si iteraciones agotadas y aún uso de tools -> forzar a generar una respuesta
            if max_iterations == 0 and response.tool_calls:
                self.chat_log.write(
                    "[dim]// límite de iteraciones alcanzado — generando resumen[/dim]"
                )
                # Importación local
                from langchain_core.messages import HumanMessage
                self.nova.history.append(HumanMessage(
                    content="Has alcanzado el límite de operaciones. No uses más herramientas. "
                            "Con la información recolectada, genera la mejor explicación posible."
                ))
                response = await loop.run_in_executor(None, self.nova.ask_again)
                final_text = self.nova.clean_content(response.content)

            if not final_text.strip() or "problema técnico" in final_text.lower():
                from langchain_core.messages import HumanMessage
                self.nova.history.append(HumanMessage(
                    content="Tu respuesta fue vaga. Revisa los resultados de las herramientas "
                            "en el historial y genera un resumen técnico real."
                ))
                response = await loop.run_in_executor(None, self.nova.ask_again)
                final_text = self.nova.clean_content(response.content)

            # Renderizar respuesta
            self.chat_log.write("")
            self.chat_log.write(Panel(
                f"[#cccccc]{final_text}[/#cccccc]",
                title="[bold #00d4aa]nova[/bold #00d4aa]",
                border_style="#1e1e1e",
                padding=(1, 2),
            ))

            self._set_status("IDLE")
            self._set_iter(0, self._max_iter)
            self.memory.save(self.nova.history)

        except Exception as e:
            from nova_agent.brain import ModelNotAvailableError
            self._set_status("ERROR")

            if isinstance(e, ModelNotAvailableError):
                self.chat_log.write(f"[red]// modelo no disponible:[/red] {e}")
                self.chat_log.write("[yellow]// abriendo configuración...[/yellow]")
                await asyncio.sleep(1.5)
                saved = await self.push_screen_wait(SetupModal())
                if saved:
                    self.chat_log.write("[dim]// reiniciando con nuevo modelo...[/dim]")
                    self.nova = Brain()
                    self._set_status("IDLE")
            else:
                self.chat_log.write(f"[red]// error: {e}[/red]")


# ── Entry point ────────────────────────────────────────────────────────────

app = NovaTUI()

# toml: nova_agent.ui:run
def run():
    """Punto de entrada para el comando 'nova'."""
    app.run()


if __name__ == "__main__":
    run()