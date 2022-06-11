from collections import defaultdict
import sqlite3
import logging

logger = logging.getLogger('bot.DB')

DB_FILE = 'db/tracking.db'


def initialize():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                id INTEGER PRIMARY KEY,
                main_channel_id INTEGER
            );
        ''')
        conn.execute('''
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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id NVARCHAR PRIMARY KEY,
                name NVARCHAR
            );
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ignored_accounts (
                account_id NVARCHAR NOT NULL,
                follower_guild_id NOT NULL,
                FOREIGN KEY (follower_guild_id) REFERENCES guilds (id) ON DELETE CASCADE
                PRIMARY KEY (account_id, follower_guild_id)
            );
        ''')


class ORM:

    _instances = {}

    def __init__(self):
        initialize()
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(ORM, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def add_guild(self, guild_id):
        with self.conn as conn:
            conn.execute("INSERT OR IGNORE INTO guilds ('id', 'main_channel_id') VALUES (?, ?);", (guild_id, None))

    def rm_guild(self, guild_id):
        with self.conn as conn:
            conn.execute("DELETE FROM guilds WHERE id = ?;", (guild_id,))

    def dump_guilds(self):
        with self.conn as conn:
            for row in conn.execute("SELECT id, main_channel_id FROM guilds"):
                print(tuple(row))

    def add_followed_game(self, game_id, guild_id):
        with self.conn as conn:
            conn.execute("INSERT OR IGNORE INTO follows ('last_post_id', 'channel_id', 'follower_guild_id', 'followed_game_id' ) VALUES (?, ?, ?, ?);", (None, None, guild_id, game_id))

    def rm_followed_game(self, game_id, guild_id):
        with self.conn as conn:
            conn.execute("DELETE FROM follows WHERE followed_game_id = ? AND follower_guild_id = ?;", (game_id, guild_id))

    def dump_follows(self):
        with self.conn as conn:
            for row in conn.execute("SELECT * FROM follows;"):
                print(tuple(row))

    def get_follow_status(self, guild_id):
        with self.conn as conn:
            game_names = []
            for row in conn.execute("SELECT g.id,g.name,fw.channel_id,fw.last_post_id FROM games AS g INNER JOIN follows AS fw ON g.id = fw.followed_game_id WHERE fw.follower_guild_id = ? ;", (guild_id,)):
                game_names.append(tuple(row))
            return game_names

    def get_follow(self, guild_id, game_id):
        with self.conn as conn:
            follows = []
            for row in conn.execute("SELECT * FROM follows WHERE follower_guild_id = ? AND followed_game_id = ?;", (guild_id, game_id)):
                follows.append(tuple(row))
            return follows[0] if follows else None

    def get_follows(self, guild_id):
        with self.conn as conn:
            follows = []
            for row in conn.execute("SELECT * FROM follows WHERE follower_guild_id = ?;", (guild_id,)):
                follows.append(tuple(row))
            return follows

    def get_all_follows(self):
        with self.conn as conn:
            follows = []
            for row in conn.execute("SELECT * FROM follows;"):
                follows.append(tuple(row))
            return follows

    def set_last_post(self, post_id, guild_id, game_id):
        with self.conn as conn:
            conn.execute("UPDATE follows SET last_post_id = ? WHERE follower_guild_id = ? AND followed_game_id = ?;", (post_id, guild_id, game_id))

    def set_main_channel(self, channel_id, guild_id):
        with self.conn as conn:
            conn.execute("UPDATE guilds SET main_channel_id = ? WHERE id = ?;", (channel_id, guild_id))

    def unset_main_channel(self, guild_id):
        with self.conn as conn:
            conn.execute("UPDATE follows SET channel_id = ? WHERE id = ?;", (None, guild_id))

    def get_main_channel(self, guild_id):
        with self.conn as conn:
            for row in conn.execute("SELECT main_channel_id FROM guilds WHERE id = ?;", (guild_id,)):
                return row['main_channel_id']
            return None

    def set_game_channel(self, channel_id, guild_id, game_id):
        with self.conn as conn:
            conn.execute("UPDATE follows SET channel_id = ? WHERE follower_guild_id = ? AND followed_game_id = ?;", (channel_id, guild_id, game_id))

    def add_fw_game_channel(self, channel_id, guild_id, game_id):
        with self.conn as conn:
            conn.execute("INSERT OR IGNORE INTO follows ('last_post_id', 'channel_id', 'follower_guild_id', 'followed_game_id' ) VALUES (?, ?, ?, ?);", (None, channel_id, guild_id, game_id))

    def unset_game_channel(self, guild_id, game_id):
        with self.conn as conn:
            conn.execute("UPDATE follows SET channel_id = ? WHERE follower_guild_id = ? AND followed_game_id = ?;", (None, guild_id, game_id))

    def get_game_channel(self, game_id, guild_id):
        with self.conn as conn:
            # Check if a channel is set per game
            for row in conn.execute("SELECT channel_id FROM follows WHERE followed_game_id = ? AND follower_guild_id = ?;", (game_id, guild_id)):
                return row['channel_id']
            return None

    def get_local_games(self):
        with self.conn as conn:

            api_games_ids = []
            for row in conn.execute("SELECT * FROM games;"):
                api_games_ids.append(tuple(row))

            return api_games_ids

    def update_local_games(self, api_games: tuple):
        with self.conn as conn:

            db_games_ids = set()
            for row in conn.execute("SELECT id FROM games"):
                db_games_ids.add(row['id'])

            api_games_ids = {game[0] for game in api_games}

            to_rem = db_games_ids.difference(api_games_ids)
            to_rem = [set(id) for id in to_rem]
            if to_rem:
                conn.executemany("DELETE FROM games WHERE id = ?;", to_rem)

            to_add = api_games_ids.difference(db_games_ids)
            to_add = [game for game in api_games if game[0] in to_add]
            if to_add:
                conn.executemany("INSERT OR IGNORE INTO games ('id', 'name') VALUES (?, ?);", to_add)

    def get_followed_games(self, guild_id):
        with self.conn as conn:

            followed_games_ids = {}
            for row in conn.execute("SELECT g.name,g.id FROM games AS g INNER JOIN follows AS fw ON g.id = fw.followed_game_id WHERE fw.follower_guild_id = ? ;", (guild_id,)):
                followed_games_ids.update({
                    row[0] : row[1]
                })

            return followed_games_ids

    def get_all_followed_games(self):
        with self.conn as conn:

            followed_games_ids = set()
            for row in conn.execute("SELECT followed_game_id FROM follows"):
                followed_games_ids.add(row['followed_game_id'])

            return followed_games_ids

    def get_all_ignored_accounts(self):
        with self.conn as conn:

            ignored_accounts = []
            for row in conn.execute("SELECT account_id,follower_guild_id FROM ignored_accounts;"):
                ignored_accounts.append(tuple(row))

            ignored_per_guild = defaultdict(list)
            for account_id, guild_id in ignored_accounts:
                ignored_per_guild[guild_id].append(account_id)

            return ignored_per_guild

    def add_ignored_account(self, guild_id, account_id):
        with self.conn as conn:
            conn.execute("INSERT OR IGNORE INTO ignored_accounts ('account_id', 'follower_guild_id') VALUES (?, ?);", (account_id, guild_id))

    def get_ignored_accounts(self, guild_id):
        with self.conn as conn:
            ignored_accounts = []
            for row in conn.execute("SELECT account_id FROM ignored_accounts WHERE follower_guild_id = ? ;", (guild_id,)):
                ignored_accounts.append(row['account_id'])
            return ignored_accounts

    def rm_ignored_account(self, guild_id, account_id):
        with self.conn as conn:
            conn.execute("DELETE FROM ignored_accounts WHERE account_id = ? AND follower_guild_id = ?;", (account_id, guild_id))


    def close_connection(self):
        with self.conn as conn:
            conn.close()
