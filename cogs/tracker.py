from collections import defaultdict
import logging
import re
from datetime import datetime

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

    @tasks.loop(minutes=5.0)
    async def resfresh_posts(self):

        logger.info('Refreshing posts.')
        posts = await self._fetch_posts()
        ordered_fws = await self._fetch_fw()

        guild = None
        channel = None
        default_channel_id = None

        all_ignored_accounts = await ORM.get_all_ignored_accounts()

        if not posts:
            logger.error("API didnt returned anything !")
            return

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
                logger.warning(f'{guild.name} [{guild.id}] follows {game_id} but hasnt set any channel')

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

            if not game_id in posts.keys():
                logger.warning(f'No posts fetched for {game_id}.')
                continue

            embeds = []
            embeds_size = 0
            ordered_posts = sorted(posts[game_id], key=lambda p: p['timestamp'], reverse=True)
            for post in ordered_posts:

                # Stop if we reach the post has already been sent (FIFO)
                if last_post_id == post['id']:
                    logger.debug(f'{guild_id}/{game_id}: {last_post_id} is the latest available.')
                    break

                logger.info(f"Processing: {guild_id} | {game_id} |#| {post['account']['identifier']} | [{post['id']}] {post['topic']}")

                # Skip the post if the guild wanted to ignore the author
                if post['account']['identifier'] in all_ignored_accounts[guild_id]:
                    logger.info(f"Skipped. ({post['account']['identifier']} is in the ignore list).")
                    continue

                em = self._generate_embed(post)
                embeds.append(em)
                embeds_size += len(em)

                # Only send the last post if none was sent before
                if not last_post_id:
                    break

                # Remove last embed if we're not repecting the Discords limits
                if len(embeds) > EMBEDS_MAX_AMOUNT or embeds_size > EMBEDS_MAX_TOTAL:
                    logger.warning("Discord Limits Reached, removing last embed.")
                    embeds.pop()
                    break

            if embeds:
                logger.info(f'Sending {len(embeds)} embeds from {len(ordered_posts)} posts.')
                try:
                    await channel.send(embeds=embeds)
                    post_id = ordered_posts[0]['id']
                    await ORM.set_last_post(post_id, guild_id, game_id)
                except disnake.Forbidden:
                    logger.warning(f"Missing permissions for #{channel.name}")
                    if default_channel_id and default_channel_id != channel.id:
                        default_channel = guild.get_channel(default_channel_id)
                        await default_channel.send(
                            f"I cant send the latest post for {game_id} in {channel.name}"
                        )
        logger.info('Refresh task completed.')

    @resfresh_posts.before_loop
    async def before_refresh(self):
        logger.info('Waiting before launching refresh tasks...')
        await self.bot.wait_until_ready()

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------
    # Trackers /
    # -------/

    @commands.slash_command(name="dt-follow", description="Add a game to follow.")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def follow_game(self, inter : disnake.AppCommandInteraction, game: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()

        game_ids = await API.fetch_available_games()
        if not game_ids:
            await inter.edit_original_message(f"It seems the DeveloperTracker.com API didn't respond.")
            return

        if game not in game_ids.keys():
            await inter.edit_original_message(f"`{game}` is either an invalid game or unsupported.")
        else:
            game_id = game_ids[game]

            await ORM.add_followed_game(game_id, inter.guild_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{game_id}" followed')

            msg = f'`{game}` has been added to following list.'
            default_channel_id = await ORM.get_main_channel(inter.guild_id)
            game_channel_id = await ORM.get_game_channel(game_id, inter.guild_id)
            channel_id = game_channel_id or default_channel_id
            if channel_id:
                msg += f" I'll post new entries in <#{channel_id}>. You should receive the last post in a few moments."
                # Fetch last post to show everything is working as intended
                await inter.edit_original_message(msg)
                await self._fetch_last_post(game_id, inter.guild.get_channel(channel_id), inter.guild)
            else:
                msg += " Please use `/dt-set-channel` to receive the latest posts."
                await inter.edit_original_message(msg)


    @commands.slash_command(name="dt-set-channel")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def set_channel(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @set_channel.sub_command(name="default", description="Set the default notification channel.")
    async def set_default_channel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):

        await inter.response.defer()

        await ORM.set_main_channel(channel.id, inter.guild_id)
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : #{channel.name} set as default channel')

        msg = f"<#{channel.id}> set as default channel.\n"

        bot_member = inter.guild.get_member(self.bot.user.id)
        perms = channel.permissions_for(bot_member)

        if not perms.view_channel:
            msg += "It seems I'm not allowed to view this channel, please check my permissions."
        elif not perms.send_messages:
            msg += "It seems I'm not allowed to send message in this channel, please check my permissions."
        await inter.edit_original_message(msg)

    @set_channel.sub_command(name="game", description="Set the notification channel per game. The game will be followed if it's not the case already.")
    async def set_game_channel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel, game: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()

        game_ids = await API.fetch_available_games()
        if not game_ids:
            await inter.edit_original_message(f"It seems the DeveloperTracker.com API didn't respond.")
            return

        if game not in game_ids.keys():
            await inter.edit_original_message(f"`{game}` is either an invalid game or unsupported.")
        else:
            game_id = game_ids[game]

            fw = await ORM.get_follow(inter.guild_id, game_id)
            if fw:
                await ORM.set_game_channel(channel.id, inter.guild_id, game_id)
            else:
                await ORM.add_fw_game_channel(channel.id, inter.guild_id, game_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : #{channel.name} set as channel for `{game}`')

            msg = f"<#{channel.id}> set as notification channel for `{game}`. You should receive the last post shortly.\n"

            bot_member = inter.guild.get_member(self.bot.user.id)
            perms = channel.permissions_for(bot_member)

            if not perms.view_channel:
                msg += "It seems I'm not allowed to view this channel, please check my permissions."
            elif not perms.send_messages:
                msg += "It seems I'm not allowed to send message in this channel, please check my permissions."

            await inter.edit_original_message(msg)

            # Fetch last post to show everything is working as intended
            await self._fetch_last_post(game_id, channel, inter.guild)


    @commands.slash_command(name="dt-mute-account", description="Ignore posts from a specific account.")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def mute_account(self, inter: disnake.ApplicationCommandInteraction, game: str = commands.Param(autocomplete=ac.games), account_id: str = commands.Param(autocomplete=ac.accounts_all)):

        await inter.response.defer()

        game_ids = await API.fetch_available_games()
        if not game_ids:
            await inter.edit_original_message(f"It seems the DeveloperTracker.com API didn't respond.")
            return

        if game not in game_ids.keys():
            await inter.edit_original_message(f"`{game}` is either an invalid game or unsupported.")
        else:
            game_id = game_ids[game]
            account_ids = await API.fetch_accounts(game_id)
            if account_id not in account_ids:
                await inter.edit_original_message(f"`{account_id}` doesn't exists or isn't followed for {game}.")
            else:
                await ORM.add_ignored_account(inter.guild_id, account_id)
                logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{account_id}" muted')
                await inter.edit_original_message(f'Posts from `{account_id}` will be ignored from now on.')

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------
    # Untrackers /
    # ---------/

    @commands.slash_command(name="dt-unfollow", description="Remove a game to the following list")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def unfollow_game(self, inter : disnake.ApplicationCommandInteraction, game: str = commands.Param(autocomplete=ac.games_fw)):

        await inter.response.defer()

        local_games = await ORM.get_local_games()
        game_id = [g[0] for g in local_games if g[1] == game][0]

        if not game_id:
            await inter.edit_original_message(f"`{game}` isn't in your following list.")
        else:
            await ORM.rm_followed_game(game_id, inter.guild_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{game_id}" unfollowed')
            msg = f'`{game}` has been removed from the following list.'
            await inter.edit_original_message(msg)

    @commands.slash_command(name="dt-unset-channel")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def unset_channel(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @unset_channel.sub_command(name="default", description="Unset the default notification channel.")
    async def unset_default_channel(self, inter: disnake.ApplicationCommandInteraction):

        await inter.response.defer()

        await ORM.unset_main_channel(inter.guild_id)
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : Default channel deleted')
        await inter.edit_original_message("You don't have a default channel anymore, make sure you have one set for each followed games using `/dt-status`.")

    @unset_channel.sub_command(name="game", description="Unset the notification channel per game.")
    async def unset_game_channel(self, inter: disnake.ApplicationCommandInteraction, game: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()

        local_games = await ORM.get_local_games()
        game_id = [g[0] for g in local_games if g[1] == game][0]

        if not game_id:
            await inter.edit_original_message("The game you entered isn't in your following list.")
        else:
            await ORM.unset_game_channel(inter.guild_id, game_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : Unset custom channel for `{game}`')
            await inter.edit_original_message(f"The notification channel for `{game}` is no longer set.")

    @commands.slash_command(name="dt-unmute-account", description="Unmute a previously ignored account.")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def unmute_account(self, inter, account_id: str = commands.Param(autocomplete=ac.accounts_ignored)):

        await inter.response.defer()
        account_ids = await ORM.get_ignored_accounts(inter.guild_id)
        if account_id not in account_ids:
            await inter.edit_original_message(f"`{account_id}` isn't in your ignore list.")
        else:
            await ORM.rm_ignored_account(inter.guild_id, account_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : "{account_id}" unmuted')
            await inter.edit_original_message(f'Posts from `{account_id}` will no longer be ignored.')

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------
    # Debug      /
    # ---------/

    @commands.slash_command(name="dt-force-send-post", description="[TECHNICAL] Debug bad formatted messages.", guild_ids=[687999396612407341])
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def force_fetch_last_post(self, inter : disnake.ApplicationCommandInteraction, post_id: str, game: str = commands.Param(autocomplete=ac.games)):

        await inter.response.defer()

        logger.info(f'Forcing fetch of {post_id}.')
        game_ids = await API.fetch_available_games()
        if game not in game_ids.keys():
            await inter.edit_original_message(f"`{game}` is either an invalid game or unsupported.")
        else:
            game_id = game_ids[game]
            post = await API.fetch_post(post_id, game_id)

            if not post:
                await inter.edit_original_message(f"I cannot fetch that post anymore.")
                return

            soup = BeautifulSoup(post[0]['content'], "html.parser")
            logger.debug(soup)
            logger.info(soup.prettify())
            if len(post) == 0:
                await inter.edit_original_message(f"`{post_id}` not found.")
            else:
                em = self._generate_embed(post[0])
                await inter.edit_original_message(embed=em)

    # ---------------------------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------------------------

    async def _fetch_last_post(self, game_id, channel, guild):

        post = await API.fetch_latest_post(game_id)

        if not post:
            logger.error('API didnt returned anything !')
            return

        em = self._generate_embed(post)
        post_id = post['id']
        logger.info(f'{guild.name} [{guild.id}] : Fetching {post_id} for "{game_id}". (Dest: `#{channel.name}`)')
        await channel.send(embed=em)
        await ORM.set_last_post(post_id, guild.id, game_id)

    async def _fetch_fw(self):
        follows = await ORM.get_all_follows()

        # Minimize calls on DBs/Disnake per guilds
        logger.info(f'{len(follows)} follows retrieved.')
        return sorted(follows, key=lambda fw: fw[2])

    async def _fetch_posts(self):
        fw_games_ids = await ORM.get_all_followed_games()
        nb_posts = 0
        res = await API.fetch_all_posts(fw_games_ids)

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

        err_msg = err_stats if err_stats else 'No errors.'
        logger.info(f'{nb_posts} posts retrieved ({err_msg}).')
        return posts

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
                    ellipsis = soup.new_tag('blockquote')

                    nb_char_stripped += len(bqs[-1].text) - 5
                    if bqs[-1].string == '[...]':
                        bqs[-1].decompose()
                        nb_blocquotes -= 1
                    else:
                        ellipsis = soup.new_tag('blockquote')
                        ellipsis.string = '[...]'
                        bqs[-1].clear()
                        bqs[-1].append('[...]')
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

        img_url = None
        imgs = soup.find_all('img')
        if len(imgs) > 0:
            img_url = imgs[-1]['src']

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
        acc_dev_nick = post['account']['developer']['nick']
        acc_dev_group = post['account']['developer']['group']

        author_text = f'{acc_dev_nick} [{acc_dev_group}]' if acc_dev_group else f'{acc_dev_nick}'
        footer_text = f"Account: {acc_id} | DT#: {post['id']}"

        footer_icon_url = "https://i33.servimg.com/u/f33/11/20/17/41/clipar10.png"
        field_topic = f"[{post['topic']}]({post['url']})"
        field_published = f"{str(datetime.fromtimestamp(post['timestamp']))} (UTC)"

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


def setup(bot: commands.Bot):
    bot.add_cog(Tracker(bot))
