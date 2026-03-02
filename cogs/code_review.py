from __future__ import annotations

import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import config
import providers
import db as database

CODE_REVIEW_PROMPT = """You are a senior code reviewer. Analyze the provided code for:
1. Bugs and potential errors
2. Style and best practices
3. Performance improvements
4. Security concerns

Respond with markdown formatting using code blocks where appropriate.
Be concise but thorough. Structure your response with clear sections."""

SUPPORTED_LANGUAGES = [
    "python", "javascript", "typescript", "java", "c", "cpp",
    "csharp", "go", "rust", "php", "ruby", "swift", "kotlin", "sql"
]


def detect_language(code: str) -> str:
    """Basic language auto-detection based on common patterns."""
    code_lower = code.lower()
    if "def " in code and ":" in code and ("import " in code or "print(" in code):
        return "python"
    if "console.log" in code or "const " in code or "let " in code or "=>" in code:
        return "javascript"
    if "interface " in code or ": string" in code or ": number" in code:
        return "typescript"
    if "public static void main" in code or "System.out.println" in code:
        return "java"
    if "fn " in code and "let mut" in code:
        return "rust"
    if "func " in code and "fmt." in code:
        return "go"
    if "SELECT " in code_lower or "INSERT INTO" in code_lower:
        return "sql"
    if "#include" in code:
        return "cpp"
    return "plaintext"


class CodeReview(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="review", description="Review a code snippet for bugs, style, and improvements")
    @app_commands.describe(
        code="The code snippet to review",
        language="Programming language (optional — auto-detected if omitted)"
    )
    @app_commands.choices(language=[
        app_commands.Choice(name=lang.capitalize(), value=lang)
        for lang in SUPPORTED_LANGUAGES
    ])
    async def review(
        self,
        interaction: discord.Interaction,
        code: str,
        language: str | None = None,
    ):
        await interaction.response.defer()

        try:
            # Auto-detect language if not provided
            detected_lang = language or detect_language(code)

            # Build the review message
            review_message = f"Please review this {detected_lang} code:\n\n```{detected_lang}\n{code}\n```"

            # Store in DB tagged as code review
            await database.add_message(
                str(interaction.channel_id),
                "user",
                f"[CODE REVIEW] {interaction.user.display_name}: {review_message}"
            )

            # Get conversation history
            messages = await database.get_messages(str(interaction.channel_id), limit=10)
            history = [{"role": m["role"], "content": m["content"]} for m in messages]

            # Run blocking AI call in executor
            loop = asyncio.get_event_loop()
            response, provider_name = await loop.run_in_executor(
                None,
                providers.chat,
                history,
                CODE_REVIEW_PROMPT
            )

            # Store response tagged as code review
            await database.add_message(
                str(interaction.channel_id),
                "assistant",
                f"[CODE REVIEW] {response}",
                provider=provider_name
            )

            provider_label = config.PROVIDERS.get(provider_name, {}).get("name", provider_name)
            footer = f"\n-# Code review powered by {provider_label}"

            # Send header
            lang_display = detected_lang.capitalize()
            auto_note = " *(auto-detected)*" if not language else ""
            header = f"## 🔍 Code Review — {lang_display}{auto_note}\n\n"

            # Split and send response in chunks
            full_response = header + response + footer
            for i in range(0, len(full_response), 1900):
                await interaction.followup.send(full_response[i: i + 1900])

        except Exception as e:
            print(f"Error in /review: {e}")
            await interaction.followup.send("Something went wrong during code review. Please try again.")

    @app_commands.command(name="review-file", description="Review code from a uploaded file")
    @app_commands.describe(
        file="Upload a code file to review",
        language="Programming language (optional)"
    )
    async def review_file(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        language: str | None = None,
    ):
        await interaction.response.defer()

        try:
            # Check file size (max 50KB)
            if file.size > 50_000:
                await interaction.followup.send("File is too large. Please keep code files under 50KB.")
                return

            # Read file content
            code_bytes = await file.read()
            code = code_bytes.decode("utf-8", errors="replace")

            # Auto-detect language from filename or content
            detected_lang = language
            if not detected_lang:
                ext_map = {
                    ".py": "python", ".js": "javascript", ".ts": "typescript",
                    ".java": "java", ".rs": "rust", ".go": "go", ".sql": "sql",
                    ".cpp": "cpp", ".c": "c", ".cs": "csharp", ".rb": "ruby",
                    ".php": "php", ".swift": "swift", ".kt": "kotlin"
                }
                for ext, lang_name in ext_map.items():
                    if file.filename.endswith(ext):
                        detected_lang = lang_name
                        break
                if not detected_lang:
                    detected_lang = detect_language(code)

            review_message = f"Please review this {detected_lang} code from file `{file.filename}`:\n\n```{detected_lang}\n{code[:3000]}\n```"
            if len(code) > 3000:
                review_message += f"\n*(showing first 3000 of {len(code)} characters)*"

            await database.add_message(
                str(interaction.channel_id),
                "user",
                f"[CODE REVIEW FILE] {interaction.user.display_name}: {review_message}"
            )

            messages = await database.get_messages(str(interaction.channel_id), limit=10)
            history = [{"role": m["role"], "content": m["content"]} for m in messages]

            loop = asyncio.get_event_loop()
            response, provider_name = await loop.run_in_executor(
                None,
                providers.chat,
                history,
                CODE_REVIEW_PROMPT
            )

            await database.add_message(
                str(interaction.channel_id),
                "assistant",
                f"[CODE REVIEW] {response}",
                provider=provider_name
            )

            provider_label = config.PROVIDERS.get(provider_name, {}).get("name", provider_name)
            footer = f"\n-# Code review powered by {provider_label}"
            header = f"## 🔍 Code Review — `{file.filename}`\n\n"

            full_response = header + response + footer
            for i in range(0, len(full_response), 1900):
                await interaction.followup.send(full_response[i: i + 1900])

        except UnicodeDecodeError:
            await interaction.followup.send("Could not read the file. Please make sure it's a text/code file.")
        except Exception as e:
            print(f"Error in /review-file: {e}")
            await interaction.followup.send("Something went wrong. Please try again.")


async def setup(bot: commands.Bot):
    await bot.add_cog(CodeReview(bot))