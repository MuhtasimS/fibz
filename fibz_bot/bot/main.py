from __future__ import annotations

import json
import os
import re

import discord
from discord import app_commands
from discord.ext import commands

from fibz_bot.config import settings
from fibz_bot.ingest.attachments import cleanup_temp, make_parts_from_attachments
from fibz_bot.ingest.files import parse_docx, parse_pptx, parse_text
from fibz_bot.ingest.images import parse_image
from fibz_bot.llm.agent import Agent
from fibz_bot.llm.router import ModelRouter
from fibz_bot.llm.revision import run_entity_revision_pass
from fibz_bot.memory.store import MemoryStore, MessageMeta
from fibz_bot.policy.injector import make_policy_text
from fibz_bot.policy.consent import classify_share_request, ensure_consent, configure_consent
from fibz_bot.storage.gcs import sign_url
from fibz_bot.utils.logging import get_logger
from fibz_bot.utils.metrics import metrics, record_command
from fibz_bot.utils.overflow import prepare_overflow_text

log = get_logger(__name__)

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.guilds = True
INTENTS.members = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)
router = ModelRouter()
memory = MemoryStore(router)
agent = Agent(router)
configure_consent(memory, router)

DEFAULT_CORE = "You are Fibz, a helpful, privacy-aware assistant for this server. Follow safety, consent, and server rules."


def get_core_user_server(guild_id: str | None, user_id: str | None):
    core = memory.get_persona_core() or DEFAULT_CORE
    user = memory.get_persona_user(str(user_id or "")) if user_id else ""
    server = memory.get_persona_server(str(guild_id or "")) if guild_id else ""
    return core, user, server


def is_owner(user: discord.abc.User) -> bool:
    try:
        return str(user.id) == str(settings.FIBZ_OWNER_ID)
    except Exception:
        return False


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        log.info("bot_ready", extra={"extra_fields": {"status": "synced", "user": str(bot.user)}})
    except Exception as e:
        log.error("sync_error", extra={"extra_fields": {"error": str(e)}})
    print(f"Logged in as {bot.user}")


@bot.tree.command(description="Show system status (counts & health).")
async def status(interaction: discord.Interaction):
    record_command("status")
    counts = memory.counts()
    snap = metrics.snapshot()
    await interaction.response.send_message(
        f"**Fibz status**\nMessages: {counts['messages']} | SelfContext: {counts['self_context']} | Entities: {counts['entities']} | Archives: {counts['archives']}\nUptime: {snap['uptime_seconds']}s",
        ephemeral=True,
    )


@bot.tree.command(description="Admin metrics snapshot (counters & uptime).")
async def metrics_cmd(interaction: discord.Interaction):
    record_command("metrics")
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only.", ephemeral=True)
    snap = metrics.snapshot()
    content = "```json\n" + json.dumps(snap, indent=2) + "\n```"
    await interaction.response.send_message(content, ephemeral=True)


@bot.tree.command(
    description="Set your personal persona/instructions (appends after core, before server)."
)
@app_commands.describe(text="Your instruction text")
async def persona_set(interaction: discord.Interaction, text: str):
    record_command("persona_set")
    memory.set_persona_user(str(interaction.user.id), text)
    await interaction.response.send_message("Your persona has been saved ✅", ephemeral=True)


@bot.tree.command(description="Set server persona (admin only).")
@app_commands.describe(text="Server instruction text")
async def persona_server(interaction: discord.Interaction, text: str):
    record_command("persona_server")
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only.", ephemeral=True)
    memory.set_persona_server(str(interaction.guild_id), text)
    await interaction.response.send_message("Server persona updated ✅", ephemeral=True)


@bot.tree.command(description="Set core persona (owner only).")
@app_commands.describe(text="Core instruction text (highest precedence)")
async def persona_core(interaction: discord.Interaction, text: str):
    record_command("persona_core")
    if not is_owner(interaction.user):
        return await interaction.response.send_message("Owner only.", ephemeral=True)
    memory.set_persona_core(text)
    await interaction.response.send_message("Core persona updated ✅", ephemeral=True)


@bot.tree.command(description="Grant or revoke cross-channel sharing (server-level).")
@app_commands.describe(
    enabled="True to allow cross-channel sharing of channel content, False to restrict to same channel"
)
async def crosschannel(interaction: discord.Interaction, enabled: bool):
    record_command("crosschannel")
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only.", ephemeral=True)
    memory.set_cross_channel(str(interaction.guild_id), enabled)
    await interaction.response.send_message(
        f"Cross-channel sharing set to **{enabled}**", ephemeral=True
    )


