"""Refresh the numbers in the profile card SVGs; everything else stays as-is."""
import calendar
import datetime as dt
import json
import math
import os
import re
import urllib.request

LOGIN = "nasagong"
LINE_WIDTH = 68  # label + dots + value, in monospace chars
BLOCKS = "▁▂▃▄▅▆▇█"

QUERY = """{ user(login: "%s") {
  createdAt
  contributionsCollection { contributionCalendar { totalContributions
    weeks { contributionDays { contributionCount } } } }
  repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
    nodes { languages(first: 20) { edges { size node { name } } } } }
} }""" % LOGIN


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    return json.load(urllib.request.urlopen(req))["data"]["user"]


def account_age(created, today):
    months = (today.year - created.year) * 12 + today.month - created.month - (today.day < created.day)
    year, month = divmod(created.month - 1 + months, 12)
    year += created.year
    anchor = dt.date(year, month + 1, min(created.day, calendar.monthrange(year, month + 1)[1]))
    unit = lambda n, s: f"{n} {s}{'' if n == 1 else 's'}"
    return f"{unit(months // 12, 'year')}, {unit(months % 12, 'month')}, {unit((today - anchor).days, 'day')}"


def languages(repos):
    sizes = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
    total = sum(sizes.values())
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:3]
    return ", ".join(f"{name} {round(size * 100 / total)}%" for name, size in top)


def sparkline(weeks):
    counts = [sum(d["contributionCount"] for d in w["contributionDays"])
              for w in weeks if len(w["contributionDays"]) == 7][-51:]
    top = math.log1p(max(counts) or 1)
    return "".join(" " if c == 0 else BLOCKS[min(7, int(math.log1p(c) / top * 7))] for c in counts)


def set_row(svg, label, value):
    dots = "." * (LINE_WIDTH - len(label) - len(value) - 1)
    pattern = rf'(<tspan fill="[^"]+">{re.escape(label)}</tspan><tspan fill="[^"]+">)\.+(</tspan><tspan fill="[^"]+">) [^<]*(</tspan>)'
    svg, n = re.subn(pattern, lambda m: f"{m[1]}{dots}{m[2]} {value}{m[3]}", svg)
    assert n == 1, f"row not found: {label}"
    return svg


def main():
    user = fetch()
    cal = user["contributionsCollection"]["contributionCalendar"]
    created = dt.date.fromisoformat(user["createdAt"][:10])
    rows = {
        ". Account Age: ": account_age(created, dt.datetime.now(dt.timezone.utc).date()),
        ". Languages: ": languages(user["repositories"]["nodes"]),
        ". Contributions: ": f"{cal['totalContributions']:,}",
    }
    spark = sparkline(cal["weeks"])
    for theme in ("dark", "light"):
        path = f"{LOGIN}-{theme}.svg"
        svg = open(path, encoding="utf-8").read()
        for label, value in rows.items():
            svg = set_row(svg, label, value)
        svg, n = re.subn(r'(<tspan fill="[^"]+">  )[ ▁-█]+( </tspan>)', lambda m: m[1] + spark + m[2], svg)
        assert n == 1, "sparkline not found"
        open(path, "w", encoding="utf-8").write(svg)


if __name__ == "__main__":
    assert account_age(dt.date(2021, 4, 28), dt.date(2026, 9, 7)) == "5 years, 4 months, 10 days"
    assert account_age(dt.date(2021, 3, 31), dt.date(2022, 3, 1)) == "0 years, 11 months, 1 day"
    main()
