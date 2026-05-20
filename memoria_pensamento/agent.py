# pyright: reportMissingImports=false, reportMissingModuleSource=false
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext, NOT_GIVEN
from livekit.plugins import noise_cancellation, google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from mem0 import AsyncMemoryClient
import logging
import os
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def _load_env_files() -> None:
    load_dotenv(PROJECT_DIR / ".env")
    for parent in PROJECT_DIR.parents:
        shared_env = parent / "cerebro_ia" / ".env"
        if shared_env.exists():
            load_dotenv(shared_env, override=False)
            break


def _get_google_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _get_google_realtime_model() -> str:
    return (
        os.getenv("GOOGLE_REALTIME_MODEL")
        or os.getenv("GEMINI_REALTIME_MODEL")
        or "gemini-2.5-flash-native-audio-preview-12-2025"
    )


_load_env_files()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Assistant(Agent):
    def __init__(self, chat_ctx: ChatContext | None = None):
        super().__init__(

            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                model=_get_google_realtime_model(),
                api_key=_get_google_api_key() or NOT_GIVEN,
                voice="Charon",
                temperature=0.6,
            ),
            chat_ctx=chat_ctx,
        )


async def entrypoint(ctx: agents.JobContext):
    
    async def shutdown_hook(chat_ctx: ChatContext, mem0: AsyncMemoryClient, memory_str: str):
        logging.info("Shutting down, saving chat context to memory...")

        messages_formatted = []

        logging.info(f"Chat context messages: {chat_ctx.items}")

        for item in chat_ctx.items:
            if not hasattr(item, 'content') or item.content is None: # type: ignore
              continue
            content_str = ''.join(item.content) if isinstance(item.content, list) else str(item.content) # type: ignore

            if memory_str and memory_str in content_str:
                continue

            if item.role in ['user', 'assistant']: # type: ignore
                messages_formatted.append({
                    "role": item.role, # type: ignore
                    "content": content_str.strip()
                })

        logging.info(f"Formatted messages to add to memory: {messages_formatted}")
        # Assuming user_id is consistent
        await mem0.add(messages_formatted, user_id="GabrielGoulartdeSouza")
        logging.info("Chat context saved to memory.")

    # Initialize Memory Client
    mem0 = AsyncMemoryClient()
    user_id = "GabrielGoulartdeSouza"

    # Load existing memories - try get_all first, fallback to search
    initial_ctx = ChatContext()
    memory_str = ''
    results = []
    
    try:
        # Try to get all memories for the user
        results = await mem0.get_all(user_id=user_id)
        logging.info(f"Retrieved {len(results) if results else 0} memories using get_all")
    except Exception as e:
        logging.warning(f"get_all failed: {e}. Trying search method...")
        try:
            # Fallback: use search with a broad query (empty query causes 400 error)
            response = await mem0.search("informações preferências contexto", filters={"user_id": user_id})
            results = response["results"] if isinstance(response, dict) and "results" in response else response
            logging.info(f"Retrieved {len(results) if results else 0} memories using search")
        except Exception as e2:
            logging.warning(f"Search also failed: {e2}. No memories loaded.")
            results = []

    if results:
        memories = []
        for result in results:
            if not isinstance(result, dict):
                continue

            memory = result.get("memory") or result.get("text") or result.get("content")
            if not memory:
                continue

            memories.append(
                {
                    "memory": str(memory),
                    "updated_at": str(result.get("updated_at", "")),
                }
            )
        
        if memories:
            memory_str = json.dumps(memories, ensure_ascii=False)
            logging.info(f"Formatted memories: {memory_str}")
            initial_ctx.add_message(
                role="assistant",
                content=f"O nome do usuário é {user_id}. Aqui estão informações importantes sobre ele que você deve lembrar e usar nas conversas: {memory_str}."
            )
    else:
        logging.info("No memories found for this user. Starting fresh conversation.")

    await ctx.connect()

    session = AgentSession()

    agent = Assistant(chat_ctx=initial_ctx)

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    async def shutdown_callback():
        await shutdown_hook(agent.chat_ctx, mem0, memory_str)

    ctx.add_shutdown_callback(shutdown_callback)

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION  + "\nCumprimente o usuário de forma breve e confiante."
    )


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint)
    )

