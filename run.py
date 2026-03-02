"""Unified launcher: starts FastAPI in a background thread and the Discord bot in the main thread."""

import asyncio
import threading
import os
import time
import uvicorn


def start_api_server():
    """Run the FastAPI server in a background thread."""
    from api.main import create_app

    app = create_app()
    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


async def _init_database():
    """Initialize the database and seed config from .env."""
    import db
    await db.init_db()
    await db.sync_env_to_db()


async def _reload_config():
    """Reload config from DB after init."""
    import db
    import config
    db_config = await db.get_all_config()
    config.reload_from_db(db_config)


def main():
    import config
    import providers

    # Initialize database and reload config from DB
    asyncio.run(_init_database())
    asyncio.run(_reload_config())

    available = providers.get_available_providers()

    print("=" * 50)
    print("  SparkSage — Bot + Dashboard Launcher")
    print("=" * 50)

    # Start FastAPI in background thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    print(f"  API server starting on http://localhost:{port}")

    # Wait for API to be ready
    time.sleep(2)

    if not config.DISCORD_TOKEN:
        print("  WARNING: DISCORD_TOKEN not set — bot will not start.")
        print(f"  Open http://localhost:{port} to configure the bot.")
        try:
            api_thread.join()
        except KeyboardInterrupt:
            print("\nShutting down...")
        return

    if not available:
        print("  WARNING: No AI providers configured. Add at least one API key.")

    print(f"  Primary provider: {config.AI_PROVIDER}")
    print(f"  Fallback chain: {' -> '.join(available) if available else 'none'}")
    print("=" * 50)

    # Start bot using new async start() function
    from bot import start
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"\n  ERROR: Bot failed to start — {e}")
        print("  Check your DISCORD_TOKEN and bot intents in the Discord Developer Portal.")
        try:
            api_thread.join()
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()