@bot.tree.command(description="Rate an answer (admin only).")
@app_commands.describe(
    message_link="Link to the message being rated", vote="up or down", note="Optional note"
)
async def rate_answer(
    interaction: discord.Interaction, message_link: str, vote: str, note: str | None = None
):
    record_command("rate_answer")
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only.", ephemeral=True)
    m = re.match(r"https?://discord.com/channels/\d+/(\d+)/(\d+)", message_link)
    if not m:
        return await interaction.response.send_message("Invalid message link.", ephemeral=True)
    channel_id, message_id = m.groups()
    memory.set_rating(str(interaction.guild_id), message_id, up=(vote.lower() == "up"), note=note)
    await interaction.response.send_message("Rating stored ✅", ephemeral=True)


# ---- privacy_status ----
@bot.tree.command(description="View and manage your stored consents (ephemeral).")
@app_commands.describe(page="Page number (default 1)")
async def privacy_status(interaction: discord.Interaction, page: int = 1):
    record_command("privacy_status")
    data = memory.list_consents_for_user(str(interaction.user.id), page=page, page_size=10)
    if not data["items"]:
        return await interaction.response.send_message(
            "No consents stored for you.", ephemeral=True
        )
    lines = [f"Total: {data['total']} — Page {page}"]
    for item in data["items"]:
        meta = item["meta"]
        lines.append(
            f"- `{item['id']}` scope={meta.get('scope')} target={meta.get('target')} granted={meta.get('granted')}"
        )
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


# ---- memory_find ----
@bot.tree.command(description="Search memory (ephemeral).")
@app_commands.describe(query="Your search query", k="Number of results (default 6)")
async def memory_find(interaction: discord.Interaction, query: str, k: int = 6):
    record_command("memory_find")
    res = memory.retrieve(query, k=k, where={"channel_id": str(interaction.channel_id)})
    if not res.get("ids"):
        return await interaction.response.send_message("No matches found.", ephemeral=True)
    out = []
    for i, (doc, meta, score) in enumerate(
        zip(res["documents"], res["metadatas"], res["scores"]), start=1
    ):
        out.append(
            f"**{i}.** score={score:.3f} — tags={meta.get('tags', [])}\n`{(doc[:250] + '…') if len(doc)>250 else doc}`"
        )
    await interaction.response.send_message("\n\n".join(out), ephemeral=True)


# ---- memory_purge ----
@bot.tree.command(description="Purge memory items by simple filter (admin only).")
@app_commands.describe(
    filter='JSON where filter, e.g. \'{"channel_id":"123"}\'',
    confirm="Set true to actually delete",
)
async def memory_purge(interaction: discord.Interaction, filter: str, confirm: bool = False):
    record_command("memory_purge")
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only.", ephemeral=True)
    try:
        where = json.loads(filter or "{}")
        if not isinstance(where, dict):
            raise ValueError("Filter must be a JSON object")
    except Exception as e:
        return await interaction.response.send_message(f"Invalid filter JSON: {e}", ephemeral=True)

    preview = memory.list_messages(where=where, limit=50)
    count_preview = len(preview.get("items", []))
    if not confirm:
        return await interaction.response.send_message(
            f"Dry run: would delete up to {count_preview} items (showing {count_preview} preview). Set confirm=true to delete.",
            ephemeral=True,
        )

    deleted = memory.delete_messages(where=where)
    await interaction.response.send_message(f"Deleted {deleted} items.", ephemeral=True)


# ---- helper: extract from local files (PDF/images/etc.) ----
def extract_from_local(
    path: str, filename_hint: str | None = None, page_whitelist: set[int] | None = None
) -> list[str]:
    low = path.lower()
    label_name = filename_hint or os.path.basename(path)
    try:
        if low.endswith(".pdf"):
            from fibz_bot.ingest.files import parse_pdf

            chunks = parse_pdf(path, pages=page_whitelist)
        elif low.endswith(".docx"):
            chunks = parse_docx(path)
        elif low.endswith(".pptx"):
            chunks = parse_pptx(path)
        elif any(low.endswith(ext) for ext in [".txt", ".md", ".log", ".csv"]):
            chunks = parse_text(path)
        elif any(low.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]):
            chunks = parse_image(path)
        else:
            return []
        context_lines = []
        for text, meta in chunks:
            label = filename_hint or meta.get("filename", "file")
            if "page" in meta:
                label += f" p.{meta['page']}"
            if "slide" in meta:
                label += f" slide {meta['slide']}"
            context_lines.append(f"[{label}] {text[:1200]}")
        return context_lines[:20]
    except Exception:
        return []


