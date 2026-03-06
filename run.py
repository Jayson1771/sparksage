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


async def _init_and_start():
    """Initialize DB, reload config, then start the bot — all in ONE event loop."""
    import db
    import config
    import providers

    # Step 1: Init DB tables
    await db.init_db()

    # Step 2: Seed config from .env into DB
    await db.sync_env_to_db()

    # Step 3: Reload config from DB into memory
    db_config = await db.get_all_config()
    config.reload_from_db(db_config)

    available = providers.get_available_providers()
    print("=" * 50)
    print("  SparkSage — Bot + Dashboard Launcher")
    print("=" * 50)

    # Step 4: Start FastAPI in background thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    print(f"  API server starting on http://localhost:{port}")
    await asyncio.sleep(2)  # Wait for API to be ready (async-friendly)

    if not config.DISCORD_TOKEN:
        print("  WARNING: DISCORD_TOKEN not set — bot will not start.")
        print(f"  Open http://localhost:{port} to configure the bot.")
        # Keep running so the API stays alive
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nShutting down...")
        return

    if not available:
        print("  WARNING: No AI providers configured. Add at least one API key.")

    print(f"  Primary provider: {config.AI_PROVIDER}")
    print(f"  Fallback chain: {' -> '.join(available) if available else 'none'}")
    print("=" * 50)

    # Step 5: Start the Discord bot (still in same event loop)
    from bot import start
    await start()


def main():
    try:
        asyncio.run(_init_and_start())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"\n  ERROR: {e}")
        raise


if __name__ == "__main__":
    main()