<p align="center">
  <img src="https://i33.servimg.com/u/f33/11/20/17/41/logo_b11.png" alt="DevTracker Bot Logo"/>
</p>

# DevTracker

Discord Bot interfacing with the API of [DeveloperTracker.com](https://developertracker.com/).

Built with [Disnake](https://disnake.dev/).

## Features

This Bot track any post made by GameDevs from **30+** games, and let you follow the one you want via [Discord Slash Commands](https://support.discord.com/hc/en-us/articles/1500000368501-Slash-Commands-FAQ).

- Posts are compatible with the Discord Markdown Implementation.
- Follow any supported game at the same time.
- Set a specific channel per followed game if desired.
- Ignore posts from specific GameDevs

![DevTracker Post Example Steam](https://i.imgur.com/506lKDV.png)

### Supported Games
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

### DISCLAMER:
> This bot is currently **BETA**, expects bugs but more importantly, report them [here](https://github.com/s0me-1/devtracker-bot/issues).

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
/dt-set-channel game channel: #general game: They Are Billions
```

### Ignore posts from a specific account

You'll find the account ID in the footer of each post
```console
/dt-mute-account game:Rainbow 6: Siege account_id:76561198137855828
```
### Get current configuration
```console
/dt-status
```
## Self-Hosting

This Bot relies on the **DeveloperTracker API** that can be found [here](https://github.com/post-tracker/rest-api).

Once you have your credentials, you can either:
- Fill the `example.env` file and rename it into `.env`.
- Use `docker-compose.yml` with [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/).

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

```console
$ docker-compose up -d
```

## Credits
- [@kokarn](https://github.com/kokarn) - Main Dev of [DeveloperTracker.com](https://developertracker.com/).
- [Disnake](https://github.com/DisnakeDev/disnake) - Discord API Wrapper for Python.

## License
[GPL v3](https://github.com/s0me-1/devtracker-bot/blob/master/LICENSE)
