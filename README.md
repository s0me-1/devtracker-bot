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

### Supported Games
 - ARK: Survival Evolved
 - Battlefield 1
 - Conan: Exiles
 - Counter Strike: Global Offensive
 - Destiny 2
 - Elite: Dangerous
 - PLAYERUNKNOWN'S BATTLEGROUNDS
 - Rainbow 6: Siege
 - RimWorld
 - Anthem
 - Fortnite
 - They Are Billions
 - Escape from Tarkov
 - Star Citizen
 - Darwin Project
 - Rocket League
 - Path of Exile
 - Sea of Thieves
 - Stonehearth
 - It Lurks Below
 - Hearthstone
 - DayZ
 - Realm Royale
 - Magic: The Gathering Arena
 - Space Haven
 - Satisfactory
 - Dwarf Fortress
 - Dead Matter
 - Oxygen Not Included
 - Dyson Sphere Program
 - Valheim
 - Going Medieval
 - Starbase
 - Icarus
 - Core Keeper
 - The Cycle: Frontier
 - Marauders
 - The Planet Crafter
 - V Rising

## Getting Started

Click the button below to add DevTracker to your server

[![](https://i33.servimg.com/u/f33/11/20/17/41/invite10.png)](https://discord.com/api/oauth2/authorize?client_id=982257201211138050&permissions=274877958144&scope=applications.commands%20bot)



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
Once you have your credentials, fill the `example.env` file and rename it into `.env`.

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
- [@kokarn](https://github.com/kokarn) - Main Dev, [DeveloperTracker.com](https://developertracker.com/).