def parse_page_hints(hints: str) -> dict[str, set[int]]:
    mapping: dict[str, set[int]] = {}
    for part in hints.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        name, ranges = part.split(":", 1)
        name = name.strip()
        pages: set[int] = set()
        for r in ranges.split(","):
            r = r.strip()
            if not r:
                continue
            if "-" in r:
                a, b = r.split("-", 1)
                try:
                    a, b = int(a), int(b)
                    if a <= b:
                        pages.update(range(a, b + 1))
                except:
                    pass
            else:
                try:
                    pages.add(int(r))
                except:
                    pass
        if pages:
            mapping[name] = pages
    return mapping


# ---- Ask with extraction and citations ----
@bot.tree.command(description="Ask Fibz (retrieval + tools + media + PDF/image extraction).")
@app_commands.describe(
    question="Your question",
    page_hints="Optional: 'file.pdf:1-3,5; other.pdf:2' to limit PDF pages",
)
async def ask(interaction: discord.Interaction, question: str, page_hints: str | None = None):
    record_command("ask")
    await interaction.response.defer(ephemeral=False)

    core, user, server = get_core_user_server(str(interaction.guild_id), str(interaction.user.id))
    policy_text = make_policy_text(memory, str(interaction.guild_id), str(interaction.channel_id))

    where = {"channel_id": str(interaction.channel_id)}
    ctx = memory.retrieve(question, k=6, where=where)
    docs = ctx.get("documents", []) or []
    entity_docs: list[str] = []
    if settings.ENTITY_REVISION_ENABLED:
        bot_entity = memory.get_entity("bot:self")
        if bot_entity:
            meta = bot_entity.get("metadata", {}) or {}
            display = meta.get("display_name") or "Fibz"
            entity_docs.append(f"### ENTITY: {display}\n{bot_entity.get('document', '')}")

    media_parts, paths, metas = ([], [], [])
    extracted = []
    labels = []
    pages_map = parse_page_hints(page_hints) if page_hints else {}

    if interaction.attachments:
        media_parts, paths, metas = make_parts_from_attachments(interaction.attachments)
        for p, meta in zip(paths, metas):
            fname = meta.get("filename", "file")
            pset = pages_map.get(fname)
            ext_chunks = extract_from_local(p, filename_hint=fname, page_whitelist=pset)
            extracted.extend(ext_chunks)
            for line in ext_chunks:
                tag = line.split("]")[0].lstrip("[").strip()
                labels.append(tag)

    docs = entity_docs + docs + extracted
    answer = agent.run(
        question=question,
        core=core,
        user=user,
        server=server,
        policy_text=policy_text,
        context_docs=docs,
        media_parts=media_parts,
        needs_reasoning=True,
        request_context={
            "guild_id": str(interaction.guild_id),
            "channel_id": str(interaction.channel_id),
            "user_id": str(interaction.user.id),
            "memory": memory,
        },
    )
    answer = answer or ""

    cleanup_temp(paths)

    memory.upsert_message(
        message_id=f"{interaction.id}-q",
        content=question,
        meta=MessageMeta(
            message_id=f"{interaction.id}-q",
            guild_id=str(interaction.guild_id),
            channel_id=str(interaction.channel_id),
            user_id=str(interaction.user.id),
            role="user",
            persona="user",
            tags=["ask"],
        ),
    )
    memory.upsert_message(
        message_id=f"{interaction.id}-a",
        content=answer,
        meta=MessageMeta(
            message_id=f"{interaction.id}-a",
            guild_id=str(interaction.guild_id),
            channel_id=str(interaction.channel_id),
            user_id=str(bot.user.id if bot.user else 0),
            role="assistant",
            persona="core",
            tags=["answer"],
        ),
    )

    await run_entity_revision_pass(
        router,
        memory,
        author_id=str(interaction.user.id),
        author_display=interaction.user.display_name,
        guild_id=str(interaction.guild_id),
        channel_id=str(interaction.channel_id),
        message_text=question,
        answer_text=answer,
        is_owner=is_owner(interaction.user),
    )

    if labels:
        uniq = []
        seen = set()
        for tag in labels:
            if tag not in seen:
                uniq.append(tag)
                seen.add(tag)
        answer = (answer or "") + "\n\n**Sources**:\n" + "\n".join(f"- {t}" for t in uniq[:20])

    display, attachment_path = prepare_overflow_text(answer)
    if attachment_path:
        await interaction.followup.send(
            display,
            file=discord.File(str(attachment_path), filename=attachment_path.name),
        )
    else:
        await interaction.followup.send(display)


