"""Interfaz de línea de comandos (CLI) para meet-tools."""

import asyncio
import logging
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from meet_tools.client import MeetClient
from meet_tools.daemon import MeetDaemon
from meet_tools.protocol import Action, ErrorCode, Message, MessageType, Source, StateSyncPayload

app = typer.Typer(help="Sistema de control externo para Google Meet.", no_args_is_help=True)
console = Console()


@app.command()
def daemon(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Dirección IP de escucha (0.0.0.0 para LAN y loopback)"),
    port: int = typer.Option(8765, "--port", "-p", help="Puerto TCP para el servidor WebSocket"),
    timeout: float = typer.Option(2.5, "--timeout", "-t", help="Timeout para ack de extensión (segundos)"),
    pin: Optional[str] = typer.Option(None, "--pin", help="PIN de seguridad de 4 dígitos (si se omite, se genera aleatorio)"),
    no_pin: bool = typer.Option(False, "--no-pin", help="Desactivar requerimiento de PIN (modo permisivo)"),
):
    """Inicia el daemon concentrador WebSocket en primer plano."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    server = MeetDaemon(host=host, port=port, command_timeout=timeout, pin=pin, require_pin=not no_pin)

    pin_info = f"PIN de Emparejamiento: [bold yellow]{server.pin}[/bold yellow] {'(Opcional)' if no_pin else '(Requerido)'}\n"
    console.print(Panel.fit(
        f"[bold cyan]Meet Daemon Concentrador v1.1[/bold cyan]\n"
        f"Escuchando en: [bold green]ws://{host}:{port}[/bold green]\n"
        f"{pin_info}"
        f"Conexión extensión: [dim]ws://127.0.0.1:{port}[/dim]\n"
        f"Conexión LAN (Android/HW): [dim]ws://<IP_LOCAL>:{port}[/dim]",
        border_style="cyan"
    ))

    async def _run():
        await server.start()
        try:
            # Mantener en ejecución hasta interrupción
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await server.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon detenido por el usuario.[/yellow]")


def _send_cmd_helper(action: Action, uri: str = "ws://127.0.0.1:8765", payload: Optional[dict] = None) -> None:
    async def _run():
        try:
            async with MeetClient(uri=uri) as client:
                resp = await client.send_command(action, payload or {})
                if resp.type == MessageType.ACK:
                    console.print(f"[bold green]✓ Acción ejecutada exitosamente:[/bold green] {action.value}")
                elif resp.type == MessageType.ERROR:
                    code = resp.payload.get("code", "ERROR")
                    reason = resp.payload.get("reason", "Error desconocido")
                    console.print(f"[bold red]✗ Comando rechazado ({code}):[/bold red] {reason}")
                else:
                    console.print(f"[cyan]Respuesta recibida:[/cyan] {resp.action} {resp.payload}")
        except Exception as e:
            console.print(f"[bold red]Error de conexión con el daemon en {uri}:[/bold red] {e}")

    asyncio.run(_run())


@app.command()
def status(
    uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u", help="URI del daemon concentrador"),
):
    """Consulta y muestra el estado actual consolidado de la sesión de Google Meet."""
    async def _run():
        try:
            async with MeetClient(uri=uri) as client:
                st = await client.get_state()
                table = Table(title="Estado Consolidado de Google Meet", border_style="cyan")
                table.add_column("Parámetro", style="bold white")
                table.add_column("Valor", style="bold")

                table.add_row("En Llamada", "[green]Sí[/green]" if st.inCall else "[red]No[/red]")
                table.add_row("Micrófono", "[red]Muteado[/red]" if st.micMuted else "[green]Abierto[/green]")
                table.add_row("Cámara", "[red]Apagada[/red]" if st.cameraOff else "[green]Encendida[/green]")
                table.add_row("Mano Levantada", "[yellow]Sí[/yellow]" if st.handRaised else "[dim]No[/dim]")
                table.add_row("Participantes", str(st.participantCount))
                table.add_row("Sala de Espera", f"[bold yellow]{st.waitingRoomCount}[/bold yellow]" if st.waitingRoomCount > 0 else "0")
                table.add_row("Rol Anfitrión", "[cyan]Sí (Host)[/cyan]" if st.isHost else "[dim]No (Invitado)[/dim]")
                table.add_row("Bloqueo de Ambigüedad", "[bold red]LOCKED (Múltiples llamadas)[/bold red]" if st.locked else "[green]Desbloqueado[/green]")

                console.print(table)
        except Exception as e:
            console.print(f"[bold red]Error de conexión con el daemon en {uri}:[/bold red] {e}")

    asyncio.run(_run())


@app.command()
def mic(uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u")):
    """Conmuta el micrófono propio (TOGGLE_MIC)."""
    _send_cmd_helper(Action.TOGGLE_MIC, uri=uri)


@app.command()
def cam(uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u")):
    """Conmuta la cámara propia (TOGGLE_CAM)."""
    _send_cmd_helper(Action.TOGGLE_CAM, uri=uri)


@app.command()
def hand(uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u")):
    """Conmuta levantar/bajar la mano (TOGGLE_HAND)."""
    _send_cmd_helper(Action.TOGGLE_HAND, uri=uri)


@app.command("admit-all")
def admit_all(uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u")):
    """Acciona 'Admitir a todos' en la sala de espera (ADMIT_ALL)."""
    _send_cmd_helper(Action.ADMIT_ALL, uri=uri)


@app.command("mute-all")
def mute_all(uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u")):
    """Acciona 'Silenciar a todos' los participantes (MUTE_ALL)."""
    _send_cmd_helper(Action.MUTE_ALL, uri=uri)


@app.command("leave")
def leave(
    end_for_all: bool = typer.Option(False, "--all", "-a", help="Finalizar la llamada para todos (solo anfitriones)"),
    uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u"),
):
    """Abandona la reunión (LEAVE_CALL)."""
    _send_cmd_helper(Action.LEAVE_CALL, uri=uri, payload={"endForAll": end_for_all})


@app.command()
def monitor(
    uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u", help="URI del daemon concentrador"),
):
    """Escucha y muestra en tiempo real todos los eventos y telemetría de Meet."""
    async def _run():
        console.print(f"[cyan]Conectando a {uri} para monitoreo continuo... (Ctrl+C para salir)[/cyan]")
        try:
            async with MeetClient(uri=uri) as client:
                async for msg in client.listen_events():
                    if msg.action == Action.STATE_SYNC.value:
                        p = msg.payload
                        console.print(
                            f"[bold green][STATE_SYNC][/bold green] inCall={p.get('inCall')} | "
                            f"mic={p.get('micMuted')} | cam={p.get('cameraOff')} | "
                            f"hand={p.get('handRaised')} | part={p.get('participantCount')} | "
                            f"wait={p.get('waitingRoomCount')} | host={p.get('isHost')} | "
                            f"locked={p.get('locked')}"
                        )
                    elif msg.action == Action.ADMISSION_REQUESTED.value:
                        console.print(f"[bold yellow][ADMISSION_REQUESTED][/bold yellow] Nuevos usuarios esperando: {msg.payload.get('count')}")
                    elif msg.action == Action.PERMISSION_DENIED.value:
                        console.print(f"[bold red][PERMISSION_DENIED][/bold red] Acción '{msg.payload.get('action')}': {msg.payload.get('detail')}")
                    elif msg.action == Action.LOCKED_STATE.value:
                        console.print(f"[bold red][LOCKED_STATE][/bold red] Bloqueado={msg.payload.get('locked')}: {msg.payload.get('reason')}")
                    else:
                        console.print(f"[dim]{msg.action}[/dim] {msg.payload}")
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoreo finalizado.[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Error durante monitoreo:[/bold red] {e}")

    asyncio.run(_run())


@app.command("mock-tab")
def mock_tab(
    tab_id: str = typer.Option("tab_mock_1", "--tab-id", "-t", help="Identificador único de la pestaña simulada"),
    in_call: bool = typer.Option(True, "--in-call/--lobby", help="Estado inicial de llamada"),
    is_host: bool = typer.Option(True, "--host/--guest", help="Rol de anfitrión"),
    uri: str = typer.Option("ws://127.0.0.1:8765", "--uri", "-u"),
):
    """Simula una pestaña de Google Meet con la extensión para pruebas locales."""
    import websockets
    from websockets.asyncio.client import connect

    async def _run():
        console.print(f"[cyan]Iniciando pestaña simulada '{tab_id}' conectando a {uri}...[/cyan]")
        state = StateSyncPayload(
            inCall=in_call,
            micMuted=False,
            cameraOff=False,
            handRaised=False,
            participantCount=5,
            waitingRoomCount=0,
            isHost=is_host,
            tabId=tab_id
        )

        async with connect(uri, proxy=None) as ws:
            # Consumir saludo del daemon
            await ws.recv()

            # Registrar como extensión
            await ws.send(Message.state_sync(state, source=Source.EXTENSION).to_json())
            console.print(f"[green]Pestaña '{tab_id}' registrada con éxito. Esperando comandos...[/green]")

            async for raw in ws:
                msg = Message.from_json(raw)
                console.print(f"[dim]Pestaña recibió:[/dim] {msg.type} {msg.action} {msg.payload}")

                if msg.type == MessageType.COMMAND:
                    req_id = msg.payload.get("requestId", "req_unknown")
                    if msg.action == Action.TOGGLE_MIC.value:
                        state.micMuted = not state.micMuted
                        ack = Message.ack(msg.action, {"requestId": req_id, "micMuted": state.micMuted}, source=Source.EXTENSION)
                        await ws.send(ack.to_json())
                        await ws.send(Message.state_sync(state, source=Source.EXTENSION).to_json())
                        console.print(f"[bold green]Micrófono conmutado -> {state.micMuted}[/bold green]")

                    elif msg.action == Action.TOGGLE_CAM.value:
                        state.cameraOff = not state.cameraOff
                        ack = Message.ack(msg.action, {"requestId": req_id, "cameraOff": state.cameraOff}, source=Source.EXTENSION)
                        await ws.send(ack.to_json())
                        await ws.send(Message.state_sync(state, source=Source.EXTENSION).to_json())
                        console.print(f"[bold green]Cámara conmutada -> {state.cameraOff}[/bold green]")

                    elif msg.action == Action.MUTE_ALL.value and not state.isHost:
                        # Rechazar por falta de permisos
                        perm = Message.event(Action.PERMISSION_DENIED, {"action": "MUTE_ALL", "detail": "Sin permisos de anfitrión"}, source=Source.EXTENSION)
                        await ws.send(perm.to_json())
                        err = Message.error("Sin permisos de anfitrión", ErrorCode.ERR_PERMISSION_DENIED, source=Source.EXTENSION)
                        err.payload["requestId"] = req_id
                        await ws.send(err.to_json())
                        console.print("[bold red]MUTE_ALL denegado: falta rol de anfitrión[/bold red]")

                    else:
                        ack = Message.ack(msg.action, {"requestId": req_id, "status": "ok"}, source=Source.EXTENSION)
                        await ws.send(ack.to_json())

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Pestaña simulada desconectada.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error en pestaña simulada:[/bold red] {e}")


@app.command()
def pack(
    target: str = typer.Option("both", "--target", "-t", help="Navegador objetivo: chrome, firefox o both"),
    out_dir: str = typer.Option("dist", "--out-dir", "-o", help="Directorio de salida para los paquetes"),
):
    """Empaqueta la extensión WebExtensions para Chrome (.zip) y Firefox (.xpi)."""
    from pathlib import Path
    from meet_tools.packer import package_extension

    try:
        res = package_extension(target=target, output_dir=Path(out_dir))
        for tgt, p in res.items():
            console.print(f"[bold green]✓ Paquete generado ({tgt}):[/bold green] [cyan]{p}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Error al empaquetar:[/bold red] {e}")


@app.command()
def sign(
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="API Key (JWT issuer) de Mozilla AMO"),
    api_secret: Optional[str] = typer.Option(None, "--api-secret", "-s", help="API Secret de Mozilla AMO"),
    channel: str = typer.Option("unlisted", "--channel", "-c", help="Canal de distribución: unlisted o listed"),
    out_dir: str = typer.Option("dist", "--out-dir", "-o", help="Directorio destino para el .xpi firmado"),
    lint_only: bool = typer.Option(False, "--lint-only", help="Solo validar compatibilidad y manifiesto con web-ext lint"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Verificar manifiesto e imprimir el comando web-ext sign sin enviar"),
):
    """Valida y firma digitalmente el addon para Firefox utilizando Mozilla web-ext."""
    from pathlib import Path
    from meet_tools.signer import sign_firefox_addon

    try:
        res = sign_firefox_addon(
            output_dir=Path(out_dir),
            api_key=api_key,
            api_secret=api_secret,
            channel=channel,
            lint_only=lint_only,
            dry_run=dry_run
        )
        if dry_run:
            console.print("[bold yellow]Modo Dry-Run activo:[/bold yellow]")
            console.print(f"Comando planificado: [cyan]{res['command']}[/cyan]")
            console.print(f"Credenciales detectadas: {'[green]Sí[/green]' if res['credentials_present'] else '[red]No[/red]'}")
        elif lint_only:
            console.print("[bold green]✓ Validación web-ext lint superada con éxito.[/bold green]")
            if res.get("lint_output"):
                console.print(f"[dim]{res['lint_output']}[/dim]")
        else:
            console.print(f"[bold green]✓ Addon firmado exitosamente:[/bold green] [cyan]{res['signed_file']}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Error durante firma con web-ext:[/bold red] {e}")


def main():
    app()


if __name__ == "__main__":
    main()


