# Rise of Kingdoms - Discord Data Bot

**A Discord bot that retrieve data from Google Sheets**

Example of Google Sheet Document,

| ID | Name | 8/16/2023 | POWER | KILLS POINTS | RSS ASSISTANCE | DEAD | T4 | T5 | KVK KILLS T4 | KVK KILLS T5 | KVK KILLS T4/T5 | KVK DEADS | EXPECTED KILLS | EXPECTED DEADS | POINTS | POWER WEIGHT | TOTAL SCORE
|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
|2123|governor|----|500|1|10|0|3|0|500|1|10|0|3|0|500|1|993|

Now, The bot has 1 main command:
`stat governor_id`

Example using the above data:
`stat 2123`, or `stat` if he's ID is saved in memory

And the **discord bot** will output something like:

![example of discord bot result](./sample/Screenshot%202023-08-19%20at%2011.01.35%20AM.png)

> The bot can use a database ([Redis](https://redis.io/)) as a memory (optional). It saves the governor_id and attach it to the discord user who use the command. **Thus, the discord user can write `stat` without the `governor_id` as it is saved in memory.**

## 1. How the program works

In the `main.py` file, you may update the values for this config:
```
GOV_KEYS = ["ID", "NAME", "POWER", "KVK RANK", "KVK KILLS T4", "KVK KILLS T5",
            "KVK KILLS T4/T5", "KVK DEADS", "EXPECTED KILLS", "EXPECTED DEADS", "TOTAL SCORE"]
GOAL_KEYS = {
    "kill": "EXPECTED KILLS",
    "t4": "KVK KILLS T4",
    "t5": "KVK KILLS T5",
    "dead": "EXPECTED DEADS",
}
GOV_GOAL_KEYS = {
    "kill": "KVK KILLS T4/T5",
    "t4": "KVK KILLS T4",
    "t5": "KVK KILLS T5",
    "dead": "KVK DEADS"
}
```
If you look closely, the values here are from the column names from the data above.

**Note: The bot will only display the last range of data collected.
Your Google Sheet Document may have multiple recording. The bot separates each data gathered using a column "Datetime"**

## 2. Requirements

- You need to create a Discord BOT (check discord documentation). You will need some secrets token like:
`APPLICATION_ID, PUBLIC_KEY, TOKEN`

- A Discord server of course, keep your `GUILD_ID`

- server (hosting), Docker installed to start easily the bot

- Google API KEY (we use API KEY for easy code), thus, your document should be "publicly" visible (only with shared link)

*The document here only covers some principle about the bot, the rest is not describe, if anything, contact me...*

## 3. Bot Installation

You may need a server for that.
This repository includes the `Github workflows` config. If you fork and host in your own account, you can have your `Docker image` automatically built when you push on `production branch`.

@see (https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)

**You also need to set in your github settings some environment variables:**
s
![github project settings secrets](./sample/Screenshot%202023-08-19%20at%2011.29.22%20AM.png)

**Because the github workflow will use theses variables and build your docker image according to it**

### a. First time installation

```
export CR_PAT=MY_GITHUB_PERSONAL_ACCESS_TOKEN
echo $CR_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

docker volume create redis-store
docker run --name redis-store -p 6379:6379 -d -v redis-store:/data redis redis-server --save 60 1 --loglevel warning

docker pull ghcr.io/YOUR_GITHUB_USERNAME/rok-discord-data:production
docker run -d --name rok-discord-data ghcr.io/YOUR_GITHUB_USERNAME/rok-discord-data:production
```

### b. Update bot code

```
export CR_PAT=MY_GITHUB_PERSONAL_ACCESS_TOKEN
echo $CR_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

docker pull ghcr.io/YOUR_GITHUB_USERNAME/rok-discord-data:production && \
    docker stop rok-discord-data && \
    docker rm rok-discord-data && \
    docker run -d --name rok-discord-data ghcr.io/YOUR_GITHUB_USERNAME/rok-discord-data:production
```

**Note: The bot uses the URL *redis://0.0.0.0:6379* to connect to the database. However, depending on your network config, it may not be accessible with this URL. So, you need to go inside the container and update the URL, specically the IP address and then restart the container. contact me if needed**