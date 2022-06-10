import logging

import sec
import disnake
from disnake.ext import commands

TOKEN = sec.load('bot_token')

logging.basicConfig(format='%(asctime)s %(levelname)s [%(name)s]: %(message)s')
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)

class DevTracker(commands.InteractionBot):

    def __init__(self):

        intents = disnake.Intents(guilds=True, messages=True)
        activity = disnake.Activity(name="GameDevs 🎮", type=disnake.ActivityType.watching)

        # Use sync_commands_debug if you have trouble syncing commands
        # super().__init__(intents=intents, sync_commands_debug=True, test_guilds=[DEBUG_GUILD_ID])
        super().__init__(activity=activity, intents=intents)

        self.load_extension("cogs.guilds")
        self.load_extension("cogs.settings")
        self.load_extension("cogs.tracker")

DT = DevTracker()
token = sec.load('bot_token')
DT.run(token)
