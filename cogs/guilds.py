import logging

from disnake.ext import commands

from cogs.utils import database as db
ORM = db.ORM()

logger = logging.getLogger('bot.Guilds')


class Guilds(commands.Cog):
    """ Manage when the bot is added/removed from a guild.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info('Loaded.')

    # ---------------------------------------------------------------------------------
    # EVENT LISTENERS
    # ---------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        logger.info(f'{guild.name} [{guild.id}] added to DB.')
        ORM.add_guild(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        logger.info(f'{guild.name} [{guild.id}] removed from DB.')
        ORM.rm_guild(guild.id)


def setup(bot: commands.Bot):
    bot.add_cog(Guilds(bot))
