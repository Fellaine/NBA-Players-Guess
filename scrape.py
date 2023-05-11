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


def get_team_urls() -> dict[str, str]:
    """
    Get urls to roster of each team
    """
    f = urllib.request.urlopen("https://www.espn.com/nba/teams")
    data = f.read().decode("utf-8")
    teams = dict(
        re.findall('www\.espn\.com/nba/team/_/name/(\w+)/(.+?)",', data)  # noqa W605
    )
    # "bos": "boston-celtics", "bkn": "brooklyn-nets",
    roster_urls = []
    for key in teams.keys():
        roster_urls.append(
            "https://www.espn.com/nba/team/roster/_/name/" + key + "/" + teams[key]
        )
    return dict(zip(teams.values(), roster_urls))


def get_players_of_team(roster_url: str) -> list[str]:
    """
    Get a list of players from a given roster URL
    """
    f = urllib.request.urlopen(roster_url)
    data = f.read().decode("utf-8")
    sleep(0.3)
    pattern = r'href="https://www\.espn\.com/nba/player/_/id/\d+/[a-z-]+">([^<]*)</a>'
    players = re.findall(pattern, data)
    return players


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
            all_list = pickle.load(fp)
    else:
        rosters = get_team_urls()
        # all_players = dict()
        all_list = []
        # i = 0
        for team in rosters.keys():
            # if i >= 3:
            #     break
            print("Gathering player info for team: " + team)
            all_list.extend(get_players_of_team(rosters[team]))
            # all_players[team] = get_players_of_team(rosters[team])
            # i = i + 1

        # all_list = []
        # for value in all_players.values():
        #     all_list.extend(value)

        all_list = [i.replace("&#x27;", "'") for i in all_list]

        with open("list_of_players.pickle", "wb") as fp:
            pickle.dump(all_list, fp)
    return all_list


all_list = get_list_of_all_players()

app = Flask(__name__)

app.secret_key = [os.environ.get("SECRET_KEY")]

app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_REDIS"] = redis.from_url("redis://redis:6379")

server_session = Session(app)


@app.route("/", methods=["GET", "POST"])
def reverse_string():
    if "user_list" in session.keys():
        user_list = session["user_list"]
    else:
        session["user_list"] = all_list[:]
        user_list = session["user_list"]
    if request.method == "POST":
        if not user_list:
            outp = f"GG, you got all {len(all_list)} of them "
        else:
            user_input = request.form["user_input"]
            matches = difflib.get_close_matches(user_input, user_list, n=1, cutoff=0.8)
            if matches:
                user_list.remove(matches[0])
                session["user_list"] = user_list
                outp = f"{len(all_list) - len(user_list)}/{len(all_list)}"
            else:
                outp = "No such player found."
        return jsonify({"outp": outp})
    return render_template("form.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0")
