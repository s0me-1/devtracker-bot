import logging
import time

import sec
from aiohttp import ClientSession, ClientConnectorError

from cogs.utils import database as db
ORM = db.ORM()

logger = logging.getLogger('bot.API')

class API:

    _instances = {}

    def __init__(self):
        self.token = sec.load('api_token')
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Cache-Control': 'no-cache'
        }
        self.api_baseurl =  sec.load('api_base')

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(API, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    async def get_status(self):
        url = f'{self.api_baseurl}/games'
        start = time.monotonic()

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    await resp.json()
                    logger.info(f'GET {url} {resp.status}')
                    response_time = time.monotonic() - start
                    return resp.status, response_time
            except ClientConnectorError as e:
                logger.error('Connection Error', str(e))

    async def fetch_available_games(self):
        url = f'{self.api_baseurl}/games'
        games = []

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    logger.info(f'GET {url} {resp.status}')
                    games = response['data']
                    api_games_data = [(g['identifier'], g['name']) for g in games]
                    await ORM.update_local_games(api_games_data)
                    games = api_games_data
            except ClientConnectorError as e:
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

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    logger.info(f'GET {url} {resp.status}')
                    posts = response['data']
                    return posts

            except ClientConnectorError as e:
                logger.error('Connection Error', str(e))

    async def fetch_post(self, post_id ,game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    content = await resp.json()
                    logger.info(f'GET {url} {resp.status}')
                    posts = content['data']
                    post = [p for p in posts if p['id'] == post_id]
                    return post
            except ClientConnectorError as e:
                logger.error('Connection Error', str(e))

    async def fetch_latest_post(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    content = await resp.json()
                    logger.info(f'GET {url} {resp.status}')
                    posts = content['data']
                    return posts[0]
            except ClientConnectorError as e:
                logger.error('Connection Error', str(e))

    async def fetch_accounts(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/accounts'

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    logger.info(f'GET {url} {resp.status}')
                    accounts = response['data']
                    return [a['identifier'] for a in accounts]
            except ClientConnectorError as e:
                logger.error('Connection Error', str(e))
