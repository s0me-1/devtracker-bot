import logging
import re
from collections import defaultdict
from datetime import datetime

from bs4 import BeautifulSoup, NavigableString
import disnake
from disnake.ext import tasks, commands

from cogs.utils.services import CUSTOMIZERS
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
        self.resfresh_posts.start()
        logger.info("Loaded.")

    def cog_unload(self):
        self.resfresh_posts.cancel()
        ORM.close_connection()
        logger.info('Unloaded.')

    # ---------------------------------------------------------------------------------
    # TASKS
    # ---------------------------------------------------------------------------------

    @tasks.loop(minutes=10.0)
    async def resfresh_posts(self):

        logger.debug('Refreshing posts.')
        posts = self._fetch_posts()
        ordered_fws = self._fetch_fw()

        guild = None
        channel = None
        default_channel_id = None

        all_ignored_accounts = ORM.get_all_ignored_accounts()

        for last_post_id, channel_id, guild_id, game_id in ordered_fws:
            if not guild or guild.id != guild_id:
                default_channel_id = ORM.get_main_channel(guild_id)
                guild = self.bot.get_guild(guild_id)

            if channel_id:
                channel = guild.get_channel(channel_id)
            elif default_channel_id:
                channel = guild.get_channel(default_channel_id)
            else:
                logger.warning(f'{guild.name} [{guild.id}] follows {game_id} but hasnt set any channel')
                continue

            embeds = []
            embeds_size = 0
            for post in posts[game_id]:

                # Stop if we reach the post has already been sent (FIFO)
                if last_post_id == post['id']:
                    break

                logger.info(f"Processing: {guild_id} | {game_id} |#| {post['account']['identifier']} | [{post['id']}] {post['topic']}")

                # Skip the post if the guild wanted to ignore the author
                if post['account']['identifier'] in all_ignored_accounts[guild_id]:
                    continue

                em = self._generate_embed(post)
                embeds.append(em)
                embeds_size += len(em)

                # Only send the last post if none was sent before
                if not last_post_id:
                    break

                # Remove last embed if we're not repecting the Discords limits
                if len(embeds) > EMBEDS_MAX_AMOUNT or embeds_size > EMBEDS_MAX_TOTAL:
                    embeds.pop()
                    break

            post_id = posts[game_id][0]['id']
            ORM.set_last_post(post_id, guild_id, game_id)
            if embeds:
                try:
                    await channel.send(embeds=embeds)
                except disnake.Forbidden:
                    logger.warning(f"Missing permissions for #{channel.name}")
                    if default_channel_id and default_channel_id != channel.id:
                        default_channel = guild.get_channel(default_channel_id)
                        await default_channel.send(
                            f"I cant send the latest post for {game_id} in {channel.name}"
                        )

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
    async def follow_game(self, inter, game: str = commands.Param(autocomplete=ac.games)):

        game_ids = API.fetch_available_games()
        if game not in game_ids.keys():
            await inter.response.send_message(f"`{game}` is either an invalid game or unsupported.")
        else:
            game_id = game_ids[game]

            ORM.add_followed_game(game_id, inter.guild_id)
            msg = f'`{game}` has been added to following list.'
            default_channel_id = ORM.get_main_channel(inter.guild_id)
            game_channel_id = ORM.get_game_channel(game_id, inter.guild_id)
            channel_id = game_channel_id or default_channel_id
            if channel_id:
                msg += f" I'll post new entries in <#{channel_id}>"
            else:
                msg += " Please use `/dt-set-channel` to receive the latest posts."
            await inter.response.send_message(msg)

            # Restart Tracker main task to fetch first new post
            self.resfresh_posts.restart()

    @commands.slash_command(name="dt-set-channel")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def set_channel(self, inter):
        pass

    @set_channel.sub_command(name="default", description="Set the default notification channel.")
    async def set_default_channel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):

        ORM.set_main_channel(channel.id, inter.guild_id)
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : #{channel.name} set as default channel')

        await inter.response.send_message(
            f"<#{channel.id}> set as default channel.\n" \
            "Please make sure I have the permission to send messages in this channel."
        )

    @set_channel.sub_command(name="game", description="Set the notification channel per game. The game will be followed if it's not the case already.")
    async def set_game_channel(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel, game: str = commands.Param(autocomplete=ac.games)):

        game_ids = API.fetch_available_games()
        if game not in game_ids.keys():
            await inter.response.send_message(f"`{game}` is either an invalid game or unsupported.")
        else:
            game_id = game_ids[game]

            fw = ORM.get_follow(inter.guild_id, game_id)
            if fw:
                ORM.set_game_channel(channel.id, inter.guild_id, game_id)
            else:
                ORM.add_fw_game_channel(channel.id, inter.guild_id, game_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : #{channel.name} set as channel for `{game}`')

            await inter.response.send_message(
                f"<#{channel.id}> set as notification channel for `{game}`.\n" \
                "Please make sure I have the permissions to send in this channel."
            )

            # Restart Tracker main task to fetch first new post
            self.resfresh_posts.restart()

    # ---------------------------------------------------------------------------------
    # APPLICATION COMMANDS
    # ---------------------------------------------------------------------------------
    # Untrackers /
    # ---------/

    @commands.slash_command(name="dt-unfollow", description="Remove a game to the following list")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def unfollow_game(self, inter, game: str = commands.Param(autocomplete=ac.games)):

        local_games = ORM.get_local_games()
        game_id = [g[0] for g in local_games if g[1] == game][0]

        if not game_id:
            await inter.response.send_message(f"`{game}` isn't in your following list.")
        else:
            ORM.rm_followed_game(game_id, inter.guild_id)
            msg = f'`{game}` has been removed from the following list.'
            await inter.response.send_message(msg)

    @commands.slash_command(name="dt-unset-channel")
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def unset_channel(self, inter):
        pass

    @unset_channel.sub_command(name="default", description="Unset the default notification channel.")
    async def unset_default_channel(self, inter: disnake.ApplicationCommandInteraction):

        ORM.unset_main_channel(inter.guild_id)
        logger.info(f'{inter.guild.name} [{inter.guild_id}] : Default channel deleted')
        await inter.response.send_message("You don't have a default channel anymore, make sure you have one set for each followed games using `/dt-status`.")

    @unset_channel.sub_command(name="game", description="Unset the notification channel per game.")
    async def unset_game_channel(self, inter: disnake.ApplicationCommandInteraction, game: str = commands.Param(autocomplete=ac.games)):

        local_games = ORM.get_local_games()
        game_id = [g[0] for g in local_games if g[1] == game][0]

        if not game_id:
            await inter.response.send_message("The game you entered isn't in your following list.")
        else:
            ORM.unset_game_channel(inter.guild_id, game_id)
            logger.info(f'{inter.guild.name} [{inter.guild_id}] : Unset custom channel for `{game}`')
            await inter.response.send_message(f"The notification channel for `{game}` is no longer set.")

    @commands.slash_command(name="dt-force-send-post", description="[TECHNICAL] Debug bad formatted messages.", guild_ids=[687999396612407341])
    @commands.default_member_permissions(manage_guild=True, moderate_members=True)
    async def force_fetch_last_post(self, inter, post_id: str, game: str = commands.Param(autocomplete=ac.games)):

        logger.info(f'Forcing fetch of {post_id}.')
        game_ids = API.fetch_available_games()
        if game not in game_ids.keys():
            await inter.response.send_message(f"`{game}` is either an invalid game or unsupported.")
        else:
            game_id = game_ids[game]
            post = API.fetch_post(post_id, game_id)

            print(post)
            if len(post) == 0:
                await inter.response.send_message(f"`{post_id}` not found.")
            else:
                em = self._generate_embed(post[0])
                await inter.response.send_message(embed=em)

    # ---------------------------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------------------------

    def _fetch_fw(self):
        follows = ORM.get_all_follows()

        # Minimize calls on DBs/Disnake per guilds
        return sorted(follows, key=lambda fw: fw[2])

    def _fetch_posts(self):
        posts = defaultdict(dict)
        fw_games_ids = ORM.get_all_followed_games()
        for gid in fw_games_ids:
            posts[gid] = API.fetch_posts(gid)

        return posts

    def _sanitize_post_content(self, post_content, origin=None):

        if origin not in ['Twitter', ]:
            post_content = post_content.replace('\n', '')
        soup = BeautifulSoup(post_content, "html.parser")
        nb_char_overflow = len(soup.prettify()) - 2048

        # Fix blockquote from Spectrum
        if origin == 'rsi':
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
            # We try to remove the less text possible, ellipsising is interrupted as soon as we can
            while i < len(bqs) and nb_char_overflow > nb_char_stripped:
                bq = bqs[i]
                init_bq_size = len(bq.text)
                bq_ps = bq.findAll('p')

                if len(bq_ps) < 2 and len(bqs) > 1:
                    bqs[-1].decompose()
                    if len(bqs) > 2:
                        ellipsis = soup.new_tag('blockquote')
                        ellipsis.string = '[...]'
                        bqs[-2].insert_after(ellipsis)
                    nb_char_stripped += init_bq_size - len(bqs[-1].text)
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
        while re.search(r'\n>\s*\n>\s*\n>\s*\n>', body, re.MULTILINE):
            body_trimmed = re.sub(r'\n>\s*\n>\s*\n>\s*\n>', '\n> \n> ', body_trimmed)
        body_trimmed = re.sub(r'\n>\s*\n>\s*\n>', '\n> \n> ', body_trimmed)

        description = (body_trimmed[:2040] + '...') if len(body_trimmed) > 2045 else body_trimmed

        img_url = None
        img = soup.find('img')
        if img:
            img_url = img['src']

        return description, img_url

    def _generate_embed(self, post):

        service = post['account']['service']

        description, img_url = self._sanitize_post_content(post['content'], origin=service)
        color = CUSTOMIZERS[service]['color']
        author_icon_url = CUSTOMIZERS[service]['icon_url']

        acc_id = post['account']['identifier']
        acc_dev_nick = post['account']['developer']['nick']
        acc_dev_group = post['account']['developer']['group']

        author_text = f'{acc_dev_nick} [{acc_dev_group}]' if acc_dev_group else f'{acc_dev_nick}'
        footer_text = f"Account: {acc_id} | DT#: {post['id']}"

        footer_icon_url = "https://developertracker.com/star-citizen/favicon-32x32.png"
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
