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
- [Commands](#commands)
  * [Set the default notification channel](#set-the-default-notification-channel)
  * [Follow a game](#follow-a-game)
  * [Follow a game in a specific channel](#follow-a-game-in-a-specific-channel)
  * [Ignore posts from a specific account](#ignore-posts-from-a-specific-account)
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

![DevTracker Post Example Steam](https://i.imgur.com/506lKDV.png)

## Supported Games
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

## Commands

Each Slash Command has **autofillers** to help you.

![Slash Command autofiller example](https://i.imgur.com/nui0Yk3.png)

### Set the default notification channel
```console
/dt-set-channel default channel: #general
```

### Follow a game
```console
/dt-follow game: Star Citizen
```

### Follow a game in a specific channel
```console
/dt-set-channel game channel: #tab-devtracker game: They Are Billions
```

### Ignore posts from a specific account

You'll find the account ID in the footer of each post
```console
/dt-mute-account game:Rainbow 6: Siege account_id:76561198137855828
```

### Unmute a specific account

You can find the account you have ignored with the `/dt-status` slash command.
```console
/dt-mute-account account_id:76561198137855828
```
### Get current configuration

![DevTracker Config](https://i.imgur.com/mF20Mfk.png)

```console
/dt-status
```
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
