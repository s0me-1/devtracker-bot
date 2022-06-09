import os
import logging

import disnake
from disnake.ext import commands
from dotenv import load_dotenv
#aaa
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
DEBUG_GUILD_ID = int(os.environ['DEBUG_GUILD_ID'])

logging.basicConfig(format='%(asctime)s %(levelname)s [%(name)s]: %(message)s')
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)

intents = disnake.Intents(guilds=True, messages=True)
bot = commands.InteractionBot(intents=intents, test_guilds=[DEBUG_GUILD_ID, 984016998084247582], sync_commands_debug=True)


@bot.event
async def on_ready():
    logger.info("Bot successfully spawned.")

bot.load_extension("cogs.guilds")
bot.load_extension("cogs.settings")
bot.load_extension("cogs.tracker")

bot.run(TOKEN)
