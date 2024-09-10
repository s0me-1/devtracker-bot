from collections import defaultdict
import aiosqlite
import logging

from cogs.utils import api
API = api.API()

logger = logging.getLogger('bot.DB')

DB_FILE = 'db/tracking.db'


class ORM:

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(ORM, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    async def initialize(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS guilds (
                    id INTEGER PRIMARY KEY,
                    main_channel_id INTEGER
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS follows (
                    last_post_id NVARCHAR,
                    channel_id INTEGER,
                    follower_guild_id INTEGER NOT NULL,
                    followed_game_id NVARCHAR NOT NULL,
                    FOREIGN KEY (follower_guild_id) REFERENCES guilds (id) ON DELETE CASCADE,
                    FOREIGN KEY (followed_game_id) REFERENCES games (id) ON DELETE CASCADE,
                    PRIMARY KEY (follower_guild_id, followed_game_id)
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    id NVARCHAR PRIMARY KEY,
                    name NVARCHAR
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS ignored_services (
                    follower_guild_id NOT NULL,
                    game_id NOT NULL,
                    service_id NOT NULL,
                    FOREIGN KEY (follower_guild_id) REFERENCES guilds (id) ON DELETE CASCADE
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                    PRIMARY KEY (follower_guild_id, game_id, service_id)
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS ignored_accounts (
                    follower_guild_id NOT NULL,
                    game_id NOT NULL,
                    account_id NOT NULL,
                    service_id NOT NULL,
                    FOREIGN KEY (follower_guild_id) REFERENCES guilds (id) ON DELETE CASCADE
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                    PRIMARY KEY (follower_guild_id, game_id, account_id)
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS allowed_services (
                    follower_guild_id NOT NULL,
                    game_id NOT NULL,
                    service_id NOT NULL,
                    FOREIGN KEY (follower_guild_id) REFERENCES guilds (id) ON DELETE CASCADE
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                    PRIMARY KEY (follower_guild_id, game_id, service_id)
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS allowed_accounts (
                    follower_guild_id NOT NULL,
                    game_id NOT NULL,
                    account_id NOT NULL,
                    service_id NOT NULL,
                    FOREIGN KEY (follower_guild_id) REFERENCES guilds (id) ON DELETE CASCADE
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                    PRIMARY KEY (follower_guild_id, game_id, account_id)
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS url_filters (
                    follower_guild_id NOT NULL,
                    game_id NOT NULL,
                    service_id NVARCHAR NOT NULL,
                    filters TEXT NOT NULL,
                    channel_id INTEGER,
                    thread_id INTEGER,
                    FOREIGN KEY (follower_guild_id) REFERENCES guilds (id) ON DELETE CASCADE
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                    PRIMARY KEY (follower_guild_id, game_id, service_id, channel_id, thread_id)
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    game_id NVARCHAR NOT NULL,
                    post_id NVARCHAR NOT NULL,
                    FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
                );
            ''')
            await conn.commit()
        await self.reset_account_services()

    async def add_guild(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "INSERT OR IGNORE INTO guilds ('id', 'main_channel_id') VALUES (?, ?);"
            params = (guild_id, None)

            await conn.execute(query, params)
            await conn.commit()

    async def rm_guild(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)
            await conn.execute("PRAGMA foreign_keys = 1")

            query = "DELETE FROM guilds WHERE id = ?;"
            params = (guild_id,)

            await conn.execute(query, params)
            await conn.commit()

    async def dump_guilds(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT id, main_channel_id FROM guilds"

            async with conn.execute(query) as cr:
                async for row in cr:
                    print(tuple(row))

    async def get_all_guilds(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT id FROM guilds;"

            guilds = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    guilds.append(row['id'])
            return guilds

    async def add_followed_game(self, game_id, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "INSERT OR IGNORE INTO follows ('last_post_id', 'channel_id', 'follower_guild_id', 'followed_game_id' ) VALUES (?, ?, ?, ?);"
            params = (None, None, guild_id, game_id)

            await conn.execute(query, params)
            await conn.commit()

    async def rm_followed_game(self, game_id, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)
            await conn.execute("PRAGMA foreign_keys = 1")

            params = (game_id, guild_id)
            query = "DELETE FROM follows WHERE followed_game_id = ? AND follower_guild_id = ?;"
            await conn.execute(query, params)

            # Clean lists
            query = "DELETE FROM ignored_services WHERE game_id = ? AND follower_guild_id = ?;"
            await conn.execute(query, params)
            query = "DELETE FROM ignored_accounts WHERE game_id = ? AND follower_guild_id = ?;"
            await conn.execute(query, params)
            query = "DELETE FROM allowed_services WHERE game_id = ? AND follower_guild_id = ?;"
            await conn.execute(query, params)
            query = "DELETE FROM allowed_accounts WHERE game_id = ? AND follower_guild_id = ?;"
            await conn.execute(query, params)

            await conn.commit()

    async def dump_follows(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT * FROM follows;"

            async with conn.execute(query) as cr:
                async for row in cr:
                    print(tuple(row))

    async def get_follow_status(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)
            game_names = []
            async with conn.execute("SELECT g.id,g.name,fw.channel_id,fw.last_post_id FROM games AS g INNER JOIN follows AS fw ON g.id = fw.followed_game_id WHERE fw.follower_guild_id = ? ;", (guild_id,)) as cr:
                async for row in cr:
                    game_names.append(tuple(row))
            return game_names

    async def get_follow(self, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT * FROM follows WHERE follower_guild_id = ? AND followed_game_id = ?;"
            params = (guild_id, game_id)

            follows = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    follows.append(tuple(row))
            return follows[0] if follows else None

    async def get_follows(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT * FROM follows WHERE follower_guild_id = ?;"
            params = (guild_id,)

            follows = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    follows.append(tuple(row))
            return follows

    async def get_all_follows(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT * FROM follows;"

            follows = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    follows.append(tuple(row))
            return follows

    async def set_last_post(self, post_id, guild_id, game_id):
        logger.debug(f"{guild_id}: Set {post_id} as last `{game_id}` post.")
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "UPDATE follows SET last_post_id = ? WHERE follower_guild_id = ? AND followed_game_id = ?;"
            params = (post_id, guild_id, game_id)

            await conn.execute(query, params)
            await conn.commit()

    async def reset_account_services(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            async def _get_query_params(accounts):
                params = []

                game_ids = set([game_id for _, game_id, _, _ in accounts])
                followable_accounts = await API.fetch_all_accounts(game_ids)
                if not followable_accounts:
                    logger.error(f'Could not fetch accounts for {game_ids}')
                    return None
                service_per_game_per_account = defaultdict(dict)
                for game_idx, followable_accounts_per_game in enumerate(followable_accounts):
                    game_id = list(game_ids)[game_idx]
                    for account in followable_accounts_per_game:
                        service_per_game_per_account[game_id][account['identifier']] = account['service']

                for guild_id, game_id, account_id, service_id in accounts:

                    service_id_detected = service_per_game_per_account[game_id].get(account_id, None)
                    if service_id_detected:
                        params.append((service_id_detected, account_id))
                return params

            ignored_accounts = await self.get_all_ignored_accounts()
            allowed_accounts = await self.get_all_allowed_accounts()

            params_ignored = await _get_query_params(ignored_accounts)
            params_allowed = await _get_query_params(allowed_accounts)
            if not params_ignored or not params_allowed:
                logger.error('No params received. Aborting accounts reset.')
                return
            query_ignored = "UPDATE ignored_accounts SET service_id = ? WHERE account_id = ?;"
            query_allowed = "UPDATE allowed_accounts SET service_id = ? WHERE account_id = ?;"
            await conn.executemany(query_ignored, params_ignored)
            await conn.executemany(query_allowed, params_allowed)

            await conn.commit()

    async def set_main_channel(self, channel_id, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "UPDATE guilds SET main_channel_id = ? WHERE id = ?;"
            params = (channel_id, guild_id)

            await conn.execute(query, params)
            await conn.commit()

    async def unset_main_channel(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "UPDATE guilds SET main_channel_id = ? WHERE id = ?;"
            params = (None, guild_id)

            await conn.execute(query, params)
            await conn.commit()

    async def get_main_channel(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT main_channel_id FROM guilds WHERE id = ?;"
            params = (guild_id,)

            async with conn.execute(query, params) as cr:
                async for row in cr:
                    return row['main_channel_id']
            return None

    async def set_game_channel(self, channel_id, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "UPDATE follows SET channel_id = ? WHERE follower_guild_id = ? AND followed_game_id = ?;"
            params = (channel_id, guild_id, game_id)

            await conn.execute(query, params)
            await conn.commit()

    async def add_fw_game_channel(self, channel_id, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "INSERT OR IGNORE INTO follows ('last_post_id', 'channel_id', 'follower_guild_id', 'followed_game_id' ) VALUES (?, ?, ?, ?);"
            params = (None, channel_id, guild_id, game_id)

            await conn.execute(query, params)
            await conn.commit()

    async def unset_game_channel(self, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "UPDATE follows SET channel_id = ? WHERE follower_guild_id = ? AND followed_game_id = ?;"
            params = (None, guild_id, game_id)

            await conn.execute(query, params)
            await conn.commit()

    async def get_game_channel(self, game_id, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            # Check if a channel is set per game
            query = "SELECT channel_id FROM follows WHERE followed_game_id = ? AND follower_guild_id = ?;"
            params = (game_id, guild_id)

            async with conn.execute(query, params) as cr:
                async for row in cr:
                    return row['channel_id']
            return None

    async def get_local_games(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT * FROM games;"

            api_games_ids = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    api_games_ids.append(tuple(row))

            return api_games_ids

    async def update_local_games(self, api_games: tuple):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)
            await conn.execute("PRAGMA foreign_keys = 1")

            query = "SELECT id FROM games"

            db_games_ids = set()
            async with conn.execute(query) as cr:
                async for row in cr:
                    db_games_ids.add(row['id'])

            api_games_ids = {game[0] for game in api_games}

            to_rem = db_games_ids.difference(api_games_ids)
            to_rem = [set(id) for id in to_rem]
            if to_rem:
                query = "DELETE FROM games WHERE id IN ?;"
                await conn.executemany(query, to_rem)
                await conn.commit()

            to_add = api_games_ids.difference(db_games_ids)
            to_add = [game for game in api_games if game[0] in to_add]
            if to_add:
                query = "INSERT OR IGNORE INTO games ('id', 'name') VALUES (?, ?);"
                await conn.executemany(query, to_add)
                await conn.commit()

    async def get_followed_games(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT g.name,g.id FROM games AS g INNER JOIN follows AS fw ON g.id = fw.followed_game_id WHERE fw.follower_guild_id = ? ;"
            params = (guild_id,)

            followed_games_ids = {}
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    followed_games_ids.update({
                        row[0]: row[1]
                    })

            return followed_games_ids

    async def get_all_followed_games(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT followed_game_id FROM follows;"

            followed_games_ids = set()
            async with conn.execute(query) as cr:
                async for row in cr:
                    followed_games_ids.add(row['followed_game_id'])

            logger.debug(f'Followed Games: {followed_games_ids}')
            return followed_games_ids

    async def get_all_ignored_accounts_per_guild(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT follower_guild_id,game_id,account_id FROM ignored_accounts;"

            ignored_accounts = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    ignored_accounts.append(tuple(row))

            ignored_per_guild = defaultdict(lambda: defaultdict(list))
            for guild_id, game_id, account_id in ignored_accounts:
                ignored_per_guild[guild_id][game_id].append(account_id)

            return ignored_per_guild

    async def get_all_ignored_accounts(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT follower_guild_id,game_id,account_id,service_id FROM ignored_accounts;"

            ignored_accounts = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    ignored_accounts.append(tuple(row))

            return ignored_accounts

    async def get_all_allowed_accounts_per_guild(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT follower_guild_id,game_id,account_id FROM allowed_accounts;"

            allowed_accounts = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    allowed_accounts.append(tuple(row))

            allowed_per_guild = defaultdict(lambda: (defaultdict(list)))
            for guild_id, game_id, account_id in allowed_accounts:
                allowed_per_guild[guild_id][game_id].append(account_id)

            return allowed_per_guild

    async def get_all_allowed_accounts(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT follower_guild_id,game_id,account_id, service_id FROM allowed_accounts;"

            allowed_accounts = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    allowed_accounts.append(tuple(row))

            return allowed_accounts

    async def get_all_ignored_services(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT follower_guild_id,game_id,service_id FROM ignored_services;"

            ignored_services = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    ignored_services.append(tuple(row))

            ignored_per_guild = defaultdict(lambda: defaultdict(list))
            for guild_id, game_id, service_id in ignored_services:
                ignored_per_guild[guild_id][game_id].append(service_id)

            return ignored_per_guild

    async def get_all_allowed_services(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT follower_guild_id,game_id,service_id FROM allowed_services;"

            allowed_services = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    allowed_services.append(tuple(row))

            allowed_per_guild = defaultdict(lambda: defaultdict(list))
            for guild_id, game_id, service_id in allowed_services:
                allowed_per_guild[guild_id][game_id].append(service_id)

            return allowed_per_guild

    async def add_ignored_account(self, guild_id, game_id, account_id, service_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "INSERT OR IGNORE INTO ignored_accounts ('follower_guild_id', 'game_id', 'account_id', 'service_id') VALUES (?, ?, ?, ?);"
            params = (guild_id, game_id, account_id, service_id)

            await conn.execute(query, params)
            await conn.commit()

    async def add_allowed_account(self, guild_id, game_id, account_id, service_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "INSERT OR IGNORE INTO allowed_accounts ('follower_guild_id', 'game_id', 'account_id', 'service_id') VALUES (?, ?, ?, ?);"
            params = (guild_id, game_id, account_id, service_id)

            await conn.execute(query, params)
            await conn.commit()

    async def add_ignored_service(self, guild_id, game_id, service_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "INSERT OR IGNORE INTO ignored_services ('follower_guild_id', 'game_id', 'service_id') VALUES (?, ?, ?);"
            params = (guild_id, game_id, service_id)

            await conn.execute(query, params)
            await conn.commit()

    async def add_allowed_service(self, guild_id, game_id, service_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "INSERT OR IGNORE INTO allowed_services ('follower_guild_id', 'game_id', 'service_id') VALUES (?, ?, ?);"
            params = (guild_id, game_id, service_id)

            await conn.execute(query, params)
            await conn.commit()

    async def get_ignored_accounts(self, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT account_id FROM ignored_accounts WHERE follower_guild_id = ? AND game_id = ? ;"
            params = (guild_id, game_id)

            ignored_accounts = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    ignored_accounts.append(row['account_id'])

            return ignored_accounts

    async def get_allowed_accounts(self, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT account_id FROM allowed_accounts WHERE follower_guild_id = ? AND game_id = ? ;"
            params = (guild_id, game_id)

            allowed_accounts = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    allowed_accounts.append(row['account_id'])

            return allowed_accounts

    async def get_ignored_services(self, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT service_id FROM ignored_services WHERE follower_guild_id = ? AND game_id = ? ;"
            params = (guild_id, game_id)

            ignored_services = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    ignored_services.append(row['service_id'])

            return ignored_services

    async def get_allowed_services(self, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT service_id FROM allowed_services WHERE follower_guild_id = ? AND game_id = ? ;"
            params = (guild_id, game_id)

            allowed_services = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    allowed_services.append(row['service_id'])

            return allowed_services

    async def get_ignored_accounts_per_game(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT game_id,account_id FROM ignored_accounts WHERE follower_guild_id = ? ;"
            params = (guild_id,)

            ignored_accounts = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    ignored_accounts.append(tuple(row))

            ignored_accounts_per_game = defaultdict(list)
            for game_id, account_id in ignored_accounts:
                ignored_accounts_per_game[game_id].append(account_id)

            return ignored_accounts_per_game

    async def get_allowed_accounts_per_game(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT game_id,account_id FROM allowed_accounts WHERE follower_guild_id = ? ;"
            params = (guild_id,)

            allowed_accounts = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    allowed_accounts.append(tuple(row))

            allowed_accounts_per_game = defaultdict(list)
            for game_id, account_id in allowed_accounts:
                allowed_accounts_per_game[game_id].append(account_id)

            return allowed_accounts_per_game

    async def get_ignored_services_per_game(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT game_id,service_id FROM ignored_services WHERE follower_guild_id = ? ;"
            params = (guild_id,)

            ignored_services = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    ignored_services.append(tuple(row))

            ignored_services_per_game = defaultdict(list)
            for game_id, service_id in ignored_services:
                ignored_services_per_game[game_id].append(service_id)

            return ignored_services_per_game

    async def get_allowed_services_per_game(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT game_id,service_id FROM allowed_services WHERE follower_guild_id = ? ;"
            params = (guild_id,)

            allowed_services = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    allowed_services.append(tuple(row))

            allowed_services_per_game = defaultdict(list)
            for game_id, service_id in allowed_services:
                allowed_services_per_game[game_id].append(service_id)

            return allowed_services_per_game

    async def rm_ignored_account(self, guild_id, game_id, account_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "DELETE FROM ignored_accounts WHERE follower_guild_id = ? AND game_id = ? AND account_id = ?;"
            params = (guild_id, game_id, account_id)

            await conn.execute(query, params)
            await conn.commit()

    async def rm_allowed_account(self, guild_id, game_id, account_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "DELETE FROM allowed_accounts WHERE follower_guild_id = ? AND game_id = ? AND account_id = ?;"
            params = (guild_id, game_id, account_id)

            await conn.execute(query, params)
            await conn.commit()

    async def rm_ignored_service(self, guild_id, game_id, service_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "DELETE FROM ignored_services WHERE follower_guild_id = ? AND game_id = ? AND service_id = ?;"
            params = (guild_id, game_id, service_id)

            await conn.execute(query, params)
            await conn.commit()

    async def rm_allowed_service(self, guild_id, game_id, service_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "DELETE FROM allowed_services WHERE follower_guild_id = ? AND game_id = ? AND service_id = ?;"
            params = (guild_id, game_id, service_id)

            await conn.execute(query, params)
            await conn.commit()

    async def get_saved_post_ids(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT * FROM posts;"

            saved_posts = defaultdict(list)
            async with conn.execute(query) as cr:
                async for row in cr:
                    saved_posts[row['game_id']].append(row['post_id'])
            return saved_posts

    async def set_saved_post_ids(self, game_id: int, post_ids: list):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "DELETE FROM posts WHERE game_id = ?;"
            params = (game_id,)
            await conn.execute(query, params)

            query = "INSERT INTO posts VALUES (?, ?);"
            params = [(game_id, post_id) for post_id in post_ids]
            await conn.executemany(query, params)
            await conn.commit()

    async def get_urlfilters_per_game(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT game_id,service_id,channel_id,thread_id,filters FROM url_filters WHERE follower_guild_id = ?;"
            params = (guild_id,)

            url_filters = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    url_filters.append(tuple(row))

            urlfiters_services_per_game = defaultdict(list)
            for game_id, service_id, channel_id, thread_id, filters in url_filters:
                urlfiters_services_per_game[game_id].append((service_id, channel_id, thread_id, filters))
            return urlfiters_services_per_game

    async def get_urlfilters(self, guild_id, game_id, service_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT channel_id,thread_id,filters FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND service_id = ?;"
            params = (guild_id, game_id, service_id)

            url_filters = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    url_filters.append(tuple(row))

            return url_filters

    async def get_urlfilters_thread(self, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT thread_id,filters FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND thread_id IS NOT NULL;"
            params = (guild_id, game_id)

            url_filters = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    url_filters.append(tuple(row))

            return url_filters

    async def get_urlfilters_channel(self, guild_id, game_id, service_id, channel_id=None, thread_id=None):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT filters FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND service_id = ?;"
            params = (guild_id, game_id, service_id)

            if channel_id:
                query = "SELECT filters FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND service_id = ? AND channel_id = ?;"
                params = (guild_id, game_id, service_id, channel_id)
            elif thread_id:
                query = "SELECT filters FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND service_id = ? AND thread_id = ?;"
                params = (guild_id, game_id, service_id, thread_id)

            async with conn.execute(query, params) as cr:
                row = await cr.fetchone()
                if row:
                    return row['filters']
                else:
                    return None

    async def get_urlfilters_per_service(self, guild_id, game_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT service_id,channel_id,thread_id,filters FROM url_filters WHERE follower_guild_id = ? AND game_id = ?;"
            params = (guild_id, game_id)

            url_filters = defaultdict(list)
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    url_filters[row['service_id']].append((row['channel_id'], row['thread_id'], row['filters']))

            return url_filters

    async def update_urlfilters_global(self, guild_id, game_id, service_id, filters):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)
            await conn.execute("PRAGMA foreign_keys = 1")

            # Clean any existing filters
            query = "DELETE FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND service_id = ?;"
            params = (guild_id, game_id, service_id)
            await conn.execute(query, params)
            await conn.commit()

            # Insert new global filters
            query = "INSERT OR REPLACE INTO url_filters ('follower_guild_id', 'game_id', 'service_id', 'filters', 'channel_id', 'thread_id') VALUES (?, ?, ?, ?, ?, ?);"
            params = (guild_id, game_id, service_id, filters, None, None)
            await conn.execute(query, params)
            await conn.commit()

    async def update_urlfilters_channel(self, guild_id, game_id, service_id, filters, channel_id=None, thread_id=None):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)
            await conn.execute("PRAGMA foreign_keys = 1")

            # Insert new filters
            if channel_id:
                query = """
                    DELETE FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND service_id = ? AND channel_id = ?;
                    """
                params = (guild_id, game_id, service_id, channel_id)
                await conn.execute(query, params)

                query = """
                    INSERT INTO url_filters ('follower_guild_id', 'game_id', 'service_id', 'filters', 'channel_id')
                    VALUES (?, ?, ?, ?, ?)
                    """
                params = (guild_id, game_id, service_id, filters, channel_id)
                await conn.execute(query, params)
            elif thread_id:

                query = """
                    DELETE FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND service_id = ? AND thread_id = ?;
                    """
                params = (guild_id, game_id, service_id, thread_id)
                await conn.execute(query, params)
                query = """
                    INSERT INTO url_filters ('follower_guild_id', 'game_id', 'service_id', 'filters', 'thread_id')
                    VALUES (?, ?, ?, ?, ?)
                    """
                params = (guild_id, game_id, service_id, filters, thread_id)
                await conn.execute(query, params)
            else:
                # No channel or thread id, this method should not be called
                return

            await conn.commit()

    async def clear_urlfilters(self, guild_id, game_id, service_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)
            await conn.execute("PRAGMA foreign_keys = 1")

            # Clean any existing filters
            query = "DELETE FROM url_filters WHERE follower_guild_id = ? AND game_id = ? AND service_id = ?;"
            params = (guild_id, game_id, service_id)
            await conn.execute(query, params)
            await conn.commit()

    async def close_connection(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.close()
