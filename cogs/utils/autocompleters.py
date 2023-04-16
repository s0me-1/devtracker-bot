import disnake
import logging

# Call are done for every user input made, but
# API requests should be cached so it should not be an issue
from cogs.utils import api
from cogs.utils import database as db


API = api.API()
ORM = db.ORM()

logger = logging.getLogger('bot.utils.AutoCompleters')

# Discord supports 25 choices max,
# so auto-completers can't return more than 25 elements

async def games(inter: disnake.ApplicationCommandInteraction, user_input: str):
    try:
        games = await API.fetch_available_games()
        max_list = [g for g in games.keys() if user_input.lower() in g.lower()]
        if len(max_list) == 0:
            return ['[ERROR] API didn\'t return any game, retry later.']
        return max_list[0:24]
    except Exception as e:
        logger.error(e)
        return ['[ERROR] API request failed. Retry later.']


async def games_fw(inter: disnake.ApplicationCommandInteraction, user_input: str):
    fw_game_ids = await ORM.get_followed_games(inter.guild_id)
    max_list = [g for g in fw_game_ids.keys() if (user_input.lower() in g.lower())]
    if len(max_list) == 0:
        return ['[ERROR] You are not following any game']
    return max_list[0:24]

async def accounts_all(inter: disnake.ApplicationCommandInteraction, user_input: str):
    try:
        games = await API.fetch_available_games()
        if 'game_name' not in inter.options['add']['account'].keys():
            return ['[ERROR] Please select a game first']
        if inter.options['add']['account']['game_name'] not in games.keys():
            return ['[ERROR] Invalid game provided']
        game_id = games[inter.options['add']['account']['game_name']]
        if 'service_id' not in inter.options['add']['account'].keys():
            return ['[ERROR] Please provide a valid service first']
        service_id = inter.options['add']['account']['service_id']
        services = await API.fetch_services(game_id)
        if service_id not in services:
            return ['[ERROR] Invalid service provided']
        accounts = await API.fetch_accounts(game_id)

        account_ids = [a['identifier'] for a in accounts if a['service'] == service_id]
        max_list = [acc_id for acc_id in account_ids if user_input.lower() in acc_id.lower()]
        return max_list[0:24]
    except Exception as e:
        logger.error(e)
        return ['[ERROR] API request failed. Retry later.']

async def accounts_service_all(inter: disnake.ApplicationCommandInteraction, user_input: str):
    try:
        games = await API.fetch_available_games()
        if 'game_name' not in inter.options['add']['account'].keys():
            return ['[ERROR] Please select a game first']
        if inter.options['add']['account']['game_name'] not in games.keys():
            return ['[ERROR] Invalid game provided']
        game_id = games[inter.options['add']['account']['game_name']]
        services = await API.fetch_services(game_id)

        max_list = [serv_id for serv_id in services if user_input.lower() in serv_id.lower()]
        return max_list[0:24]
    except Exception as e:
        logger.error(e)
        return ['[ERROR] API request failed. Retry later.']

