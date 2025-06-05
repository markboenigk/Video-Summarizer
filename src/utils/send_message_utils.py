from telegram import Update


async def send_company_summary(update: Update, data: dict) -> None:
    """
    Send a company summary message to a Telegram user.

    Args:
        update (Update): Telegram update containing message context.
        data (dict): Dictionary containing 'summaries', 'tags', and 'companies'.
    """
    summaries = data.get("summaries", [])
    tags = data.get("tags", [])
    companies = data.get("companies", [])

    lines = ["*📢 Company Summaries*\n"]

    for i, company in enumerate(summaries, start=1):
        lines.append(f"*{i}. {company['company_name']}*")
        lines.append(f"🏢 Location: {company.get('location', 'Not specified')}")
        lines.append(f"🏭 Industry: {company.get('industry', 'Not specified')}")
        lines.append(f"💰 Funding: {company.get('funding', 'Not specified')}")

        # Escape Markdown special characters in notes
        notes = company.get('notes', '')
        notes = (
            notes.replace('_', '\\_')
                 .replace('*', '\\*')
                 .replace('[', '\\[')
                 .replace(']', '\\]')
        )
        lines.append(f"📝 Notes: {notes}\n")

    if tags:
        tags_str = ", ".join(tags)
        lines.append(f"*🏷️ Tags:* {tags_str}")

    if companies:
        companies_str = ", ".join(companies)
        lines.append(f"\n*Companies Mentioned:* {companies_str}")

    message_text = "\n".join(lines)
    await update.message.reply_text(message_text, parse_mode="Markdown")


async def send_general_summary(update: Update, data: dict) -> None:
    """
    Send a general summary message to a Telegram user.

    Args:
        update (Update): Telegram update containing message context.
        data (dict): Dictionary containing 'title', 'summary', and optional 'tags'.
    """
    title = data.get("title", "No Title")
    summary = data.get("summary", "No Summary")
    tags = data.get("tags", [])

    lines = ["*🎬 Summary Created*\n"]
    lines.append(f"*Title:* _{title}_\n")
    lines.append(f"*Summary:*\n{summary}\n")

    if tags:
        tags_str = " | ".join(f"`{tag}`" for tag in tags)
        lines.append(f"*🏷️ Tags:* {tags_str}")
    else:
        lines.append("*🏷️ Tags:* None")

    message_text = "\n".join(lines)
    await update.message.reply_text(message_text, parse_mode="Markdown")


async def send_technology_summary(update: Update, data: dict) -> None:
    """
    Send a technology summary message to a Telegram user.

    Parses structured summary sections and adds formatting and emojis.

    Args:
        update (Update): Telegram update containing message context.
        data (dict): Dictionary containing 'title', 'summary', and optional 'tags'.
    """
    title = data.get("title", "No Title")
    summary_text = data.get("summary", "")
    tags = data.get("tags", [])

    sections = {}
    for line in summary_text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            sections[key.strip()] = value.strip()

    lines = ["*🎬 Summary Created*\n"]
    lines.append(f"*Title:* _{title}_\n")

    if "Topic" in sections:
        lines.append(f"📌 *Topic:* {sections['Topic']}")
    if "Tech" in sections:
        lines.append(f"⚙️ *Tech:* {sections['Tech']}")
    if "Insight" in sections:
        lines.append(f"💡 *Insight:* {sections['Insight']}")
    if "Takeaway" in sections:
        lines.append(f"🎯 *Takeaway:* {sections['Takeaway']}")

    if tags:
        tags_str = " | ".join(f"`{tag}`" for tag in tags)
        lines.append(f"\n🏷️ *Tags:* {tags_str}")
    else:
        lines.append("\n🏷️ *Tags:* None")

    message_text = "\n".join(lines)
    await update.message.reply_text(message_text, parse_mode="Markdown")
