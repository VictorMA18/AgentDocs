"""Ensamblado del agente con su configuración por defecto (lo usan la CLI y la API web)."""

from __future__ import annotations

from techdoc_agent.core.agent import Agent
from techdoc_agent.core.llm import LLMClient
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.prompts import build_system_prompt
from techdoc_agent.core.skills import load_skill
from techdoc_agent.core.tools import ToolRegistry
from techdoc_agent.core.tools_outputs import output_tools
from techdoc_agent.core.tools_rag import rag_tools
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.store import VectorStore


def build_agent(
    llm: LLMClient, store: VectorStore, embedder: Embedder, memory: Memory | None = None
) -> Agent:
    """Une el LLM, las herramientas RAG y de salida y el system prompt (reglas fijas + skill activa).

    ``memory`` por defecto vive en RAM; un adaptador puede pasar una ``Memory`` con carpeta.
    """
    prompt = build_system_prompt(load_skill())
    tools = ToolRegistry([*rag_tools(store, embedder), *output_tools()])
    return Agent(llm, tools, memory if memory is not None else Memory(), prompt)
