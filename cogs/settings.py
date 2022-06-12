import logging

import disnake
from disnake.ext import commands

from cogs.utils import autocompleters as ac

from cogs.utils import database as db
from cogs.utils import api
ORM = db.ORM()
API = api.API()

logger = logging.getLogger('bot.Settings')


class Settings(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info('Loaded.')

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------

    @commands.slash_command(name="dt-status", description="See the current configuration of this server.")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def status(self, inter : disnake.ApplicationCommandInteraction):
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : Status request')

        await inter.response.defer()

        default_channel_id = ORM.get_main_channel(inter.guild_id)

        chname = f'<#{default_channel_id}>' if default_channel_id else 'Not set'
        api_md = "[DeveloperTracker.com](https://developertracker.com/)\n" +  u'\u200B'
        fw_status = ORM.get_follow_status(inter.guild_id)
        ignored_accounts = ORM.get_ignored_accounts(inter.guild_id)
        fw_tabs = self._generate_fw_table(fw_status)
        acc_tabs = self._generate_ignored_acc_table(ignored_accounts)
        api_status_code, latency = API.get_status()
        emoji = "✅" if api_status_code == 200 else "❌"
        api_status = f"API Status - {emoji} ({api_status_code})"

        description = "Check the [Github](https://github.com/s0me-1/devtracker-bot#commands) page " \
            "if you need any help.\n" +  u'\u200B'

        emb = disnake.Embed(
            description=description,
            color=7506394
        )

        emb.set_author(name="⚙️ Current config")
        emb.add_field(name='Default Channel', value=chname, inline=True)
        emb.add_field(name=api_status, value=api_md, inline=True)
        emb.add_field(name='📡 Followed Games', value=fw_tabs[0], inline=False)

        embeds = []
        embeds.append(emb)
        for fw_tab in fw_tabs[1:]:
            emb = disnake.Embed(
                color=7506394
            )
            emb.add_field(name='📡 Followed Games', value=fw_tab, inline=False)
            embeds.append(emb)

        for acc_tab in acc_tabs:
            emb = disnake.Embed(
                color=7506394
            )
            emb.add_field(name='🔇 Ignored accounts', value=acc_tab, inline=False)
            embeds.append(emb)

        # Max 10 embeds can be sent at once
        await inter.edit_original_message(embeds=embeds[0:9])

    # ---------------------------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------------------------
    def _generate_fw_table(self, fw_status):

        if not fw_status:
            return ['None\n']

        fw_tabs = []
        fw_tab = ''

        max_fw = max(fw_status,key=lambda fw: len(fw[1]))
        lg = len(max_fw[1])
        for gid, gname, game_ch_id, last_post_id in fw_status:
            fw_line = ''
            offset = lg - len(gname)
            fw_line += f"`{gname}"
            fw_line += " "*offset
            if game_ch_id:
                fw_line += f"`  |  <#{game_ch_id}> - [{last_post_id}](https://developertracker.com/{gid}/?post={last_post_id})\n"
            else:
                 fw_line += f"` |  \n"


            # Max Field size is 1024 characters
            if len(fw_line) + len(fw_tab) > 1024:
                fw_tabs.append(fw_tab)
                fw_tab = ''

            fw_tab += fw_line

        fw_tabs.append(fw_tab)

        return fw_tabs

    def _generate_ignored_acc_table(self, ignored_accounts):

        if not ignored_accounts:
            return ['None\n']

        acc_tabs = []
        acc_tab = ''
        for acc_id in ignored_accounts:
            acc_line = f' - `{acc_id}`\n'

            if len(acc_line) + len(acc_tab) > 1024:
                acc_tabs.append(acc_tab)
                acc_tab = ''

            acc_tab += acc_line

        return acc_tabs


def setup(bot: commands.Bot):
    bot.add_cog(Settings(bot))
