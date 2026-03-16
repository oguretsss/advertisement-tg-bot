# Simple telegram bot for posting user generated advertisements into channel.
Users of your channel can post messages in channels using this bot.
They simply need to write a message to bot. Bot will prompt them if they want their message to be posted to your public channel with link to author.
If the user agrees, their message will be posted to the channel. This may be useful for channels where users can buy/sell stuff.
Currently, bot supports text and photos.
## Initial setup 
### Creating bot and channel
1. Create new telegram bot with @BotFather or use existing one
2. Create a new channel in telegram or use existing one
3. Add your bot to the channel as administrator

### Setting bot up
1. Clone this repo
2. Setup virtual environment and install dependencies: 
```commandline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
3. Create directory for logs: `mkdir logs`
4. Create bot_settings.py file: `touch bot_settings.py`
5. Add the following to you bot_settings file:
```python
# Replace value below with bot token that you can receive from BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN" 
# Replace value below with ID of your channel.
# You can see it in web version of telegram
# Keep in mind that you should append -100 at the beginning
# For example, if your channel's ID is -12304577778, 
# the value should be -10012304577778 
CHANNEL_ID = "-100<YOUR_CHANNEL_ID>"
```
Example of bot settings for bot with token `123456789:hgdywtwhq8vQWERTYUIOPASDFGHKJKMNNBU`
and channel with id `-1123456789`:
```python
BOT_TOKEN = "123456789:hgdywtwhq8vQWERTYUIOPASDFGHKJKMNNBU"
CHANNEL_ID = "-1001123456789"
```
## Starting the bot

### Option 1: Run locally
1. Activate venv: `source venv/bin/activate`
2. Start bot: `python3 main.py`

### Option 2: Run with Docker
You can run the bot in a Docker container without creating `bot_settings.py`. Configuration is passed via environment variables.

1. Create a `.env` file (or export the variables in your shell):
```bash
BOT_TOKEN=123456789:hgdywtwhq8vQWERTYUIOPASDFGHKJKMNNBU
CHANNEL_ID=-1001123456789
```
2. Start the bot:
```bash
docker compose up --build -d
```

The database is stored in `./data/` and logs in `./logs/` on the host (mounted as volumes).

To stop the bot:
```bash
docker compose down
```

**Note:** When running locally without `bot_settings.py`, you can also use environment variables:
```bash
BOT_TOKEN="your-token" CHANNEL_ID="-100your-channel-id" python3 main.py
```