async def accounts_ignored(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await ORM.get_followed_games(inter.guild_id)
    if 'game_name' not in inter.options['remove']['account'].keys():
        return ['[ERROR] Please select a game first']
    if inter.options['remove']['account']['game_name'] not in games.keys():
        return ['[ERROR] Invalid game provided']
    game_id = games[inter.options['remove']['account']['game_name']]

    account_ids = await ORM.get_ignored_accounts(inter.guild_id, game_id)
    max_list = [acc_id for acc_id in account_ids if user_input.lower() in acc_id.lower()]
    return max_list[0:24]

async def accounts_allowed(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await ORM.get_followed_games(inter.guild_id)
    if 'game_name' not in inter.options['remove']['account'].keys():
        return ['[ERROR] Please select a game first']
    if inter.options['remove']['account']['game_name'] not in games.keys():
        return ['[ERROR] Invalid game provided']
    game_id = games[inter.options['remove']['account']['game_name']]

    account_ids = await ORM.get_allowed_accounts(inter.guild_id, game_id)
    max_list = [acc_id for acc_id in account_ids if user_input.lower() in acc_id.lower()]
    return max_list[0:24]

async def services_all(inter: disnake.ApplicationCommandInteraction, user_input: str):
    try:
        games = await API.fetch_available_games()
        if 'game_name' not in inter.options['add']['service'].keys():
            return ['[ERROR] Please select a game first']
        if inter.options['add']['service']['game_name'] not in games.keys():
            return ['[ERROR] Invalid game provided']
        game_id = games[inter.options['add']['service']['game_name']]
        service_ids = await API.fetch_services(game_id)
        max_list = [serv_id for serv_id in service_ids if not user_input or user_input.lower() in serv_id.lower()]
        return max_list[0:24]
    except Exception as e:
        logger.error(e)
        return ['[ERROR] API request failed. Retry later.']

async def services_urlfilters_all(inter: disnake.ApplicationCommandInteraction, user_input: str):
    try:
        games = await API.fetch_available_games()
        if 'game_name' not in inter.options['global'].keys():
            return ['[ERROR] Please select a game first']
        if inter.options['global']['game_name'] not in games.keys():
            return ['[ERROR] Invalid game provided']
        game_id = games[inter.options['global']['game_name']]
        service_ids = await API.fetch_services(game_id)
        max_list = [serv_id for serv_id in service_ids if not user_input or user_input.lower() in serv_id.lower()]
        return max_list[0:24]
    except Exception as e:
        logger.error(e)
        return ['[ERROR] API request failed. Retry later.']

async def services_urlfilters_channel(inter: disnake.ApplicationCommandInteraction, user_input: str):
    try:
        games = await API.fetch_available_games()
        if 'game_name' not in inter.options['channel'].keys():
            return ['[ERROR] Please select a game first']
        if inter.options['channel']['game_name'] not in games.keys():
            return ['[ERROR] Invalid game provided']
        game_id = games[inter.options['channel']['game_name']]
        service_ids = await API.fetch_services(game_id)
        max_list = [serv_id for serv_id in service_ids if not user_input or user_input.lower() in serv_id.lower()]
        return max_list[0:24]
    except Exception as e:
        logger.error(e)
        return ['[ERROR] API request failed. Retry later.']

async def services_urlfilters_thread(inter: disnake.ApplicationCommandInteraction, user_input: str):
    try:
        games = await API.fetch_available_games()
        if 'game_name' not in inter.options['thread'].keys():
            return ['[ERROR] Please select a game first']
        if inter.options['thread']['game_name'] not in games.keys():
            return ['[ERROR] Invalid game provided']
        game_id = games[inter.options['thread']['game_name']]
        service_ids = await API.fetch_services(game_id)
        max_list = [serv_id for serv_id in service_ids if not user_input or user_input.lower() in serv_id.lower()]
        return max_list[0:24]
    except Exception as e:
        logger.error(e)
        return ['[ERROR] API request failed. Retry later.']

async def services_urlfilters_clear(inter: disnake.ApplicationCommandInteraction, user_input: str):
    try:
        games = await API.fetch_available_games()
        if 'game_name' not in inter.options['clear'].keys():
            return ['[ERROR] Please select a game first']
        if inter.options['clear']['game_name'] not in games.keys():
            return ['[ERROR] Invalid game provided']
        game_id = games[inter.options['clear']['game_name']]
        service_ids = await API.fetch_services(game_id)
        max_list = [serv_id for serv_id in service_ids if not user_input or user_input.lower() in serv_id.lower()]
        return max_list[0:24]
    except Exception as e:
        logger.error(e)
        return ['[ERROR] API request failed. Retry later.']

async def service_ignored(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await ORM.get_followed_games(inter.guild_id)
    if 'game_name' not in inter.options['remove']['service'].keys():
        return ['[ERROR] Please select a game first']
    if inter.options['remove']['service']['game_name'] not in games.keys():
        return ['[ERROR] Invalid game provided']
    game_id = games[inter.options['remove']['service']['game_name']]

    service_ids = await ORM.get_ignored_services(inter.guild_id, game_id)
    max_list = [serv_id for serv_id in service_ids if not user_input or user_input.lower() in serv_id.lower()]
    return max_list[0:24]

async def service_allowed(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await ORM.get_followed_games(inter.guild_id)
    if 'game_name' not in inter.options['remove']['service'].keys():
        return ['[ERROR] Please select a game first']
    if inter.options['remove']['service']['game_name'] not in games.keys():
        return ['[ERROR] Invalid game provided']
    game_id = games[inter.options['remove']['service']['game_name']]

    service_ids = await ORM.get_allowed_services(inter.guild_id, game_id)
    max_list = [serv_id for serv_id in service_ids if not user_input or user_input.lower() in serv_id.lower()]
    return max_list[0:24]
