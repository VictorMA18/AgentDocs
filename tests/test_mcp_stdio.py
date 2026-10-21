"""El servidor como lo ejecuta un cliente real: un subproceso que habla MCP por stdin/stdout."""

import asyncio
import os
import sys
from pathlib import Path

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters


def server_params(tmp_path: Path) -> StdioServerParameters:
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "data"), "LOGS_DIR": str(tmp_path / "logs"),
        "OUTPUTS_DIR": str(tmp_path / "outputs"),
        # Si el servidor cargara el modelo al arrancar, este nombre inexistente lo haría fallar:
        "EMBEDDING_MODEL": "modelo-que-no-existe/para-el-test",
    }
    return StdioServerParameters(command=sys.executable, args=["-m", "techdoc_agent.mcp_server"], env=env)


def test_server_speaks_mcp_over_stdio_without_loading_the_model(tmp_path: Path) -> None:
    async def run() -> tuple[list[str], str, str]:
        async with Client(server_params(tmp_path)) as client:  # initialize: cualquier byte extra en stdout lo rompería
            tools = [t.name for t in (await client.list_tools()).tools]
            listed = await client.call_tool("listar_documentos", {})
            rejected = await client.call_tool("ingestar_documento", {"ruta": "../../etc/passwd"})
            assert not listed.is_error and rejected.is_error
            return tools, listed.content[0].text, rejected.content[0].text

    tools, listed, rejected = asyncio.run(asyncio.wait_for(run(), timeout=60))
    assert sorted(tools) == ["buscar_documentos", "ingestar_documento", "listar_documentos", "preguntar_agente"]
    assert listed == "No hay documentos indexados."
    assert "Ruta no permitida" in rejected
