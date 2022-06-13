import logging
import time

import sec
import aiohttp
from aiohttp_client_cache import CachedSession, SQLiteBackend


from cogs.utils import database as db
ORM = db.ORM()

logger = logging.getLogger('bot.API')

class API:

    _instances = {}

    def __init__(self):
        self.token = sec.load('api_token')
        self.cache = SQLiteBackend('api_cache')
        self.headers = {'Authorization': f'Bearer {self.token}'}
        self.api_baseurl =  sec.load('api_base')

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(API, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    async def get_status(self):
        url = f'{self.api_baseurl}/games'
        start = time.monotonic()

        async with CachedSession(cache=self.cache, headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    await resp.json()
                    response_time = time.monotonic() - start
                    return resp.status, response_time
            except aiohttp.ClientConnectorError as e:
                logger.error('Connection Error', str(e))

    async def fetch_available_games(self):
        url = f'{self.api_baseurl}/games'
        games = []

        async with CachedSession(cache=self.cache, headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    games = response['data']
                    api_games_data = [(g['identifier'], g['name']) for g in games]
                    await ORM.update_local_games(api_games_data)
                    games = api_games_data
            except aiohttp.ClientConnectorError as e:
                logger.error('Connection Error', str(e))
                games = await ORM.get_local_games()

        game_dict = {}
        for g in games:
            game_dict.update({
                g[1]: g[0]
            })
        return game_dict

    async def fetch_posts(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        async with CachedSession(cache=self.cache, headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    posts = response['data']
                    return posts

            except aiohttp.ClientConnectorError as e:
                logger.error('Connection Error', str(e))

    async def fetch_post(self, post_id ,game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        async with CachedSession(cache=self.cache, headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    content = await resp.json()
                    posts = content['data']
                    post = [p for p in posts if p['id'] == post_id]
                    return post
            except aiohttp.ClientConnectorError as e:
                logger.error('Connection Error', str(e))

    async def fetch_accounts(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/accounts'

        async with CachedSession(cache=self.cache, headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    accounts = response['data']
                    return [a['identifier'] for a in accounts]
            except aiohttp.ClientConnectorError as e:
                logger.error('Connection Error', str(e))
