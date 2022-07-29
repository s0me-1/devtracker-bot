from collections import defaultdict
from email.policy import default
import disnake

# Call are done for every user input made, but
# API requests should be cached so it should not be an issue
from cogs.utils import api
API = api.API()

from cogs.utils import database as db
ORM = db.ORM()


# Discord supports 25 choices max,
# so auto-completers can't return more than 25 elements

async def games(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await API.fetch_available_games()
    max_list = [g for g in games.keys() if user_input.lower() in g.lower()]
    return max_list[0:24]

async def games_fw(inter: disnake.ApplicationCommandInteraction, user_input: str):
    fw_game_ids = await ORM.get_followed_games(inter.guild_id)
    max_list = [g for g in fw_game_ids.keys() if (user_input.lower() in g.lower())]
    return max_list[0:24]

async def accounts_all(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await API.fetch_available_games()
    if inter.options['account']['game_name'] not in games.keys():
        return ['[ERROR] Invalid game provided']
    game_id = games[inter.options['account']['game_name']]
    account_ids = await API.fetch_accounts(game_id)
    max_list = [acc_id for acc_id in account_ids if user_input.lower() in acc_id.lower()]
    return max_list[0:24]

async def accounts_ignored(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await ORM.get_followed_games(inter.guild_id)
    if inter.options['account']['game_name'] not in games.keys():
        return ['[ERROR] Invalid game provided']
    game_id = games[inter.options['account']['game_name']]

    account_ids = await ORM.get_ignored_accounts(inter.guild_id, game_id)
    max_list = [acc_id for acc_id in account_ids if user_input.lower() in acc_id.lower()]
    return max_list[0:24]

async def services_all(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await API.fetch_available_games()
    if inter.options['service']['game_name'] not in games.keys():
        return ['[ERROR] Invalid game provided']
    game_id = games[inter.options['service']['game_name']]
    service_ids = await API.fetch_services(game_id)
    max_list = [serv_id for serv_id in service_ids if user_input.lower() in serv_id.lower()]
    return max_list[0:24]

async def service_ignored(inter: disnake.ApplicationCommandInteraction, user_input: str):
    games = await ORM.get_followed_games(inter.guild_id)
    if inter.options['service']['game_name'] not in games.keys():
        return ['[ERROR] Invalid game provided']
    game_id = games[inter.options['service']['game_name']]

    service_ids = await ORM.get_ignored_services(inter.guild_id, game_id)
    max_list = [serv_id for serv_id in service_ids if user_input.lower() in serv_id.lower()]
    return max_list[0:24]
