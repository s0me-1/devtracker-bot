import asyncio
from collections import defaultdict
import logging
import re

from bs4 import BeautifulSoup, NavigableString
import disnake
from disnake.ext import tasks, commands

from cogs.utils.services import CUSTOMIZERS
from cogs.utils.emojimapper import EmojiMapper
from cogs.utils import autocompleters as ac
from cogs.utils import mardownify_discord as md
from cogs.utils import database as db
from cogs.utils import api
ORM = db.ORM()
API = api.API()


# Enforced by the Discord API
EMBEDS_MAX_DESC = 4096
EMBEDS_MAX_TOTAL = 6000
EMBEDS_MAX_AMOUNT = 10

logger = logging.getLogger('bot.Tracker')

# ---------------------------------------------------------------------------------
# MODALS
# ---------------------------------------------------------------------------------
class URLFiltersModal(disnake.ui.Modal):

    def __init__(self):
        # The details of the modal, and its components
        components = [
            disnake.ui.TextInput(
                label="URL Filters (Separate each by a comma (,))",
                custom_id="url_filters_input",
                value=self.current_filters,
                placeholder="spectrum/community/SC/forum/1,spectrum/community/SC/forum/4",
                max_length=1000,
            )
        ]
        super().__init__(title="Create Tag", components=components)

    # The callback received when the user input is completed.
    async def callback(self, inter: disnake.ModalInteraction):
        embed = disnake.Embed(title="Tag Creation")
        for key, value in inter.text_values.items():
            embed.add_field(
                name=key.capitalize(),
                value=value[:1024],
                inline=False,
            )
        await inter.response.send_message(embed=embed)


class Tracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.EM = EmojiMapper()
        self.resfresh_posts.start()
        logger.info("Loaded.")

    def cog_unload(self):
        self.resfresh_posts.cancel()
        logger.info('Unloaded.')

    # ---------------------------------------------------------------------------------
    # LISTENERS
    # ---------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("DevTracker has landed.")

    # ---------------------------------------------------------------------------------
    # TASKS
    # ---------------------------------------------------------------------------------

    @tasks.loop(seconds=30)
    async def resfresh_posts(self):

        logger.debug('Refreshing posts.')
        posts_per_gid = await self._fetch_posts()
        ordered_fws = await self._fetch_fw()

        api_games_dict = await API.fetch_available_games()
        fw_game_ids = await ORM.get_all_followed_games()
        local_games = await ORM.get_local_games()

        if len(api_games_dict.keys()) > len(local_games):
            # No need to reread, next loop will do it
            await ORM.update_local_games(api_games_dict)

        game_ids = [g[0] for g in local_games]

        guild = None
        channel = None
        default_channel_id = None

        all_ignored_accounts = await ORM.get_all_ignored_accounts_per_guild()
        all_ignored_services = await ORM.get_all_ignored_services()

        all_allowed_accounts = await ORM.get_all_allowed_accounts_per_guild()
        all_allowed_services = await ORM.get_all_allowed_services()

        if not posts_per_gid:
            logger.error("API didnt returned anything !")
            return

        saved_post_ids_per_game = await ORM.get_saved_post_ids()
        if not saved_post_ids_per_game:
            logger.error("No saved post_ids detected ! Please init them with /dt-save-posts")
            return

        if not game_ids:
            logger.error("No games found !")
            return

        embeds_per_gid = defaultdict(list)

        for gid in game_ids:
            if gid not in posts_per_gid.keys():
                logger.warning(f"{gid} is in the available games but no posts were found.")
                continue

            ordered_posts = sorted(posts_per_gid[gid], key=lambda p: p['timestamp'], reverse=True)

            current_post_ids = set([p['id'] for p in posts_per_gid[gid]])
            saved_post_ids = set(saved_post_ids_per_game[gid])
            new_post_ids = current_post_ids.difference(saved_post_ids)

            if not new_post_ids:
                logger.debug(f'{gid}: No new posts detected.')
            else:
                logger.info(f"{gid}: New posts detected ({new_post_ids}).")
                new_posts = list(filter(lambda p: p['id'] in new_post_ids, ordered_posts))

                for post in new_posts:
                    if gid not in fw_game_ids:
                        # logger.info(f"Ignoring {gid} because it isnt followed by anyone.")
                        continue

                    logger.info(f"Processing: [{gid}] {post['account']['identifier']} | {post['topic']} [{post['id']}] ")
                    em = self._generate_embed(post)
                    embeds_per_gid[gid].append((em, post['account']['identifier'], post['account']['service']))

        message_queue = []
        for last_post_id, channel_id, guild_id, game_id in ordered_fws:
            if not guild or guild.id != guild_id:
                default_channel_id = await ORM.get_main_channel(guild_id)
                guild = self.bot.get_guild(guild_id)

            # Means the bot lost permissions for some reasons
            if not guild:
                logger.warning(f'{guild_id} cant be found in the discord API !')
                continue

            if channel_id:
                channel = guild.get_channel(channel_id)
            elif default_channel_id:
                channel = guild.get_channel(default_channel_id)
            else:
                logger.debug(f'{guild.name} [{guild.id}] follows {game_id} but hasnt set any channel')

                # We can see the owner only if we have the Members privileged intent
                if not guild.owner:
                    continue

                try:
                    msg = "It seems you're following `{game_id}` but you have not set any channel !\n"
                    msg += "Please set a channel with `/dt-set-channel` to receives the latests posts."
                    await guild.owner.send(msg)
                except disnake.Forbidden:
                    logger.warning(f'{guild.owner.name} has blocked his DMs.')
                continue

            if game_id not in embeds_per_gid.keys():
                logger.debug(f'No new posts for {game_id}.')
                continue

            if not channel:
                logger.error(f'Could not find a proper channel [{channel_id} | {default_channel_id}].')
                continue

            url_filters_per_service = await ORM.get_urlfilters_per_service(guild_id, game_id)

            messages = []
            embeds = []
            embeds_size = 0

            for em, account_id, service_id in embeds_per_gid[game_id]:

                # Check Whitelist/Blacklist
                skip_post = self._should_skip(guild_id, game_id, service_id, account_id, all_ignored_accounts, all_ignored_services, all_allowed_accounts, all_allowed_services)
                if skip_post:
                    continue

                if service_id in url_filters_per_service.keys():
                    filter_result = self._apply_urlfilters(guild, url_filters_per_service[service_id], em.fields[0].value)

                    # Only send message if filters are matched if no channel_id
                    if filter_result == 'skip_post':
                        continue

                    # Means we have to override the current channel
                    elif isinstance(filter_result, disnake.TextChannel):
                        channel = filter_result

                    elif isinstance(filter_result, disnake.Thread):
                        channel = filter_result

                embeds.append(em)
                embeds_size += len(em)

                # Remove last embed if we're not repecting the Discords limits
                if len(embeds) > EMBEDS_MAX_AMOUNT or embeds_size > EMBEDS_MAX_TOTAL:
                    logger.warning("Discord Limits Reached, creating a new message.")
                    embeds.pop()
                    messages.append({
                        'embeds': embeds,
                        'game_id': game_id
                    })
                    embeds = [em]
                    embeds_size = len(em)

            if embeds:
                messages.append({'embeds': embeds, 'game_id': game_id})
            if messages:
                message_queue.append((channel, messages, ordered_posts[0]['id']))
                logger.debug(f"{guild_id}/{game_id}: {len(messages)} messages to send.")

        await asyncio.gather(
            *[
                self._send_embeds(channel, messages, latest_post_id)
                for channel, messages, latest_post_id in message_queue
            ],
        )

        if embeds_per_gid:
            logger.info(f"Updating posts state for {embeds_per_gid.keys()}")
            await asyncio.gather(
                *[
                    ORM.set_saved_post_ids(gid, [p['id'] for p in posts_per_gid[gid]])
                    for gid in embeds_per_gid.keys()
                ],
            )
        logger.debug('Refresh task completed.')

    async def _send_embeds(self, channel_or_thread, messages, last_post_id):
        for msg in messages:
            if channel_or_thread:
                logger.info(f"{channel_or_thread.guild.name} [{channel_or_thread.guild.id}]: Sending {len(msg['embeds'])} embeds to {channel_or_thread.name}.")
            else:
                logger.error("Tried to send embeds to a channel that does not exist !")
                continue
            try:
                await channel_or_thread.send(embeds=msg['embeds'])
                await ORM.set_last_post(last_post_id, channel_or_thread.guild.id, msg['game_id'])

            except disnake.Forbidden:
                logger.warning(f"Missing permissions for #{channel_or_thread.name}")
                if not channel_or_thread.guild.owner_id:
                    continue
                try:
                    owner = await self.bot.fetch_user(channel_or_thread.guild.owner_id)
                    if not owner.dm_channel:
                        await owner.create_dm()
                    error_msg = f"Sending the latest post for {msg['game_id']} in {channel_or_thread.mention} failed because I'm not allowed to send messages in this channel."
                    error_msg += "\nPlease give me the `Send Messages` permission for this channel or set another channel with `/dt-set-channel`."
                    await owner.dm_channel.send(error_msg)
                    logger.info(f'{channel_or_thread.guild.name}[{channel_or_thread.guild.id}]: Owner has been warned. ')
                except disnake.Forbidden:
                    logger.warning(f'{channel_or_thread.guild.name}[{channel_or_thread.guild.id}]: Owner cannot be contacted via DM (Forbidden) ')

            except disnake.HTTPException as e:
                logger.error(f"HTTPException: {e.code} | {e.status} | {e.text}")
                continue

    @resfresh_posts.before_loop
    async def before_refresh(self):
        logger.info('Waiting before launching refresh task...')
        await self.bot.wait_until_ready()
        logger.info(f'Bot ready, launching refresh task. (Loop every {self.resfresh_posts.seconds} seconds)')

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------
    # Trackers /
    # -------/

    @commands.slash_command(name="dt-follow", description="Add a game to follow.")
    @commands.default_member_permissions(manage_guild=True)
    async def follow_game(self, inter: disnake.AppCommandInteraction, game_name: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()

        games = await API.fetch_available_games()

        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]

            await ORM.add_followed_game(game_id, inter.guild_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{game_id}" followed')

            msg = f'`{game_name}` has been added to following list.'
            default_channel_id = await ORM.get_main_channel(inter.guild_id)
            game_channel_id = await ORM.get_game_channel(game_id, inter.guild_id)
            channel_id = game_channel_id or default_channel_id
            if channel_id:
                msg += f" I'll post new entries in <#{channel_id}>. You should receive the last post in a few moments."
                # Fetch last post to show everything is working as intended
                emb_success.description = msg
                await inter.edit_original_message(embed=emb_success)
                try:
                    await self._fetch_last_post(game_id, inter.guild.get_channel(channel_id), inter.guild)
                except disnake.Forbidden:
                    emb = disnake.Embed(colour=14242639)
                    emb.title = "❌ Permission Error"
                    msg = f"It seems I don't have the permission to post in <#{channel_id}>. "
                    msg += f"Please note that it means you won't receive any post for `{game_name}` until you resolve this issue."
                    emb.description = msg
                    logger.warning(f'{inter.guild.name} [{inter.guild_id}] : Missing permissions for #{channel_id}, error embed sent instead.')
                    await inter.edit_original_message(embed=emb)
            else:
                msg += " Please use `/dt-set-channel` to receive the latest posts."
                emb_success.description = msg
                await inter.edit_original_message(embed=emb_success)

    @commands.slash_command(name="dt-set-channel")
    @commands.default_member_permissions(manage_guild=True)
    async def set_channel(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @set_channel.sub_command(name="default", description="Set the default notification channel.")
    async def set_default_channel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):

        await inter.response.defer()

        await ORM.set_main_channel(channel.id, inter.guild_id)
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : #{channel.name} set as default channel')

        msg = f"<#{channel.id}> set as default channel.\n"

        all_follows = await ORM.get_follows(inter.guild.id)
        new_follows = [fw for fw in all_follows if fw[1] == channel.id or not fw[1]]

        bot_member = inter.guild.get_member(self.bot.user.id)
        perms = channel.permissions_for(bot_member)
        emb_err = disnake.Embed(colour=14242639)

        if not perms.view_channel:
            emb_err.title = "❌ Permission Error"
            emb_err.description = f"It seems I'm not allowed to view  <#{channel.id}>, please check my permissions."
        elif not perms.send_messages:
            emb_err.title = "❌ Permission Error"
            emb_err.description = f"It seems I'm not allowed to send message in <#{channel.id}>, please check my permissions."
        else:
            msg += "Fetching latest posts from your current followed games that didn't had a channel before..."

        emb_err = emb_err if emb_err.description else None
        await inter.edit_original_message(content=msg, embed=emb_err)

        await asyncio.gather(
            *[
                self._fetch_last_post(game_id, channel, inter.guild)
                for _, _, _, game_id in new_follows
            ],
        )

    @set_channel.sub_command(name="game", description="Set the notification channel per game. The game will be followed if it's not the case already.")
    async def set_game_channel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel, game_name: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()
        emb_err = disnake.Embed(colour=14242639)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]

            fw = await ORM.get_follow(inter.guild_id, game_id)
            if fw:
                await ORM.set_game_channel(channel.id, inter.guild_id, game_id)
            else:
                await ORM.add_fw_game_channel(channel.id, inter.guild_id, game_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : #{channel.name} set as channel for `{game_name}`')

            msg = f"<#{channel.id}> set as notification channel for `{game_name}`. You should receive the last post shortly.\n"

            bot_member = inter.guild.get_member(self.bot.user.id)
            perms = channel.permissions_for(bot_member)

            if not perms.view_channel:
                emb_err.title = "❌ Permission Error"
                emb_err.description = f"It seems I'm not allowed see <#{channel.id}>, please check my permissions."
            elif not perms.send_messages:
                emb_err.title = "❌ Permission Error"
                emb_err.description = f"It seems I'm not allowed see <#{channel.id}>, please check my permissions."

            emb_err = emb_err if emb_err.description else None
            await inter.edit_original_message(content=msg, embed=emb_err)

            # Fetch last post to show everything is working as intended
            try:
                await self._fetch_last_post(game_id, channel, inter.guild)
            except disnake.Forbidden:
                emb_err.title = "❌ Permission Error"
                emb_err.description = f"I don't have the permission to send the latest post for {game_name} in <#{channel.id}>"
                logger.warning(f'{inter.guild.name} [{inter.guild_id}] : Missing permissions for #{channel.id}, error embed sent instead.')
                await inter.edit_original_message(embed=emb_err)

    @commands.slash_command(name="dt-ignorelist", description="Ignore posts from a specific account.")
    @commands.default_member_permissions(manage_guild=True)
    async def ignorelist(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @ignorelist.sub_command_group(name="add", description="Add an account to the ignore.")
    async def ignorelist_add(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @ignorelist_add.sub_command(name="account", description="Ignore posts from a specific account.")
    async def ignorelist_add_account(self, inter: disnake.ApplicationCommandInteraction,
                                     game_name: str = commands.Param(autocomplete=ac.games_fw),
                                     service_id: str = commands.Param(autocomplete=ac.accounts_service_all),
                                     account_id: str = commands.Param(autocomplete=ac.accounts_all)):

        await inter.response.defer()
        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]
            accounts = await API.fetch_accounts(game_id)
            account_ids = [a["identifier"] for a in accounts]
            if account_id not in account_ids:
                emb_err.title = "❌ Account Error"
                emb_err.description = f"`{account_id}` doesn't exists or isn't followed for `{game_name}`."
                await inter.edit_original_message(embed=emb_err)
            else:
                await ORM.add_ignored_account(inter.guild_id, game_id, account_id, service_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{account_id}" muted')

                emb_success.description = f'Posts from `{account_id} [{service_id}]` will be ignored from now on for `{game_name}`'
                await inter.edit_original_message(embed=emb_success)

    @ignorelist_add.sub_command(name="service", description="Ignore posts from a specific service.")
    async def ignorelist_add_service(self, inter: disnake.ApplicationCommandInteraction, game_name: str = commands.Param(autocomplete=ac.games_fw), service_id: str = commands.Param(autocomplete=ac.services_all)):

        await inter.response.defer()

        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]
            service_ids = await API.fetch_services(game_id)
            if service_id not in service_ids:
                emb_err.title = "❌ Service Error"
                emb_err.description = f"`{service_id}` doesn't exists or isn't followed for `{game_name}`."
                await inter.edit_original_message(embed=emb_err)
            else:
                await ORM.add_ignored_service(inter.guild_id, game_id, service_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{service_id}" added to ignorelist for `{game_name}`')

                emb_success.description = f'Posts from `{service_id}` will be ignored from now on for `{game_name}`'
                await inter.edit_original_message(embed=emb_success)

    @ignorelist.sub_command_group(name="remove", description="Remove an account from the ignore.")
    async def ignorelist_rm(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @ignorelist_rm.sub_command(name="account", description="Remove a previously ignored account from the ignore.")
    async def ignorelist_rm_account(self, inter, game_name: str = commands.Param(autocomplete=ac.games_fw), account_id: str = commands.Param(autocomplete=ac.accounts_ignored)):

        await inter.response.defer()

        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]

            account_ids = await ORM.get_ignored_accounts(inter.guild_id, game_id)
            if account_id not in account_ids:
                emb_err.title = "❌ Account Error"
                emb_err.description = f"`{account_id}` isn't in your ignore list."
                await inter.edit_original_message(embed=emb_err)
            else:
                await ORM.rm_ignored_account(inter.guild_id, game_id, account_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{account_id}" removed from ignorelist for {game_name}')
                emb_success.description = f'Posts from `{account_id}` will no longer be ignored for {game_name}.'
                await inter.edit_original_message(embed=emb_success)

    @ignorelist_rm.sub_command(name="service", description="Remove a previously ignored service from the ignore.")
    async def ignorelist_rm_service(self, inter, game_name: str = commands.Param(autocomplete=ac.games_fw), service_id: str = commands.Param(autocomplete=ac.service_ignored)):

        await inter.response.defer()

        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]

            service_ids = await ORM.get_ignored_services(inter.guild_id, game_id)
            if service_id not in service_ids:
                emb_err.title = "❌ Service Error"
                emb_err.description = f"`{service_id}` isn't in your ignore list."
                await inter.edit_original_message(embed=emb_err)
            else:
                await ORM.rm_ignored_service(inter.guild_id, game_id, service_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{service_id}" removed from ignorelist for {game_id}')
                emb_success.description = f'Posts from `{service_id}` will no longer be ignored for {game_id}.'
                await inter.edit_original_message(embed=emb_success)

    @commands.slash_command(name="dt-allowlist", description="Accept posts only from specific accounts.")
    @commands.default_member_permissions(manage_guild=True)
    async def allowlist(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @allowlist.sub_command_group(name="add", description="Add an account to the allowlist.")
    async def allowlist_add(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @allowlist_add.sub_command(name="account", description="Allow only posts from specific accounts.")
    async def allowlist_add_account(self, inter: disnake.ApplicationCommandInteraction,
                                    game_name: str = commands.Param(autocomplete=ac.games_fw),
                                    service_id: str = commands.Param(autocomplete=ac.accounts_service_all),
                                    account_id: str = commands.Param(autocomplete=ac.accounts_all)):

        await inter.response.defer()

        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]
            accounts = await API.fetch_accounts(game_id)
            account_ids = [a['identifier'] for a in accounts if a['service'] == service_id]
            if account_id not in account_ids:
                emb_err.title = "❌ Account Error"
                emb_err.description = f"`{account_id}` doesn't exists or isn't followed for `{game_name}`."
                await inter.edit_original_message(embed=emb_err)
            else:
                await ORM.add_allowed_account(inter.guild_id, game_id, account_id, service_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{account_id}" added to allowlist for {game_name} ')
                emb_success.description = f'The account `{account_id}` has been added to the allowlist for `{game_name}`. From now on, only posts of service(s)/account(s) from this allowlist will be sent.'
                await inter.edit_original_message(embed=emb_success)

    @allowlist_add.sub_command(name="service", description="Allow only posts from specific services.")
    async def allowlist_add_service(self, inter: disnake.ApplicationCommandInteraction, game_name: str = commands.Param(autocomplete=ac.games_fw), service_id: str = commands.Param(autocomplete=ac.services_all)):

        await inter.response.defer()

        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]
            service_ids = await API.fetch_services(game_id)
            if service_id not in service_ids:
                emb_err.title = "❌ Service Error"
                emb_err.description = f"`{service_id}` doesn't exists or isn't followed for `{game_name}`."
                await inter.edit_original_message(embed=emb_err)
            else:
                await ORM.add_allowed_service(inter.guild_id, game_id, service_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{service_id}" added to allowlist for `{game_name}`')
                emb_success.description = f'The service `{service_id}` has been added to the allowlist for `{game_name}`. From now on, only posts of service(s)/account(s) from this allowlist will be sent.'
                await inter.edit_original_message(embed=emb_success)

    @allowlist.sub_command_group(name="remove", description="Remove an account from the allowlist.")
    async def allowlist_rm(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @allowlist_rm.sub_command(name="account", description="Remove a previously ignored account from the allowlist.")
    async def allowlist_rm_account(self, inter, game_name: str = commands.Param(autocomplete=ac.games_fw), account_id: str = commands.Param(autocomplete=ac.accounts_allowed)):

        await inter.response.defer()

        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]

            account_ids = await ORM.get_allowed_accounts(inter.guild_id, game_id)
            if account_id not in account_ids:
                emb_err.title = "❌ Account Error"
                emb_err.description = f"`{account_id}` isn't in your allowlist."
                await inter.edit_original_message(embed=emb_err)
            else:
                await ORM.rm_allowed_account(inter.guild_id, game_id, account_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{account_id}" removed from allowlist for {game_name}')
                emb_success.description = f'The account `{account_id}` has been removed from the allowlist for `{game_name}`.'
                await inter.edit_original_message(embed=emb_success)

    @allowlist_rm.sub_command(name="service", description="Remove a previously ignored service from the ignore.")
    async def allowlist_service(self, inter, game_name: str = commands.Param(autocomplete=ac.games_fw), service_id: str = commands.Param(autocomplete=ac.service_allowed)):

        await inter.response.defer()

        emb_err = disnake.Embed(colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        games = await API.fetch_available_games()
        if not games:
            emb_err.title = "❌ API Error"
            emb_err.description = "It seems the DeveloperTracker.com API didn't respond. Please try again later."
            await inter.edit_original_message(embed=emb_err)
            return

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_err)
            return
        else:
            game_id = games[game_name]

            service_ids = await ORM.get_allowed_services(inter.guild_id, game_id)
            if service_id not in service_ids:
                emb_err.title = "❌ Service Error"
                emb_err.description = f"`{service_id}` isn't in your allowlist."
                await inter.edit_original_message(embed=emb_err)
            else:
                await ORM.rm_allowed_service(inter.guild_id, game_id, service_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{service_id}" unmuted for {game_id}')
                emb_success.description = f'The service `{service_id}` has been removed from the allowlist for `{game_name}`.'
                await inter.edit_original_message(embed=emb_success)

    @commands.slash_command(name="dt-urlfilters", description="Accept posts only with specific keywords in their origin URLs.")
    @commands.default_member_permissions(manage_guild=True)
    async def manage_urlfilters(self, inter: disnake.ApplicationCommandInteraction):
        pass

    async def _urlfilters_send_modal(self, inter, game_name, service_id, current_filters, channel_or_thread):

        title = f"{game_name} [{service_id}] - {channel_or_thread.name}"
        title_shortened = title[:40] + "..." if len(title) > 44 else title
        warning_msg = f"Make sure DevTracker is allowed to send messages in #{channel_or_thread.name}, otherwise you won't receive any post."

        await inter.response.send_modal(
            title=title_shortened,
            custom_id=f"url_filters_modal-{inter.id}",
            components=[
                disnake.ui.TextInput(
                    label="Warning !",
                    custom_id="url_filters_warning",
                    value=warning_msg,
                    max_length=300,
                    style=disnake.TextInputStyle.paragraph,
                ),
                disnake.ui.TextInput(
                    label="URL Filters - Separated by commas (,)",
                    custom_id="url_filters_input",
                    value=current_filters,
                    placeholder="forum/1,forum/4",
                    max_length=1000,
                    style=disnake.TextInputStyle.paragraph,
                )
            ]
        )
        try:
            modal_inter: disnake.ModalInteraction = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.custom_id == f"url_filters_modal-{inter.id}" and i.author.id == inter.author.id,
                timeout=300,
            )
        except asyncio.TimeoutError:
            # user didn't submit the modal, so a timeout error is raised
            emb_err = disnake.Embed(colour=14242639)
            emb_err.title = "❌ Timeout Error"
            emb_err.description = "Modal submission was not received quickly enough."
            await inter.send(embed=emb_err, ephemeral=True)
            return
        return modal_inter

    @manage_urlfilters.sub_command(name="global", description="Receive only posts with specific keywords in their origin URLs.")
    async def edit_urlfilters_global(self, inter: disnake.ApplicationCommandInteraction,
                                     game_name: str = commands.Param(autocomplete=ac.games_fw),
                                     service_id: str = commands.Param(autocomplete=ac.services_urlfilters_all)):

        games = await API.fetch_available_games()
        game_id = None
        emb_err = disnake.Embed(colour=14242639)

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.send(embed=emb_err)
        else:
            game_id = games[game_name]

        current_filters = await ORM.get_urlfilters(inter.guild_id, game_id, service_id)

        modal_components = []
        current_filters_raw = ""

        if len(current_filters) == 1 and not current_filters[0][0]:
            current_filters_raw = current_filters[0][1]
        elif len(current_filters) > 1:
            modal_components.append(
                disnake.ui.TextInput(
                    label="Warning !",
                    value="You have multiple filters for this service. Submitting this modal will erase them !",
                    style=disnake.TextInputStyle.short,
                )
            )
        modal_components.append(
            disnake.ui.TextInput(
                label="URL Filters - Separated by commas (,)",
                custom_id="url_filters_input",
                value=current_filters_raw,
                placeholder="forum/1,forum/4",
                max_length=1000,
                style=disnake.TextInputStyle.paragraph,
            )
        )
        title = f"{game_name} [{service_id}]"
        title_shortened = title[:40] + "..." if len(title) > 44 else title
        await inter.response.send_modal(
            title=title_shortened,
            custom_id=f"url_filters_modal-{inter.id}",
            components=modal_components
        )
        try:
            modal_inter: disnake.ModalInteraction = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.custom_id == f"url_filters_modal-{inter.id}" and i.author.id == inter.author.id,
                timeout=300,
            )
        except asyncio.TimeoutError:
            # user didn't submit the modal, so a timeout error is raised
            # we don't have any action to take, so just return early

            emb_err.title = "❌ Timeout Error"
            emb_err.description = "Modal submission was not received quickly enough."
            await inter.send(embed=emb_err, ephemeral=True)
            return

        await modal_inter.response.defer()
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)
        emb_success.description = f"Global URL filters for {game_name} [{service_id}] have been updated.\n" \
            "Only posts with URLs containing the specified keywords will be sent." \
            "\n\n **Note:**" \
            "\n- If you want to clear all current filters, use `dt-clear` instead." \
            "\n- You can see all your courrent filters with `dt-config`."
        emb_success.add_field(name="Filters", value=modal_inter.text_values["url_filters_input"])

        new_filters = modal_inter.text_values["url_filters_input"]
        if new_filters and game_id:
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{new_filters}" added as URL filters for {game_name} [{service_id}]')
            await ORM.update_urlfilters_global(inter.guild_id, game_id, service_id, modal_inter.text_values["url_filters_input"])
        await modal_inter.edit_original_message(embed=emb_success)

    @manage_urlfilters.sub_command(name="channel", description="Dispatch posts with specific keywords in their origin URLs to a specific channel.")
    async def edit_urlfilters_channel(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel,
        game_name: str = commands.Param(autocomplete=ac.games_fw),
        service_id: str = commands.Param(autocomplete=ac.services_urlfilters_channel),
    ):

        games = await API.fetch_available_games()
        current_channel_filters = None

        emb_err = disnake.Embed(colour=14242639)

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.send(embed=emb_err)
            return
        else:
            game_id = games[game_name]
            current_channel_filters = await ORM.get_urlfilters_channel(inter.guild_id, game_id, service_id, channel_id=channel.id)

        modal_inter = await self._urlfilters_send_modal(inter, game_name, service_id, current_channel_filters, channel)

        await modal_inter.response.defer()
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)
        emb_success.description = f"URL filters for **{game_name}** [`{service_id}`] have been updated.\n" \
            f"Posts with URLs containing the specified keywords will be sent to <#{channel.id}>." \
            "\n\n **Note:**" \
            "\n- If you want to clear all current filters, use `dt-clear` instead." \
            "\n- You can see all your courrent filters with `dt-config`."

        emb_success.add_field(name="Filters", value=modal_inter.text_values["url_filters_input"])

        new_filters = modal_inter.text_values["url_filters_input"]
        if new_filters:
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{new_filters}" added as URL filters for {game_name} [{service_id}] - Redirect to  channel {channel.name}')
            await ORM.update_urlfilters_channel(inter.guild_id, game_id, service_id, new_filters, channel_id=channel.id),
            await modal_inter.edit_original_message(embed=emb_success)
        else:
            emb_neutral = disnake.Embed(description=" ❌ No filters were provided. No changes were made.")
            await modal_inter.edit_original_message(embed=emb_neutral)

    @manage_urlfilters.sub_command(name="thread", description="Dispatch posts with specific keywords in their origin URLs to a specific thread.")
    async def edit_urlfilters_thread(
        self,
        inter: disnake.ApplicationCommandInteraction,
        thread: disnake.Thread,
        game_name: str = commands.Param(autocomplete=ac.games_fw),
        service_id: str = commands.Param(autocomplete=ac.services_urlfilters_thread),
    ):

        games = await API.fetch_available_games()
        current_channel_filters = None

        emb_err = disnake.Embed(colour=14242639)

        if game_name not in games.keys():
            emb_err.title = "❌ Game Error"
            emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.send(embed=emb_err)
            return
        else:
            game_id = games[game_name]
            current_channel_filters = await ORM.get_urlfilters_channel(inter.guild_id, game_id, service_id, thread_id=thread.id)

        modal_inter = await self._urlfilters_send_modal(inter, game_name, service_id, current_channel_filters, thread)

        await modal_inter.response.defer()
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)
        emb_success.description = f"URL filters for **{game_name}** [`{service_id}`] have been updated.\n" \
            f"Posts with URLs containing the specified keywords will be sent to <#{thread.id}>." \
            "\n\n **Note:**" \
            "\n- If you want to clear all current filters, use `dt-clear` instead." \
            "\n- You can see all your courrent filters with `dt-config`."

        emb_success.add_field(name="Filters", value=modal_inter.text_values["url_filters_input"])

        new_filters = modal_inter.text_values["url_filters_input"]
        if new_filters:
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{new_filters}" added as URL filters for {game_name} [{service_id}] - Redirect to Thread {thread.name}')
            await ORM.update_urlfilters_channel(inter.guild_id, game_id, service_id, new_filters, thread_id=thread.id),
            await modal_inter.edit_original_message(embed=emb_success)
        else:
            emb_neutral = disnake.Embed(description=" ❌ No filters were provided. No changes were made.")
            await modal_inter.edit_original_message(embed=emb_neutral)

    @manage_urlfilters.sub_command(name="clear", description="Clear all current urlfilters.")
    async def clear_urlfilters(
        self,
        inter: disnake.ApplicationCommandInteraction,
        game_name: str = commands.Param(autocomplete=ac.games_fw),
        service_id: str = commands.Param(autocomplete=ac.services_urlfilters_clear),
    ):
        await inter.response.defer()

        games = await API.fetch_available_games()
        game_id = None

        emb_err = disnake.Embed(colour=14242639)
        if game_name in games.keys():
            game_id = games[game_name]

            if game_id:
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : URL filters cleared for {game_name} [{service_id}]')
                await ORM.clear_urlfilters(inter.guild_id, game_id, service_id)

                emb_success = disnake.Embed(title="✅  Success", colour=6076508)
                emb_success.description = f"All URL filters for **{game_name}** [`{service_id}`] have been cleared."
                await inter.edit_original_message(embed=emb_success)
                return

        emb_err.title = "❌ Game Error"
        emb_err.description = f"`{game_name}` is either an invalid game or unsupported."
        await inter.edit_original_message(embed=emb_err)

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------
    # Untrackers /
    # ---------/

    @commands.slash_command(name="dt-unfollow", description="Remove a game to the following list")
    @commands.default_member_permissions(manage_guild=True)
    async def unfollow_game(self, inter: disnake.ApplicationCommandInteraction, game: str = commands.Param(autocomplete=ac.games_fw)):

        await inter.response.defer()

        local_games = await ORM.get_local_games()
        game_id = [g[0] for g in local_games if g[1] == game][0]

        emb_error = disnake.Embed(title="❌  Error", colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        if not game_id:
            emb_error.description = f"`{game}` isn't in your following list."
            await inter.edit_original_message(embed=emb_error)
        else:
            await ORM.rm_followed_game(game_id, inter.guild_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{game_id}" unfollowed')
            emb_success.description = f'`{game}` has been removed from the following list.'
            await inter.edit_original_message(embed=emb_success)

    @commands.slash_command(name="dt-unset-channel")
    @commands.default_member_permissions(manage_guild=True)
    async def unset_channel(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @unset_channel.sub_command(name="default", description="Unset the default notification channel.")
    async def unset_default_channel(self, inter: disnake.ApplicationCommandInteraction):

        await inter.response.defer()

        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        await ORM.unset_main_channel(inter.guild_id)
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : Default channel deleted')
        emb_success.description = "You don't have a default channel anymore, make sure you have one set for each followed games using `/dt-status`."
        await inter.edit_original_message(embed=emb_success)

    @unset_channel.sub_command(name="game", description="Unset the notification channel per game.")
    async def unset_game_channel(self, inter: disnake.ApplicationCommandInteraction, game: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()

        local_games = await ORM.get_local_games()
        game_id = [g[0] for g in local_games if g[1] == game][0]

        emb_error = disnake.Embed(title="❌  Error", colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        if not game_id:
            emb_error.description = f"`{game}` isn't in your following list."
            await inter.edit_original_message(embed=emb_error)
        else:
            await ORM.unset_game_channel(inter.guild_id, game_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : Unset custom channel for `{game}`')
            emb_success.description = f"The notification channel for `{game}` is no longer set."
            await inter.edit_original_message(emb=emb_success)

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------
    # Debug      /
    # ---------/

    @commands.slash_command(name="dt-force-send-post", description="[TECHNICAL] Debug bad formatted messages.", guild_ids=[687999396612407341, 1091641191176605796])
    @commands.default_member_permissions(manage_guild=True)
    async def force_fetch_last_post(self, inter: disnake.ApplicationCommandInteraction, post_id: str, game_name: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()

        emb_error = disnake.Embed(title="❌  Error", colour=14242639)

        logger.info(f'Forcing fetch of {post_id}.')
        games = await API.fetch_available_games()
        if game_name not in games.keys():
            emb_error.description = f"`{game_name}` is either an invalid game or unsupported."
            await inter.edit_original_message(embed=emb_error)
        else:
            game_id = games[game_name]
            post = await API.fetch_post(post_id, game_id)

            if not post:
                await inter.edit_original_message("I cannot fetch that post anymore.")
                return

            soup = BeautifulSoup(post[0]['content'], "html.parser")
            logger.debug(soup)
            logger.info(soup.prettify())
            if len(post) == 0:
                emb_error.description = f"`{post_id}` not found."
                await inter.edit_original_message(embed=emb_error)
            else:
                em = self._generate_embed(post[0])

                all_ignored_accounts = await ORM.get_all_ignored_accounts_per_guild()
                all_ignored_services = await ORM.get_all_ignored_services()
                all_allowed_accounts = await ORM.get_all_allowed_accounts_per_guild()
                all_allowed_services = await ORM.get_all_allowed_services()

                should_skip = self._should_skip(
                    inter.guild_id,
                    game_id,
                    post[0]['account']['service'],
                    post[0]['account']['identifier'],
                    all_allowed_services,
                    all_ignored_services,
                    all_allowed_accounts,
                    all_ignored_accounts
                )

                url_filters = await ORM.get_urlfilters(inter.guild_id, game_id, post[0]['account']['service'])
                filter_result = self._apply_urlfilters(inter.guild, url_filters, em.fields[0].value)

                msg = f"**Should skip:** {should_skip}\n"
                if isinstance(filter_result, disnake.TextChannel):
                    msg += f"**Filter result:** <#{filter_result.id}>"
                else:
                    msg += f"**Filter result:** `{filter_result}`"
                await inter.edit_original_message(content=msg, embed=em)

    @commands.slash_command(name="dt-save-post-ids", description="Update posts state of the Bot.", guild_ids=[984016998084247582, 687999396612407341])
    @commands.default_member_permissions(manage_guild=True)
    async def set_current_post_ids(self, inter: disnake.ApplicationCommandInteraction):

        await inter.response.defer()
        posts_per_game = await self._fetch_posts()
        games = await API.fetch_available_games()
        game_ids = [gid for gid in games.values()]

        emb_error = disnake.Embed(title="❌  API Error", colour=14242639)
        emb_success = disnake.Embed(title="✅  Success", colour=6076508)

        if not all([gid in posts_per_game.keys() for gid in game_ids]):
            emb_error.description = "Couldn't fetch all games. Aborting..."
            await inter.edit_original_message(embed=emb_error)
            return

        for game_id, posts in posts_per_game.items():
            post_ids = [p['id'] for p in posts]
            logger.info(f"{game_id}: Updating posts state.")
            logger.debug(post_ids)
            await ORM.set_saved_post_ids(game_id, post_ids)

        emb_success.description = "The bot state has been updated."
        await inter.edit_original_message(embed=emb_success)

    @commands.slash_command(name="dt-get-post-ids", description="Show the bot state.", guild_ids=[984016998084247582, 687999396612407341])
    @commands.default_member_permissions(manage_guild=True)
    async def get_saved_post_ids(self, inter: disnake.ApplicationCommandInteraction, game_name: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()
        games = await API.fetch_available_games()
        gid = games[game_name]
        saved_post_ids = await ORM.get_saved_post_ids()

        msg = '```\n'
        for post_id in saved_post_ids[gid]:
            msg += f'{post_id}\n'
        msg += '```'

        em = disnake.Embed(description=msg, title=game_name)

        await inter.edit_original_message(embed=em)

    # ---------------------------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------------------------

    async def _fetch_last_post(self, game_id, channel: disnake.TextChannel, guild: disnake.Guild):

        post = await API.fetch_latest_post(game_id)

        if not post:
            logger.error('API didnt returned anything !')
            return

        em = self._generate_embed(post)
        post_id = post['id']
        logger.info(f'{guild.name} [{guild.id}] : Fetching {post_id} for "{game_id}". (Dest: `#{channel.name}`)')
        try:
            await channel.send(embed=em)
            await ORM.set_last_post(post_id, guild.id, game_id)
        except disnake.Forbidden as e:
            logger.error(f'{guild.name} [{guild.id}] : Cannot send message in #{channel.name}. last_post not updated.')
            raise e

    async def _fetch_fw(self):
        follows = await ORM.get_all_follows()

        # Minimize calls on DBs/Disnake per guilds
        logger.debug(f'{len(follows)} follows retrieved.')
        return sorted(follows, key=lambda fw: fw[2])

    async def _fetch_posts(self):
        games = await API.fetch_available_games()
        game_ids = [gid for gid in games.values()]
        nb_posts = 0
        res = await API.fetch_all_posts(game_ids)

        posts = {}
        for r in res:
            posts.update(r)

        errors = defaultdict(list)
        for gid, g_res in posts.items():
            if isinstance(g_res, list):
                nb_posts += len(posts[gid])
            else:
                errors[g_res].append(gid)
        err_stats = ''
        for error, gids in errors.items():
            err_stats += f'{error}: {gids}'
            for gid in gids:
                posts.pop(gid)

        err_msg = err_stats if err_stats else 'No errors'
        logger.info(f'{nb_posts} posts retrieved ({err_msg}).')
        return posts

    def _find_img(self, soup: BeautifulSoup):
        imgs = soup.find_all('img')

        if not imgs:
            return None

        # Last img first
        imgs.reverse()
        for img in imgs:
            if 'icon' in img['src'] and '.gif' in img['src']:
                # Some services use old .gif emojis, in the future it would probably
                # be better to check for a minimal size.
                continue
            else:
                # Force HTTPS url scheme
                return re.sub(r"^\/\/", 'https://', img['src'])
        return None

    def _sanitize_post_content(self, post_content, origin=None):

        if origin not in ['Twitter', ]:
            post_content = post_content.replace('\n', '')

        # Fix Missing emojis
        post_content = self.EM._replace_emoji_shortcodes(post_content)

        soup = BeautifulSoup(post_content, "html.parser")
        nb_char_overflow = len(soup.prettify()) - EMBEDS_MAX_DESC

        # Fix blockquote from Spectrum
        if origin in ['rsi', 'Bungie.net']:
            for quoteauthor in soup.find_all('div', {'class': 'quoteauthor'}):
                quoteauthor.insert_after(soup.new_tag("br"))
                quoteauthor.insert_after(soup.new_tag("br"))

        # Fix blockquote from Reddit
        if origin in ['Reddit', 'Steam']:
            for quoteauthor in soup.find_all('div', {'class': 'bb_quoteauthor'}):
                quoteauthor.insert_after(soup.new_tag("br"))
                quoteauthor.insert_after(soup.new_tag("br"))

        # Fix blockquote from Twitter
        if origin == 'Twitter':
            for quoteblock in soup.find_all('blockquote'):
                quoteauthor = quoteblock.next_element
                quoteauthor.insert_after(soup.new_tag("br"))
                quoteauthor.insert_after(soup.new_tag("br"))
                quoteauthor.insert_before("Originally posted by ")

        # Ellipsising Blocquotes
        bqs = soup.find_all('blockquote')
        if nb_char_overflow > 0:
            i = 0
            bqs = soup.find_all('blockquote')
            nb_char_stripped = 0
            last_processed_bq = False

            nb_blocquotes = len(bqs)
            # We try to remove the less text possible, ellipsising is interrupted as soon as we can
            while i < nb_blocquotes and nb_char_overflow > nb_char_stripped:
                bq = bqs[i]
                init_bq_size = len(bq.text)
                bq_ps = bq.findAll('p')

                if len(bq_ps) < 2:

                    # Prevent useless loop
                    if len(bqs) < 1:
                        nb_blocquotes = 0
                        break

                    if bqs[-1].string == '[...]':
                        bqs[-1].decompose()
                        nb_blocquotes -= 1
                        nb_char_stripped += 5
                        logger.debug(f"{nb_char_stripped} chars stripped.")
                        bqs = soup.find_all('blockquote')
                        nb_blocquotes = len(bqs)
                    elif len(bqs) > 1:
                        ellipsis = soup.new_tag('blockquote')
                        ellipsis.string = '[...]'
                        nb_char_stripped += len(bqs[-1].text) - 5
                        bqs[-1].decompose()
                        bqs[-2].insert_after(ellipsis)
                        logger.debug(f"{nb_char_stripped} chars stripped.")
                        bqs = soup.find_all('blockquote')
                        nb_blocquotes = len(bqs)
                    elif len(bqs) == 1:
                        nb_char_stripped += len(bqs[-1].text)
                        bqs[-1].decompose()
                        bqs = soup.find_all('blockquote')
                        nb_blocquotes = 0
                        break
                    else:
                        logger.error("Useless stripping loop !")
                        break

                    continue

                ellipsis = soup.new_tag('p')
                ellipsis.string = '[...]'
                bq_ps[-1].decompose()
                bq_ps[-2].insert_after(ellipsis)
                if len(bq_ps) > 2:
                    # Delete last two nodes and reinsert ellipsis
                    bq_ps[-1].decompose()
                    bq_ps[-2].decompose()
                    bq_ps[-3].insert_after(ellipsis)
                    nb_char_stripped += init_bq_size - len(bq.text)
                    last_processed_bq = bq
                else:
                    i += 1
                    continue

            # Ensure Ellipsis
            if last_processed_bq:
                last_p = last_processed_bq.findAll('p')[-1]
                if last_p.text != '[...]':
                    if last_p.string:
                        last_p.string.replace_with('[...]')
                    else:
                        last_p.append(NavigableString('[...]'))

                logger.debug(str(nb_char_stripped) + ' characters stripped from blockquotes')

        # HTML -> Markdown
        body = md.markdownify(soup, bullets="-", strip=["img"])

        # Max 2 new lines in a row
        body_trimmed = re.sub(r'\n\s*\n', '\n\n', body)

        # For blocquotes too
        # There's probably a simpler way to do this, but I'm too tired to fight with regex :D
        while re.search(r'\n>\s*\n>\s*\n>\s*\n>', body_trimmed, re.MULTILINE):
            body_trimmed = re.sub(r'\n>\s*\n>\s*\n>\s*\n>', '\n> \n> ', body_trimmed)
        body_trimmed = re.sub(r'\n>\s*\n>\s*\n>', '\n> \n> ', body_trimmed)

        description = (body_trimmed[:EMBEDS_MAX_DESC - 15] + '...\n\n[...]') if len(body_trimmed) > EMBEDS_MAX_DESC else body_trimmed

        img_url = self._find_img(soup)

        return description, img_url

    def _generate_embed(self, post):

        service = post['account']['service']

        description, img_url = self._sanitize_post_content(post['content'], origin=service)

        color = CUSTOMIZERS['default']['color']
        author_icon_url = CUSTOMIZERS['default']['icon_url']

        if service in CUSTOMIZERS.keys():
            color = CUSTOMIZERS[service]['color']
            author_icon_url = CUSTOMIZERS[service]['icon_url']
        else:
            logger.warning(f'{service} NOT FOUND in CUSTOMIZERS !')

        acc_id = post['account']['identifier']
        acc_dev_nick = post['account']['developer']['nick'] if service != "CommLink" else "Comm-Link"
        acc_dev_group = post['account']['developer']['group']

        author_text = f'{acc_dev_nick} [{acc_dev_group}]' if acc_dev_group else f'{acc_dev_nick}'
        footer_text = f"{acc_id} / {post['id']}"

        footer_icon_url = "https://i33.servimg.com/u/f33/11/20/17/41/noun-a10.png"
        field_topic = f"[{post['topic']}]({post['url']})"
        field_published = f"<t:{post['timestamp']}:f>"

        emb = disnake.Embed(
            description=description,
            color=color
        )

        emb.set_author(name=author_text, icon_url=author_icon_url)
        emb.set_footer(text=footer_text, icon_url=footer_icon_url)
        emb.add_field(name='Topic', value=field_topic, inline=True)
        emb.add_field(name='Published', value=field_published, inline=True)

        # Add any image found
        if img_url:
            emb.set_image(img_url)

        return emb

    def _should_skip(self, guild_id, game_id, service_id, account_id, all_allowed_services, all_ignored_services, all_allowed_accounts, all_ignored_accounts):

        # Always send allowed services
        if len(all_allowed_services[guild_id][game_id]) > 0 and service_id in all_allowed_services[guild_id][game_id]:
            logger.info(f"[{guild_id}] Post Sent. ({service_id} is in the allowlist).")
            return False

        # Always send allowed accounts
        elif len(all_allowed_accounts[guild_id][game_id]) > 0 and account_id in all_allowed_accounts[guild_id][game_id]:
            logger.info(f"[{guild_id}] Post Sent. ({account_id} is in the allowlist).")
            return False

        # Check if service is blacklisted
        if len(all_ignored_services[guild_id][game_id]) > 0 and service_id in all_ignored_services[guild_id][game_id]:
            logger.info(f"[{guild_id}] Post Skipped. ({service_id} is in the ignore).")
            return True

        # Check if account is blacklisted
        elif len(all_ignored_accounts[guild_id][game_id]) > 0 and account_id in all_ignored_accounts[guild_id][game_id]:
            logger.info(f"[{guild_id}] Post Skipped. ({account_id} is in the ignore).")
            return True

        return False

    def _apply_urlfilters(self, guild, url_filters, em_url):

        # Only send message if filters are matched if no channel_id
        if len(url_filters) == 1 and not url_filters[0][0] and not url_filters[0][1]:
            filters_list = url_filters[0][2].split(',')
            filters_list_sanitized = [f for f in filters_list if f]
            if not any(f.strip() in em_url for f in filters_list_sanitized):
                logger.info(f"[{guild.id}] Post Skipped. ({em_url} didn't match {filters_list} [Single Filter Mode]).")
                return 'skip_post'

        # Send everything but adapt channel accordingly
        elif len(url_filters) > 0:
            for channel_id, thread_id, filters in url_filters:
                filters_list = filters.split(',')
                filters_list_sanitized = [f for f in filters_list if f]
                if channel_id and any(f.strip() in em_url for f in filters_list_sanitized):
                    new_channel = guild.get_channel(channel_id)
                    logger.info(f"[{guild.id}] Overriding channel by #{new_channel.name}: {em_url} matched {filters} [Multi Filter Mode]).")
                    return new_channel
                elif thread_id and any(f.strip() in em_url for f in filters_list_sanitized):
                    new_thread = guild.get_thread(thread_id)
                    logger.info(f"[{guild.id}] Overriding channel by #{new_thread.name}: {em_url} matched {filters} [Multi Filter Mode]).")
                    return new_thread
        return False


def setup(bot: commands.Bot):
    bot.add_cog(Tracker(bot))