@bot.tree.command(description="Ask about a user with consent-aware checks.")
@app_commands.describe(user="Target user", question="Your question")
async def ask_about(interaction: discord.Interaction, user: discord.Member, question: str):
    record_command("ask_about")
    await interaction.response.defer(ephemeral=False)

    cross_enabled = memory.get_cross_channel(str(interaction.guild_id))
    classification = await classify_share_request(
        question,
        str(interaction.user.id),
        str(user.id),
        str(interaction.guild_id),
        str(interaction.channel_id),
        cross_enabled,
        router=router,
    )
    if classification == "share_block":
        return await interaction.followup.send(
            "I can't share that across channels or without explicit permission.",
            ephemeral=True,
        )

    if classification == "share_needs_consent":
        scope = f"guild:{interaction.guild_id}"
        target_key = f"ask_about:{interaction.channel_id}:{user.id}"
        granted = await ensure_consent(
            str(user.id),
            scope,
            target_key,
            interaction,
            requester_name=interaction.user.display_name,
        )
        if not granted:
            return await interaction.followup.send(
                "I don't have consent to share that yet.",
                ephemeral=True,
            )

    core, user_instr, server = get_core_user_server(
        str(interaction.guild_id), str(interaction.user.id)
    )
    policy_text = make_policy_text(memory, str(interaction.guild_id), str(interaction.channel_id))

    entity_context: list[str] = []
    entity_doc = memory.get_entity(f"user:{user.id}") if settings.ENTITY_REVISION_ENABLED else None
    if entity_doc:
        meta = entity_doc.get("metadata", {}) or {}
        raw_channels = meta.get("channels", "")
        if isinstance(raw_channels, str):
            channels = {c for c in raw_channels.split(",") if c}
        else:
            channels = {str(c) for c in raw_channels}
        if cross_enabled or str(interaction.channel_id) in channels:
            display = meta.get("display_name") or user.display_name
            entity_context.append(f"### ENTITY: {display}\n{entity_doc.get('document', '')}")

    where = {"user_id": str(user.id)}
    if not cross_enabled:
        where["channel_id"] = str(interaction.channel_id)
    ctx = memory.retrieve(question, k=4, where=where)
    docs = entity_context + (ctx.get("documents", []) or [])

    answer = agent.run(
        question=question,
        core=core,
        user=user_instr,
        server=server,
        policy_text=policy_text,
        context_docs=docs,
        needs_reasoning=True,
        request_context={
            "guild_id": str(interaction.guild_id),
            "channel_id": str(interaction.channel_id),
            "user_id": str(interaction.user.id),
            "memory": memory,
        },
    )
    answer = answer or ""

    memory.upsert_message(
        message_id=f"{interaction.id}-qa",
        content=question,
        meta=MessageMeta(
            message_id=f"{interaction.id}-qa",
            guild_id=str(interaction.guild_id),
            channel_id=str(interaction.channel_id),
            user_id=str(interaction.user.id),
            role="user",
            persona="user",
            tags=["ask_about"],
        ),
    )
    memory.upsert_message(
        message_id=f"{interaction.id}-qa-answer",
        content=answer,
        meta=MessageMeta(
            message_id=f"{interaction.id}-qa-answer",
            guild_id=str(interaction.guild_id),
            channel_id=str(interaction.channel_id),
            user_id=str(bot.user.id if bot.user else 0),
            role="assistant",
            persona="core",
            tags=["answer", "ask_about"],
        ),
    )

    await run_entity_revision_pass(
        router,
        memory,
        author_id=str(interaction.user.id),
        author_display=interaction.user.display_name,
        guild_id=str(interaction.guild_id),
        channel_id=str(interaction.channel_id),
        message_text=question,
        answer_text=answer,
        is_owner=is_owner(interaction.user),
    )

    display, attachment_path = prepare_overflow_text(answer)
    if attachment_path:
        await interaction.followup.send(
            display,
            file=discord.File(str(attachment_path), filename=attachment_path.name),
        )
    else:
        await interaction.followup.send(display)


