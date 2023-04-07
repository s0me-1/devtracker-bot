from collections import defaultdict
from itertools import zip_longest
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
    @commands.slash_command(name="dt-help", description="Getting started.")
    async def help(self, inter : disnake.ApplicationCommandInteraction):
        await inter.response.defer()

        embeds = []

        if not inter.user.guild_permissions.manage_guild:
            emb_err = disnake.Embed(color=14242639)
            emb_err.title = "❌ Permission Error"
            emb_err.description = "Sorry, you don't have enough permissions on this server to manage this bot."
            embeds.append(emb_err)
        else:
            emb_help = disnake.Embed(color=7506394)
            emb_help.description = """
            **Specific channel for each game**
            ```/dt-set-channel game channel: #sc-devtracker game: Star Citizen```

            **Single channel for all games**
            ```/dt-set-channel default channel: #devtracker```
            Add some games:
```
/dt-follow game: Star Citizen
/dt-follow game: Elite: Dangerous
```
            All posts will then be sent all the post from __Star Citizen__ and __Elite: Dangerous__ to the __#devtracker__ channel.


            **Filtering posts**
            `/dt-allowlist`: Only posts matching the accounts or services in this list will be sent.
            `/dt-ignorelist`: Posts matching the accounts or services in this list will be ignored.

            __Notes__:
            - Each `allowlist` or `ignorelist` is game-specific, so you can have different filters for each game.
            - You can use both at the same time, but the `allowlist` will take precedence over the `ignorelist`.
            - You'll find the `account_id` in the footer of each post.

            **Get current configuration**
            ```/dt-config```
            """
            emb_help_links = disnake.Embed(color=6013150)
            emb_help_links.title = "Need more help?"
            emb_help_links.description = """
                - Detailed [commands](https://github.com/s0me-1/devtracker-bot#commands) page.
                - DevTracker Official [Discord Server](https://discord.gg/QN9uveFYXX).
                - DevTracker [Github](https://github.com/s0me-1/devtracker-bot) page.
            """
            embeds.append(emb_help)
            embeds.append(emb_help_links)
        await inter.edit_original_message(embeds=embeds)

    @commands.slash_command(name="dt-config", description="See the current configuration of this server.")
    @commands.default_member_permissions(manage_guild=True)
    async def get_current_config(self, inter : disnake.ApplicationCommandInteraction):
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : Status request')

        await inter.response.defer()

        default_channel_id = await ORM.get_main_channel(inter.guild_id)

        chname = 'Not set'
        emb_err = None
        if default_channel_id:
            emb_err = disnake.Embed(colour=14242639)
            emb_err.title = "❌ Permission Error"
            bot_member = inter.guild.get_member(self.bot.user.id)
            channel = inter.guild.get_channel(default_channel_id)
            perms = channel.permissions_for(bot_member)
            if not perms.view_channel:
                emb_err.description = f"Missing `View Channel` Permission for default channel <#{default_channel_id}>"
            if not perms.send_messages:
                emb_err.description = f"Missing `Send Message` Channel Permission for default channel <#{default_channel_id}> "
            chname = f'<#{default_channel_id}>'

        api_md = "[DeveloperTracker.com](https://developertracker.com/)\n" +  u'\u200B'
        fw_status = await ORM.get_follow_status(inter.guild_id)

        ignored_accounts = await ORM.get_ignored_accounts_per_game(inter.guild_id)
        ignored_services = await ORM.get_ignored_services_per_game(inter.guild_id)
        allowed_accounts = await ORM.get_allowed_accounts_per_game(inter.guild_id)
        allowed_services = await ORM.get_allowed_services_per_game(inter.guild_id)

        fw_tabs = self._generate_fw_table(fw_status, inter.guild)

        local_game_data = await ORM.get_local_games()
        games = {}
        for g in local_game_data:
            games.update({
                g[0]: g[1]
            })

        ignored_acc_tabs = self._generate_ignored_table(games, ignored_accounts)
        ignored_serv_tabs = self._generate_ignored_table(games, ignored_services)
        allowed_acc_tabs = self._generate_ignored_table(games, allowed_accounts)
        allowed_serv_tabs = self._generate_ignored_table(games, allowed_services)

        filter_mode = None
        if (len(ignored_accounts) > 0 or len(ignored_services) > 0) and not (len(allowed_accounts) > 0 or len(allowed_services) > 0):
            filter_mode = "ignorelist"
        elif not (len(ignored_accounts) > 0 or len(ignored_services) > 0) and (len(allowed_accounts) > 0 or len(allowed_services) > 0):
            filter_mode = "allowlist"
        elif (len(ignored_accounts) > 0 or len(ignored_services) > 0) and (len(allowed_accounts) > 0 or len(allowed_services) > 0):
            filter_mode = "allowlist_and_ignorelist"

        api_status_code, latency = await API.get_status()
        emoji = "✅" if api_status_code == 200 else "❌"
        api_status = f"API Status - {emoji} ({api_status_code})"
        version = f'v{self.bot.__version__}'

        description = "- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n" \
            " - DevTracker Official [Discord Server](https://discord.gg/QN9uveFYXX).\n" \
            " - DevTracker [Github](https://github.com/s0me-1/devtracker-bot#commands) page.\n" +  u'\u200B'

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

        if emb_err.description:
            embeds.append(emb_err)

        if filter_mode == "allowlist_and_ignorelist":
            emb = disnake.Embed(
                color=15773006 # BS4 Warning Color
            )
            emb.title = "⚠️ Warning !"
            emb.description = """
            It seems that you have some **allowlists** alongsite inglorelists set up.
            Please note that allowlists will **always take precedence** over ignorelists.
            """
            embeds.append(emb)

        for acc_tab in allowed_acc_tabs:
            if acc_tab == "None\n":
                break
            emb = disnake.Embed(
                color=16250871
            )
            emb.add_field(name='🔊 Allowed accounts', value=acc_tab, inline=False)
            embeds.append(emb)

        for serv_tab in allowed_serv_tabs:
            if serv_tab == "None\n":
                break
            emb = disnake.Embed(
                color=16250871
            )
            emb.add_field(name='🔊 Allowed services', value=serv_tab, inline=False)
            embeds.append(emb)

        for acc_tab in ignored_acc_tabs:
            if acc_tab == "None\n":
                break
            emb = disnake.Embed(
                color=2698028
            )
            emb.add_field(name='🔇 Ignored accounts', value=acc_tab, inline=False)
            embeds.append(emb)

        for serv_tab in ignored_serv_tabs:
            if serv_tab == "None\n":
                break
            emb = disnake.Embed(
                color=2698028
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
