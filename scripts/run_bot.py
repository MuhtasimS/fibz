from fibz_bot.bot.main import bot
from fibz_bot.config import settings

if __name__ == "__main__":
    bot.run(settings.DISCORD_BOT_TOKEN)
