import os
import requests
import time
import typer
from dotenv import load_dotenv

load_dotenv()
APPLICATION_ID = os.getenv("APPLICATION_ID")
TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

app = typer.Typer()

URL_BASE = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"
HEADERS_BASE = {"Authorization": f"Bot {TOKEN}"}


@app.command()
def hello():
    print(f"=== CLI: Manage Slash Commands for Discord Bot ===")


@app.command()
def list_commands():
    resp = requests.get(URL_BASE, headers=HEADERS_BASE)
    try:
        data = resp.json()
        print(f"List Commands: {data}")
        return data
    except Exception as e:
        print(e)


@app.command()
def list_ids_commands():
    data = list_commands()
    if data is not None:
        ids = [e["id"] for e in data]
        print(f"List ID Commands: {ids}")
        return ids
    return []


@app.command()
def reset():
    ids = list_ids_commands()
    for id in ids:
        resp = requests.delete(f"{URL_BASE}/{id}", headers=HEADERS_BASE)
        time.sleep(2)
        print(f"COMMAND ID {id}: {resp.status_code}")


@app.command()
def add_commands():
    cmds = [
        {
            "name": "stat",
            "description": "Display the lastest registered stats for a governor",
            "type": 1,
            "options": [
                {
                    "name": "governor_id",
                    "description": "The governor ID",
                    "required": True,
                    "type": 4,  # require a INTEGER INPUT (ID)
                },
            ],
        },
        {
            "name": "top",
            "description": "Display the TOP by total score",
            "type": 1,
        },
    ]
    for cmd in cmds:
        # This create or update the slash commands
        response = requests.post(URL_BASE, headers=HEADERS_BASE, json=cmd)
        if response.status_code >= 400:
            print(response.content)
            raise Exception("Request Error!")
        else:
            print("command updated")
        time.sleep(2)


if __name__ == "__main__":
    app()
