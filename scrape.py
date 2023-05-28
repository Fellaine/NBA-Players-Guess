import difflib
import os
import pickle
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep

import redis
from flask import Flask, jsonify, render_template, request, session
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix


def get_team_urls() -> dict[str, str]:
    """
    Get urls to roster of each team
    """
    f = urllib.request.urlopen("https://www.espn.com/nba/teams")
    data = f.read().decode("utf-8")
    teams = dict(
        re.findall('www\.espn\.com/nba/team/_/name/(\w+)/(.+?)",', data)  # noqa W605
    )
    roster_urls = [
        f"https://www.espn.com/nba/team/roster/_/name/{key}/{value}"
        for key, value in teams.items()
    ]
    return dict(zip(teams.values(), roster_urls))


def get_players_of_team(roster_url: str) -> list[str]:
    """
    Get a list of players from a given roster URL
    """
    f = urllib.request.urlopen(roster_url)
    data = f.read().decode("utf-8")
    sleep(0.3)
    pattern = r'href="https://www\.espn\.com/nba/player/_/id/\d+/[a-z-]+">([^<]*)</a>'
    return re.findall(pattern, data)


def get_list_of_all_players() -> list[str]:
    """
    Get list of players
    """
    path = Path("./list_of_players.pickle")
    has_expired = True
    if path.is_file():
        last_modified = datetime.fromtimestamp(path.stat().st_mtime)
        has_expired = datetime.now() - last_modified > timedelta(days=1)
    if not has_expired:
        with open("list_of_players.pickle", "rb") as fp:
            all_players = pickle.load(fp)
    else:
        rosters = get_team_urls()
        # all_players = dict()
        all_players = []
        # i = 0
        for team in rosters.keys():
            # if i >= 3:
            #     break
            print("Gathering player info for team: " + team)
            all_players.extend(get_players_of_team(rosters[team]))
            # all_players[team] = get_players_of_team(rosters[team])
            # i = i + 1

        # all_list = []
        # for value in all_players.values():
        #     all_list.extend(value)

        all_players = [i.replace("&#x27;", "'") for i in all_players]

        with open("list_of_players.pickle", "wb") as fp:
            pickle.dump(all_players, fp)
    return all_players


all_players = get_list_of_all_players()

app = Flask(__name__)

app.secret_key = [os.environ.get("SECRET_KEY")]

app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_REDIS"] = redis.from_url("redis://redis:6379")

server_session = Session(app)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


@app.route("/", methods=["GET", "POST"])
def reverse_string():
    if "user_players" not in session.keys():
        session["user_players"] = all_players[:]
    user_players = session["user_players"]
    if request.method == "POST":
        if not user_players:
            outp = f"GG, you got all {len(all_players)} of them "
        else:
            user_input = request.form["user_input"]
            if matches := difflib.get_close_matches(
                user_input, user_players, n=1, cutoff=0.8
            ):
                user_players.remove(matches[0])
                session["user_list"] = user_players
                outp = f"{len(all_players) - len(user_players)}/{len(all_players)}"
            else:
                outp = "No such player found."
        return jsonify({"outp": outp})
    return render_template("form.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0")
