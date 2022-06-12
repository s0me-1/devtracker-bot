import logging

import disnake
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

        msg = "Use the command below **in your Server** to follow your first game 🎮\n"
        msg += "```\n"
        msg += "/dt-set-channel game\n"
        msg += "```\n"
        msg += "You can find some explanations for all available commands on <https://github.com/s0me-1/devtracker-bot#commands>."

        self.help_message = msg

    # ---------------------------------------------------------------------------------
    # EVENT LISTENERS
    # ---------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if isinstance(message.channel, disnake.DMChannel) and message.author != self.bot.user:

            await message.reply(self.help_message)


    @commands.Cog.listener()
    async def on_guild_join(self, guild : disnake.Guild):

        dt_channel = self.bot.get_channel(985250371981172757)
        await dt_channel.send(f'`{guild.name} [{guild.id}]` joined. (Approx `{guild.member_count}` members)')

        ORM.add_guild(guild.id)
        logger.info(f'{guild.name} [{guild.id}] added to DB.')


        # We can see the owner only if we have the Members privileged intent
        if not guild.owner:
            return

        msg = "I'm now ready to track GameDevs for you !\n"
        msg += self.help_message

        try:
            await guild.owner.send(msg)
        except disnake.Forbidden:
            logger.warning(f'{guild.owner.name} has blocked his DMs.')


    @commands.Cog.listener()
    async def on_guild_remove(self, guild : disnake.Guild):

        dt_channel = self.bot.get_channel(985250371981172757)
        await dt_channel.send(f'`{guild.name} [{guild.id}]` removed. (Approx `{guild.member_count}` members)')

        ORM.rm_guild(guild.id)
        logger.info(f'{guild.name} [{guild.id}] removed from DB.')

    # ---------------------------------------------------------------------------------
    # SLASH COMMANDS
    # ---------------------------------------------------------------------------------

    @commands.slash_command(name="dt-invite", description="Invite DevTracker to your server.")
    async def invite(self, inter : disnake.ApplicationCommandInteraction):
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : Show invite link.')

        invite_btn = disnake.ui.Button(
            label="Invite Me !",
            url="https://discord.com/api/oauth2/authorize?client_id=982257201211138050&permissions=274877958144&scope=applications.commands%20bot",
            style=disnake.ButtonStyle.link,
        ),

        await inter.response.send_message(components=[invite_btn])

    @commands.slash_command(name="dt-help", description="Struggling getting started?")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def get_help_message(self, inter : disnake.ApplicationCommandInteraction):
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : Show help.')

        await inter.response.send_message(self.help_message)

def setup(bot: commands.Bot):
    bot.add_cog(Guilds(bot))
