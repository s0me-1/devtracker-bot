from collections import defaultdict
import aiosqlite
import logging

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
                CREATE TABLE IF NOT EXISTS ignored_accounts (
                    account_id NVARCHAR NOT NULL,
                    follower_guild_id NOT NULL,
                    FOREIGN KEY (follower_guild_id) REFERENCES guilds (id) ON DELETE CASCADE
                    PRIMARY KEY (account_id, follower_guild_id)
                );
            ''')
            await conn.commit()

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

            query = "DELETE FROM follows WHERE followed_game_id = ? AND follower_guild_id = ?;"
            params = (game_id, guild_id)

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
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "UPDATE follows SET last_post_id = ? WHERE follower_guild_id = ? AND followed_game_id = ?;"
            params = (post_id, guild_id, game_id)

            await conn.execute(query, params)
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

            query = "SELECT id FROM games"

            db_games_ids = set()
            async with conn.execute(query) as cr:
                async for row in cr:
                    db_games_ids.add(row['id'])

            api_games_ids = {game[0] for game in api_games}

            to_rem = db_games_ids.difference(api_games_ids)
            to_rem = [set(id) for id in to_rem]
            if to_rem:
                query = "DELETE FROM games WHERE id = ?;"
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
            params =  (guild_id,)

            followed_games_ids = {}
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    followed_games_ids.update({
                        row[0] : row[1]
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

            return followed_games_ids

    async def get_all_ignored_accounts(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "SELECT account_id,follower_guild_id FROM ignored_accounts;"

            ignored_accounts = []
            async with conn.execute(query) as cr:
                async for row in cr:
                    ignored_accounts.append(tuple(row))

            ignored_per_guild = defaultdict(list)
            for account_id, guild_id in ignored_accounts:
                ignored_per_guild[guild_id].append(account_id)

            return ignored_per_guild

    async def add_ignored_account(self, guild_id, account_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "INSERT OR IGNORE INTO ignored_accounts ('account_id', 'follower_guild_id') VALUES (?, ?);"
            params = (account_id, guild_id)

            await conn.execute(query, params)
            await conn.commit()

    async def get_ignored_accounts(self, guild_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.set_trace_callback(logger.debug)

            query = "SELECT account_id FROM ignored_accounts WHERE follower_guild_id = ? ;"
            params = (guild_id,)

            ignored_accounts = []
            async with conn.execute(query, params) as cr:
                async for row in cr:
                    ignored_accounts.append(row['account_id'])
            return ignored_accounts

    async def rm_ignored_account(self, guild_id, account_id):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.set_trace_callback(logger.debug)

            query = "DELETE FROM ignored_accounts WHERE account_id = ? AND follower_guild_id = ?;"
            params = (account_id, guild_id)

            await conn.execute(query, params)
            await conn.commit()


    async def close_connection(self):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.close()
