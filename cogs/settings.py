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

        default_channel_id = await ORM.get_main_channel(inter.guild_id)

        chname = 'Not set'

        if default_channel_id:
            error_msg = ''
            bot_member = inter.guild.get_member(self.bot.user.id)
            channel = inter.guild.get_channel(default_channel_id)
            perms = channel.permissions_for(bot_member)
            if not perms.view_channel:
                error_msg = "**[ERROR]** Missing `View Channel` Permission"
            if not perms.send_messages:
                error_msg = "**[ERROR]** Missing `Send Message` Channel Permission"
            chname = f'<#{default_channel_id}> {error_msg}' if error_msg else f'<#{default_channel_id}>'

        api_md = "[DeveloperTracker.com](https://developertracker.com/)\n" +  u'\u200B'
        fw_status = await ORM.get_follow_status(inter.guild_id)
        ignored_accounts = await ORM.get_ignored_accounts_per_game(inter.guild_id)
        ignored_services = await ORM.get_ignored_services_per_game(inter.guild_id)
        fw_tabs = self._generate_fw_table(fw_status, inter.guild)

        local_game_data = await ORM.get_local_games()
        games = {}
        for g in local_game_data:
            games.update({
                g[0]: g[1]
            })

        acc_tabs = self._generate_ignored_table(games, ignored_accounts)
        serv_tabs = self._generate_ignored_table(games, ignored_services)
        api_status_code, latency = await API.get_status()
        emoji = "✅" if api_status_code == 200 else "❌"
        api_status = f"API Status - {emoji} ({api_status_code})"
        version = f'v{self.bot.__version__}'

        description = "- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n" \
            "Need any help ? You can find some here :\n" \
            " - DevTracker Official [Discord Server](https://discord.gg/QN9uveFYXX).\n" \
            " - DevTracker [Github](https://github.com/s0me-1/devtracker-bot#commands) page." +  u'\u200B'

        emb = disnake.Embed(
            description=description,
            color=7506394
        )

        emb.set_author(name="⚙️ Current config")
        emb.add_field(name='Default Channel', value=chname, inline=True)
        emb.add_field(name=api_status, value=api_md, inline=True)
        emb.add_field(name='Bot Version', value=version, inline=True)
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

        for serv_tab in serv_tabs:
            emb = disnake.Embed(
                color=7506394
            )
            emb.add_field(name='🔇 Ignored services', value=serv_tab, inline=False)
            embeds.append(emb)

        # Max 10 embeds can be sent at once
        await inter.edit_original_message(embeds=embeds[0:9])

    # ---------------------------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------------------------
    def _generate_fw_table(self, fw_status, guild: disnake.Guild):

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

                error_msg = ''
                bot_member = guild.get_member(self.bot.user.id)
                channel = guild.get_channel(game_ch_id)
                perms = channel.permissions_for(bot_member)

                if not perms.view_channel:
                    error_msg = "**[ERROR]** Missing `View Channel` Permission"
                if not perms.send_messages:
                    error_msg = "**[ERROR]** Missing `Send Message` Channel Permission"

                if not error_msg:
                    fw_line += f"`  |  <#{game_ch_id}> - [{last_post_id}](https://developertracker.com/{gid}/?post={last_post_id})\n"
                else:
                    fw_line += f"`  |  <#{game_ch_id}> - {error_msg}\n"
            else:
                 fw_line += f"` |  \n"


            # Max Field size is 1024 characters
            if len(fw_line) + len(fw_tab) > 1024:
                fw_tabs.append(fw_tab)
                fw_tab = ''

            fw_tab += fw_line

        fw_tabs.append(fw_tab)

        return fw_tabs

    def _generate_ignored_table(self, games, ignored_data):

        if not ignored_data:
            return ['None\n']

        ign_tabs = []
        ign_tab = ''
        for gid, igns in ignored_data.items():
            ign_tab += f'\n**{games[gid]}**\n'
            for ign in igns:
                ign_line = f' - `{ign}`\n'

                if len(ign_line) + len(ign_tab) > 1024:
                    ign_tabs.append(ign_tab)
                    ign_tab = ''

                ign_tab += ign_line

        ign_tabs.append(ign_tab)

        return ign_tabs


def setup(bot: commands.Bot):
    bot.add_cog(Settings(bot))
