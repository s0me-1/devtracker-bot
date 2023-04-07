import logging
import time
import aiohttp

import sec
from aiohttp import ClientSession, ClientConnectorError, ClientTimeout, ContentTypeError
import asyncio


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
                    logger.debug(f'GET {url} {resp.status}')
                    response_time = time.monotonic() - start
                    return resp.status, response_time
            except ClientConnectorError as e:
                logger.error(str(e))

    async def fetch_available_games(self):
        url = f'{self.api_baseurl}/games'
        games = []

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    logger.debug(f'GET {url} {resp.status}')
                    games = response['data']
                    api_games_data = [(g['identifier'], g['name']) for g in games]
                    games = api_games_data
            except ClientConnectorError as e:
                logger.error(str(e))
                games = None

        game_dict = {}
        for g in games:
            game_dict.update({
                g[1]: g[0]
            })
        return game_dict

    async def fetch_posts(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        timeout = ClientTimeout(total=15)
        async with ClientSession(headers=self.headers, timeout=timeout) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    logger.debug(f'GET {url} {resp.status}')
                    posts = response['data']
                    return {game_id: posts}

            except asyncio.TimeoutError as e:
                logger.warning(f'GET {url} | Timeout ({session.timeout})')
                return {game_id: 'timeout'}

            except aiohttp.ContentTypeError as e:
                # This likely means the API Endpoint crashed and gave
                # an HTML fallback response instead of JSON.
                logger.error(f'GET {url} | ContentTypeError: {e.message}.')
                return {game_id: 'content_type_error'}

            except Exception as e:
                logger.error(f'Unhandled: {repr(e)}')
                return {game_id: e}

    async def fetch_all_posts(self, game_ids):

        timeout = ClientTimeout(total=60)
        async with ClientSession(headers=self.headers, timeout=timeout) as session:
            try:
                res = await asyncio.gather(
                *[
                        self.fetch_posts(gid)
                        for gid in game_ids
                    ],
                    return_exceptions=True
                )
                return res

            except asyncio.TimeoutError as e:
                logger.error(f'TIMEOUT: The Fetchs posts process took more than {timeout.total} seconds.')
                return None

    async def fetch_post(self, post_id ,game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    content = await resp.json()
                    logger.debug(f'GET {url} {resp.status}')
                    posts = content['data']
                    post = [p for p in posts if p['id'] == post_id]
                    return post
            except ClientConnectorError as e:
                logger.error(str(e))

    async def fetch_latest_post(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    content = await resp.json()
                    logger.debug(f'GET {url} {resp.status}')
                    posts = content['data']
                    return posts[0]
            except ClientConnectorError as e:
                logger.error(str(e))

    async def fetch_accounts(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/accounts'

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    logger.debug(f'GET {url} {resp.status}')
                    accounts = response['data']
                    return accounts
            except ClientConnectorError as e:
                logger.error(str(e))

    async def fetch_all_accounts(self, game_ids):

        timeout = ClientTimeout(total=60)
        async with ClientSession(headers=self.headers, timeout=timeout) as session:
            try:
                res = await asyncio.gather(
                *[
                        self.fetch_accounts(gid)
                        for gid in game_ids
                    ],
                    return_exceptions=True
                )
                return res

            except asyncio.TimeoutError as e:
                logger.error(f'TIMEOUT: The Fetchs accounts process took more than {timeout.total} seconds.')
                return None

    async def fetch_services(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/accounts'

        async with ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as resp:
                    response = await resp.json()
                    logger.debug(f'GET {url} {resp.status}')
                    accounts = response['data']
                    services = [a['service'] for a in accounts]
                    return set(services)
            except ClientConnectorError as e:
                logger.error(str(e))
