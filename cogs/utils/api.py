import logging

import sec
import requests
import requests_cache
requests_cache.install_cache('api_cache', backend='sqlite', expire_after=180)


from cogs.utils import database as db
ORM = db.ORM()

logger = logging.getLogger('bot.API')

class API:

    _instances = {}

    def __init__(self):
        token = sec.load('api_token')
        self.headers = {'Authorization': f'Bearer {token}'}
        self.api_baseurl =  sec.load('api_base')

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(API, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def get_status(self):
        url = f'{self.api_baseurl}/games'
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.status_code, response.elapsed.total_seconds()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error while connecting to {url}: {e}, falling back to database")
            return 500

    def fetch_available_games(self):
        url = f'{self.api_baseurl}/games'

        games = []
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            data = response.json()['data']
            api_games_data = [(g['identifier'], g['name']) for g in data]
            ORM.update_local_games(api_games_data)
            games = api_games_data
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error while connecting to {url}: {e}, falling back to database")
            games = ORM.get_local_games()

        game_dict = {}
        for g in games:
            game_dict.update({
                g[1]: g[0]
            })
        return game_dict

    def fetch_posts(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()['data']
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error while fetching posts {url}: {e}")

    def fetch_post(self, post_id ,game_id):
        url = f'{self.api_baseurl}/{game_id}/posts'

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            posts = response.json()['data']
            post = [p for p in posts if p['id'] == post_id]
            return post
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error while fetching posts {url}: {e}")

    def fetch_accounts(self, game_id):
        url = f'{self.api_baseurl}/{game_id}/accounts'

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            accounts = response.json()['data']
            return [a['identifier'] for a in accounts]
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error while fetching posts {url}: {e}")