# ---- Summarize PDF ----
@bot.tree.command(
    description="Summarize an attached PDF, index it to memory, and produce a page-referenced outline."
)
async def summarize(interaction: discord.Interaction):
    record_command("summarize")
    await interaction.response.defer(ephemeral=False)
    if not interaction.attachments:
        return await interaction.followup.send(
            "Attach a **PDF** to this command and try again.", ephemeral=True
        )
    pdf = None
    for a in interaction.attachments:
        if a.filename.lower().endswith(".pdf"):
            pdf = a
            break
    if not pdf:
        return await interaction.followup.send("No PDF attachment found.", ephemeral=True)

    parts, paths, metas = make_parts_from_attachments([pdf])
    path = paths[0]
    meta = metas[0]
    fname = meta.get("filename", "document.pdf")

    from fibz_bot.ingest.files import parse_pdf as parsepdf

    texts = parsepdf(path)
    for idx, (text, m) in enumerate(texts, start=1):
        memory.upsert_message(
            message_id=f"doc:{interaction.id}:{idx}",
            content=text,
            meta=MessageMeta(
                message_id=f"doc:{interaction.id}:{idx}",
                guild_id=str(interaction.guild_id),
                channel_id=str(interaction.channel_id),
                user_id=str(interaction.user.id),
                role="system",
                modality="file",
                tags=["doc", "pdf", fname],
            ),
        )
    context_lines = []
    for text, m in texts[:60]:
        label = fname
        if "page" in m:
            label += f" p.{m['page']}"
        context_lines.append(f"[{label}] {text[:1200]}")

    core, user, server = get_core_user_server(str(interaction.guild_id), str(interaction.user.id))
    policy_text = make_policy_text(memory, str(interaction.guild_id), str(interaction.channel_id))
    question = f"Create a hierarchical outline of **{fname}**. Include page tags like [file p.N] inline for claims, and a short abstract up top."

    answer = agent.run(
        question=question,
        core=core,
        user=user,
        server=server,
        policy_text=policy_text,
        context_docs=context_lines,
        needs_reasoning=True,
        request_context={
            "guild_id": str(interaction.guild_id),
            "channel_id": str(interaction.channel_id),
            "user_id": str(interaction.user.id),
            "memory": memory,
        },
    )
    answer = answer or ""

    labels = []
    for line in context_lines:
        tag = line.split("]")[0].lstrip("[").strip()
        labels.append(tag)
    if labels:
        uniq = []
        seen = set()
        for tag in labels:
            if tag not in seen:
                uniq.append(tag)
                seen.add(tag)
        answer = (
            (answer or "") + "\n\n**Indexed & Sources**:\n" + "\n".join(f"- {t}" for t in uniq[:20])
        )

    cleanup_temp(paths)

    display, attachment_path = prepare_overflow_text(answer)
    if attachment_path:
        await interaction.followup.send(
            display,
            file=discord.File(str(attachment_path), filename=attachment_path.name),
        )
    else:
        await interaction.followup.send(display)


@bot.tree.command(description="Create a signed URL for a GCS object path (admin only).")
@app_commands.describe(path_in_bucket="e.g., 'discord/filename.pdf'")
async def sign(interaction: discord.Interaction, path_in_bucket: str):
    record_command("sign")
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only.", ephemeral=True)
    if not settings.GCS_BUCKET:
        return await interaction.response.send_message(
            "GCS_BUCKET is not configured.", ephemeral=True
        )
    url = sign_url(path_in_bucket)
    if not url:
        return await interaction.response.send_message(
            "Failed to sign URL (missing perms or path).", ephemeral=True
        )
    await interaction.response.send_message(
        f"Signed URL (expires in {settings.GCS_SIGN_URL_EXPIRY_SECONDS}s):\n{url}", ephemeral=True
    )


