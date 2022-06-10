import logging
import sec

import disnake
from disnake.ext import commands

logging.basicConfig(format='%(asctime)s %(levelname)s [%(name)s]: %(message)s')
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)

intents = disnake.Intents(guilds=True, messages=True)
activity = disnake.Activity(name="GameDevs 🎮", type=disnake.ActivityType.watching)
# Use sync_commands_debug if you have trouble syncing commands
# bot = commands.InteractionBot(intents=intents, sync_commands_debug=True, test_guilds=[DEBUG_GUILD_ID])
bot = commands.InteractionBot(intents=intents, activity=activity)


@bot.event
async def on_ready():
    logger.info("Bot successfully spawned.")

bot.load_extension("cogs.guilds")
bot.load_extension("cogs.settings")
bot.load_extension("cogs.tracker")

token = sec.load('bot_token')
bot.run(token)
