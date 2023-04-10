import logging
import argparse

import sec
import disnake
from disnake.ext import commands
from cogs.utils.database import ORM

# Logger Setup
parser = argparse.ArgumentParser()
parser.add_argument(
    "--log-level",
    default="info",
    help=(
        "Provide logging level. "
        "Example --log debug', default='info'"
    ),
)

options = parser.parse_args()
levels = {
    'critical': logging.CRITICAL,
    'error': logging.ERROR,
    'warn': logging.WARNING,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG
}
level = levels.get(options.log_level.lower())
if level is None:
    raise ValueError(
        f"log level given: {options.log_level}"
        f" -- must be one of: {' | '.join(levels.keys())}")

logging.basicConfig(level=level, format='%(asctime)s %(levelname)s [%(name)s]: %(message)s')
logger = logging.getLogger('bot')

class DevTracker(commands.InteractionBot):

    __version__ = "1.7.1"

    def __init__(self):


        intents = disnake.Intents(guilds=True, messages=True)
        activity = disnake.Activity(name="GameDevs 🎮", type=disnake.ActivityType.watching)

        # Use sync_commands_debug if you have trouble syncing commands
        if logger.getEffectiveLevel() == logging.DEBUG:
            super().__init__(intents=intents, sync_commands_debug=True, test_guilds=[int(sec.load('debug_guild_id'))])
        else:
            super().__init__(activity=activity, intents=intents)

        self.load_extension("cogs.guilds")
        self.load_extension("cogs.settings")
        self.load_extension("cogs.admin")
        self.load_extension("cogs.tracker")

DT = DevTracker()

init_db_tack = DT.loop.create_task(ORM().initialize())
DT.loop.run_until_complete(init_db_tack)

token = sec.load('bot_token')
if logger.getEffectiveLevel() == logging.DEBUG:
    token = sec.load('debug_bot_token')

DT.run(token)