@bot.tree.command(description="Owner-only: inspect an entity summary (ephemeral).")
@app_commands.describe(id="Entity identifier, e.g. bot:self or user:1234567890")
async def entity_debug(interaction: discord.Interaction, id: str):
    record_command("entity_debug")
    if not is_owner(interaction.user):
        return await interaction.response.send_message("Owner only.", ephemeral=True)
    doc = memory.get_entity(id)
    if not doc:
        return await interaction.response.send_message("Entity not found.", ephemeral=True)
    meta_json = json.dumps(doc.get("metadata", {}) or {}, indent=2)
    content = doc.get("document", "")
    await interaction.response.send_message(
        f"**Entity {id}**\n```json\n{meta_json}\n```\n```text\n{content}\n```",
        ephemeral=True,
    )


@bot.tree.command(description="Admin: refresh a user entity from recent channel content.")
@app_commands.describe(user="User whose public facts should be refreshed")
async def entity_refresh(interaction: discord.Interaction, user: discord.Member):
    record_command("entity_refresh")
    if not (interaction.user.guild_permissions.administrator or is_owner(interaction.user)):
        return await interaction.response.send_message("Admin only.", ephemeral=True)
    cross_enabled = memory.get_cross_channel(str(interaction.guild_id))
    where = {"user_id": str(user.id)}
    if not cross_enabled:
        where["channel_id"] = str(interaction.channel_id)
    ctx = memory.retrieve(user.display_name or user.name, k=4, where=where)
    docs = [d for d in ctx.get("documents", []) if d]
    if not docs:
        return await interaction.response.send_message(
            "No recent same-channel notes to refresh.", ephemeral=True
        )
    combined = "\n".join(docs[:3])
    await run_entity_revision_pass(
        router,
        memory,
        author_id=str(user.id),
        author_display=user.display_name,
        guild_id=str(interaction.guild_id),
        channel_id=str(interaction.channel_id),
        message_text=combined,
        answer_text=None,
        is_owner=is_owner(user),
    )
    await interaction.response.send_message(
        "Entity refresh triggered from recent public notes.", ephemeral=True
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if bot.user and (
        bot.user.mentioned_in(message) or message.content.strip().lower().startswith("!fibz")
    ):
        record_command("mention")
        query = message.content.replace("!fibz", "").strip()

        core, user_instr, server = get_core_user_server(
            str(message.guild.id if message.guild else ""), str(message.author.id)
        )
        policy_text = make_policy_text(
            memory, str(message.guild.id if message.guild else ""), str(message.channel.id)
        )

        where = {"channel_id": str(message.channel.id)}
        ctx = memory.retrieve(query, k=6, where=where)
        docs = ctx.get("documents", []) or []
        entity_docs: list[str] = []
        if settings.ENTITY_REVISION_ENABLED:
            bot_entity = memory.get_entity("bot:self")
            if bot_entity:
                meta = bot_entity.get("metadata", {}) or {}
                display = meta.get("display_name") or "Fibz"
                entity_docs.append(f"### ENTITY: {display}\n{bot_entity.get('document', '')}")

        media_parts, paths, metas = ([], [], [])
        if message.attachments:
            media_parts, paths, metas = make_parts_from_attachments(message.attachments)
            # optional extraction
            extracted = []
            for p, meta in zip(paths, metas):
                extracted.extend(extract_from_local(p, filename_hint=meta.get("filename")))
            docs = entity_docs + docs + extracted
        else:
            docs = entity_docs + docs

        answer = agent.run(
            question=query,
            core=core,
            user=user_instr,
            server=server,
            policy_text=policy_text,
            context_docs=docs,
            media_parts=media_parts,
            needs_reasoning=False,
            request_context={
                "guild_id": str(message.guild.id if message.guild else ""),
                "channel_id": str(message.channel.id),
                "user_id": str(message.author.id),
                "memory": memory,
            },
        )
        answer = answer or ""

        cleanup_temp(paths)

        display, attachment_path = prepare_overflow_text(answer)
        if attachment_path:
            await message.channel.send(
                display,
                file=discord.File(str(attachment_path), filename=attachment_path.name),
            )
        else:
            await message.channel.send(display)

        await run_entity_revision_pass(
            router,
            memory,
            author_id=str(message.author.id),
            author_display=message.author.display_name,
            guild_id=str(message.guild.id) if message.guild else None,
            channel_id=str(message.channel.id),
            message_text=query,
            answer_text=answer,
            is_owner=is_owner(message.author),
        )


if __name__ == "__main__":
    bot.run(settings.DISCORD_BOT_TOKEN)
