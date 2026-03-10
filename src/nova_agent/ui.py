import asyncio
import psutil
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Button, Label, Static
from textual import work
from textual.screen import ModalScreen
from textual.containers import Grid, Horizontal, Vertical
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule

from nova_agent.brain import Brain
from nova_agent.executor import ToolExecutor
from nova_agent.memory import MemoryManager


class SecurityModal(ModalScreen[bool]):
    """Modal de confirmación para acciones sensibles."""

    def __init__(self, tool_name: str, args: dict):
        super().__init__()
        self.tool_name = tool_name
        self.args = args

    def compose(self) -> ComposeResult:
        with Grid(id="modal_grid"):
            yield Label("[ AUTORIZACIÓN REQUERIDA ]", id="modal_title")
            yield Static(
                f"[dim]OPERACIÓN  :[/dim] [bold white]{self.tool_name}[/bold white]\n"
                f"[dim]ARGUMENTOS :[/dim] [white]{self.args}[/white]",
                id="modal_body",
            )
            yield Button("[ PERMITIR ]", variant="success", id="allow")
            yield Button("[ DENEGAR ]", variant="error", id="deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "allow")


class NovaTUI(App):
    """Nova Agent — Terminal UI minimalista industrial."""

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

    /* ── Modal ────────────────────────────────────────────── */
    #modal_grid {
        grid-size: 2;
        grid-gutter: 1;
        grid-rows: auto 1fr auto;
        padding: 1 2;
        background: #0d0d0d;
        border: solid #00d4aa;
        width: 58;
        height: 18;
        align: center middle;
    }

    #modal_title {
        column-span: 2;
        text-align: center;
        color: #ff4444;
        text-style: bold;
        margin-bottom: 1;
    }

    #modal_body {
        column-span: 2;
        color: #aaaaaa;
        border-top: solid #1e1e1e;
        border-bottom: solid #1e1e1e;
        padding: 1;
        margin: 1 0;
    }

    #allow {
        width: 100%;
        background: #003322;
        color: #00d4aa;
        border: solid #00d4aa;
        text-style: bold;
    }

    #allow:hover {
        background: #004433;
    }

    #deny {
        width: 100%;
        background: #220000;
        color: #ff4444;
        border: solid #ff4444;
        text-style: bold;
    }

    #deny:hover {
        background: #330000;
    }
    """

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

    def on_mount(self) -> None:
        self._nova_start_time = datetime.now()
        self._current_iter = 0
        self._max_iter = 15

        self.nova = Brain()
        self.memory = MemoryManager()
        self.chat_log = self.query_one("#chat_log", RichLog)

        self.set_interval(2.0, self._tick_stats)

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
        self.chat_log.write("[dim]  Autonomous System Agent  //  v2.0[/dim]")
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

        self.query_one("#user_input").value = ""
        self.chat_log.write("")
        self.chat_log.write(f"[bold white]>[/bold white] [white]{user_text}[/white]")
        self.process_nova_query(user_text)

    # ── Procesamiento ──────────────────────────────────────────────────────

    @work(exclusive=True)
    async def process_nova_query(self, user_input: str) -> None:
        self.chat_log.write("[dim]// procesando...[/dim]")
        self._set_status("PENSANDO")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.nova.process_query, user_input)

            max_iterations = self._max_iter
            current_iter = 0

            while response.tool_calls and max_iterations > 0:
                max_iterations -= 1
                current_iter += 1
                self._set_iter(current_iter, self._max_iter)

                for tool_call in response.tool_calls:
                    name = tool_call["name"]
                    args = tool_call["args"]

                    self._set_status("EJECUTANDO", name)

                    if name in ["write_file", "delete_file", "run_command"]:
                        self.chat_log.write(
                            f"[dim]//[/dim] [yellow]auth?[/yellow] [bold white]{name}[/bold white]"
                        )
                        authorized = await self.push_screen_wait(SecurityModal(name, args))
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

            if max_iterations == 0 and response.tool_calls:
                self.chat_log.write(
                    "[dim]// límite de iteraciones alcanzado — generando resumen[/dim]"
                )
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

            # Renderizar respuesta con borde limpio
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
            self.chat_log.write(f"[red]// error: {e}[/red]")
            self._set_status("ERROR")


# ── Entry point ────────────────────────────────────────────────────────────

app = NovaTUI()


def run():
    """Punto de entrada para el comando 'nova'."""
    app.run()


if __name__ == "__main__":
    run()