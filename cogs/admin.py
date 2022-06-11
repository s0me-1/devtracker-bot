import logging

import disnake
from disnake.ext import commands

from cogs.utils import autocompleters as ac

from cogs.utils import database as db
from cogs.utils import api
ORM = db.ORM()
API = api.API()

logger = logging.getLogger('bot.Admin')


class Admin(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info('Loaded.')

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------

    @commands.slash_command(name="dt-stats", description="See DevTracker statistics.", guild_ids=[984016998084247582, 687999396612407341])
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def statistics(self, inter : disnake.ApplicationCommandInteraction):
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : Statistiques request')

        await inter.response.defer()

        emb = disnake.Embed(
            description="- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -",
            color=7506394
        )

        api_status_code, latency = API.get_status()
        api_latency = f"{round(latency * 1000)}ms"
        emoji = "✅" if api_status_code == 200 else "❌"
        api_status = f"API Status - {emoji} ({api_status_code})"

        guild_ids = ORM.get_all_guilds()

        total_members = 0
        for guild_id in guild_ids:
            guild = self.bot.get_guild(guild_id)
            total_members += guild.member_count

        follows = ORM.get_all_follows()

        emb.set_author(name="📊 Current Statistics")
        emb.add_field(name='🎮 Total Follows', value=f"{len(follows)}", inline=True)
        emb.add_field(name='🌐 Total Servers', value=f"{len(guild_ids)}", inline=True)
        emb.add_field(name='👥 Total Members', value=f"{total_members}\n" +  u'\u200B', inline=True)
        emb.add_field(name='Bot Latency', value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        emb.add_field(name=api_status, value=api_latency, inline=True)

        await inter.edit_original_message(embed=emb)


def setup(bot: commands.Bot):
    bot.add_cog(Admin(bot))
