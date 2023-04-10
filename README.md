<p align="center">
  <img src="https://i33.servimg.com/u/f33/11/20/17/41/logo_b11.png" alt="DevTracker Bot Logo"/>
</p>

# DevTracker
<a href="https://discord.gg/QN9uveFYXX"><img src="https://img.shields.io/discord/984016998084247582?style=flat-square&color=5865f2&logo=discord&logoColor=ffffff&label=discord" alt="Discord server invite" /></a>
<a href="https://pypi.python.org/pypi/disnake"><img src="https://img.shields.io/pypi/pyversions/disnake.svg?style=flat-square" alt="PyPI supported Python versions" /></a>

Discord Bot interfacing with the API of [DeveloperTracker.com](https://developertracker.com/).

Built with [Disnake](https://disnake.dev/).

- [Features](#features)
- [Supported Games](#supported-games)
- [Getting Started](#getting-started)
  * [Installation](#installation)
  * [Basic setup](#basic-setup)
  * [Advanced setup](#advanced-setup)
- [Commands](#commands)
  * [Filtering posts](#filtering-posts)
  * [Get current configuration](#get-current-configuration)
- [Self-Hosting](#self-hosting)
  * [Python](#python)
  * [Docker-Compose](#docker-compose)
- [Credits](#credits)
- [License](#license)

## Features

This Bot track any post made by GameDevs from **30+** games, and let you follow the one you want via [Discord Slash Commands](https://support.discord.com/hc/en-us/articles/1500000368501-Slash-Commands-FAQ).

- Posts are compatible with the Discord Markdown Implementation.
- Follow any supported game at the same time.
- Set a specific channel per followed game if desired.
- Ignore posts from specific GameDevs

![DevTracker Post Example Steam](https://i.imgur.com/0VGp7pl.png)

## Supported Games

This is a non-exhaustive list of the games supported by the bot. You can find the full list [here](https://developertracker.com/).

- ARK: Survival Evolved
- Anthem
- Battlefield 1
- Conan: Exiles
- Core Keeper
- Counter Strike: Global Offensive
- Darwin Project
- DayZ
- Dead Matter
- Destiny 2
- Dwarf Fortress
- Dyson Sphere Program
- Elite: Dangerous
- Escape from Tarkov
- Fortnite
- Going Medieval
- Hearthstone
- Icarus
- It Lurks Below
- Magic: The Gathering Arena
- Marauders
- Oxygen Not Included
- PLAYERUNKNOWN'S BATTLEGROUNDS
- Path of Exile
- Rainbow 6: Siege
- Realm Royale
- RimWorld
- Rocket League
- Satisfactory
- Sea of Thieves
- Space Haven
- Star Citizen
- Starbase
- Stonehearth
- The Cycle: Frontier
- The Planet Crafter
- They Are Billions
- V Rising
- Valheim

## Getting Started
### Installation

Click the button below to add **DevTracker** to your server.

[![](https://i33.servimg.com/u/f33/11/20/17/41/invite10.png)](https://discord.com/api/oauth2/authorize?client_id=982257201211138050&permissions=274877925376&scope=bot%20applications.commands)

### Basic setup
Simply create a channel where you want to receive the posts, make sure **DevTracker** has the `View Channel` and `Send Messages` Discord permissions for that channel.

Then, use the `/dt-set-channel` command to tell the bot where to send the posts. e.g.:
```
 /dt-set-channel game channel: #sc-devtracker game: Star Citizen
```

### Advanced setup

You have 2 options, use a single channel for all the posts, or use a specific channel for each game:
- **Single channel**: Use the `/dt-set-channel default` command to set the default channel for all the posts. e.g.:
```
 /dt-set-channel default channel: #devtracker
```
You can then use the `/dt-follow` command to follow games. e.g.:
```
/dt-follow game: Star Citizen
/dt-follow game: Elite: Dangerous
```
Now all the posts from `Star Citizen` and `Elite: Dangerous` will be sent to the `#devtracker` channel.

- **Specific channel per game**: Use the `/dt-set-channel game` command to set a specific channel for each game. e.g.:
```
 /dt-set-channel game channel: #sc-devtracker game: Star Citizen
```


## Commands

Each Slash Command has **autofillers** to help you.

![Slash Command autofiller example](https://i.imgur.com/nui0Yk3.png)


### Filtering posts

#### Allowlist & Ignorelist
You can setup allowlists or ignorelists to filter posts for **each game**.
- `allowlist`: Only posts matching the accounts or service in this list will be sent.
- `ignorelist`: Posts matching the accounts or service in this list will be ignored.

**Notes**:
- Each `allowlist` or `ignorelist` is game-specific, so you can have different filters for each game.
- You can use both at the same time, but the `allowlist` will take precedence over the `ignorelist`. E.g. if you have an `igorelist` with a specific account for `Star Citizen` from the `Twitter` service, and an `allowlist` for the whole `rsi` service for `Star Citizen`, only posts from the `rsi` service will be sent, the ignored account will not even be considered.
- You'll find the `account_id` in the footer of each post.

**Ignore specific accounts or service:**

This is achieved via the `/dt-ignorelist` command. Any future post from the specified account or service from the `ignorelist` for the specified game will be ignored.

**Examples:**

```sh
# Ignore posts from a specific account
/dt-ignorelist add account game_name: Star Citizen service_id: rsi account_id: Zyloh-CIG

# Ignore all posts from a specific service
/dt-ignorelist add service game_name: Star Citizen service_id: rsi

# Stop ignoring posts from a specific service
/dt-ignorelist remove service game_name: Star Citizen service_id: rsi

# Stop ignoring posts from a specific account
/dt-ignorelist remove account game_name: Star Citizen account_id: Zyloh-CIG
```

**Get only posts from specific accounts or service:**

This is achieved via the `/dt-allowlist` command. Any future post from the specified account or service from the `allowlist` will be the only ones sent for the specified game.

Usage is the same than the `ignorelist` command.

**Examples:**

```sh
# Get posts from a specific account only
/dt-allowlist add account game_name: Star Citizen service_id: rsi account_id: Zyloh-CIG

# Get posts from a specific service only
/dt-allowlist add service game_name: Star Citizen service_id: rsi

# Remove a specific service from the allowlist
/dt-allowlist remove service game_name: Star Citizen service_id: rsi

# Remove a specific account from the allowlist
/dt-allowlist remove account game_name: Star Citizen account_id: Zyloh-CIG
```

#### URL Filters

You can also filter posts by URL. This is useful if you want to get only posts from specific threads.
There's two different con

##### Global URL Filters
Only posts where the origin URL matches the filters will be sent to the channel configured with the `/dt-set-channel` command.

**Example**

Let's imagine you want only posts from the `Announcements` section of the Star Citizen forums. The url for the `Announcements` section is `https://robertsspaceindustries.com/spectrum/community/SC/forum/1`

You can use the `/dt-urlfilters global` command to add `forum/1` filter for `Star Citizen` forums:
```sh
/dt-urlfilters global game_name: Star Citizen service_id: rsi
```

This will open a modal with your current filters.

![URL Filters modal](https://i.imgur.com/7DM5hIR.png)

You can then add the `forum/1` filter then click the **Submit** button to apply changes.

**Note:**
You can also add multiple filters for the same service. You just need to separate them with a comma `,`.
If any of the filters match the post URL, it will be sent to the set channel.

E.g.: `forum/1,forum/3,forum/4`, this will match any post from the `Announcements`, `General` and `Feedback` sections.

##### Channel URL Filters
This allows to use URL Filters to dispatch posts that match the filters to a specific channel.

**Example**

Let's imagine you want all the posts from the `Announcements` section of the Star Citizen forums to be sent to the `#sc-announcements` Discord channel. The url for the `Announcements` section is `https://robertsspaceindustries.com/spectrum/community/SC/forum/1`

You can use the `/dt-urlfilters channel` command to add `forum/1` filter for `Star Citizen` forums:
```
/dt-urlfilters global channel: #sc-announcements game_name: Star Citizen service_id: rsi
```

This will open a modal with your current filters.
You can then add the `forum/1` filter then click the **Submit** button to apply changes.

**Note**:
- Please make sure the bot have the __**Send Message permission**__ for the channel you're using. Otherwise it won't be able to send the posts.
- You can add multiple filters for the same service here too. You just need to separate them with a comma `,`.

### Get current configuration

You can use the `/dt-config` command to get the current configuration for the server.

This will list all the games you're following, and the channel where the posts are sent.
It will also give you the active `allowlist` and `ignorelist` for each game.

![DevTracker Config](https://i.imgur.com/Za6pQ7F.png)

## Self-Hosting

This Bot relies on the **DeveloperTracker API** that can be found [here](https://github.com/post-tracker/rest-api).

Once you have your credentials, you can either:
- Fill the `example.env` file and rename it into `.env`.
- Use `docker-compose.yml` with [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/).

Here's what you'll need to set:
- `API_BASE`: The DeveloperTracker.com API base url.
- `API_TOKEN`: Your DeveloperTracker.com API Token.
- `BOT_TOKEN`:  Your [Discord Bot Token](https://discord.com/developers/applications)

Optional (Only used when the `--log-level debug` argument is passed or with `docker-compose --profile debug`.):
- `DEBUG_GUILD_ID`: Your Debug Guild ID, slash commands will only be synchronized for this guild only.
- `DEBUG_BOT_TOKEN`:  Your Debug [Discord Bot Token](https://discord.com/developers/applications), to run the bot on a seperate Discord App when debugging.

You can then launch the bot as described below:

### Python

Install the pip dependancies (virtual environment recommended).
```console
$ pip -r requirements.txt
```
And you can simply run the bot with
```console
$ python bot.py
```

### Docker-Compose
Docker will manage the dependancies for you.
It will build the images automatically on first run.

```console
$ docker-compose --profile default up -d
```

Run in debug mode:
```console
$ docker-compose --profile debug up -d
```

## Credits
- [@kokarn](https://github.com/kokarn) - Main Dev of [DeveloperTracker.com](https://developertracker.com/).
- [Disnake](https://github.com/DisnakeDev/disnake) - Discord API Wrapper for Python.

## License
[GPL v3](https://github.com/s0me-1/devtracker-bot/blob/master/LICENSE)
