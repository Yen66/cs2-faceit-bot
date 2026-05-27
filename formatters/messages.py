from datetime import datetime


LEVEL_EMOJI = {
    1: "🔰", 2: "🔰",
    3: "⚔️", 4: "⚔️",
    5: "🥉", 6: "🥉",
    7: "🥈", 8: "🥈",
    9: "🥇",
    10: "👑",
}

COUNTRY_FLAGS = {
    "RU": "🇷🇺", "UA": "🇺🇦", "BY": "🇧🇾", "KZ": "🇰🇿",
    "PL": "🇵🇱", "DE": "🇩🇪", "FR": "🇫🇷", "TR": "🇹🇷",
    "BR": "🇧🇷", "US": "🇺🇸", "SE": "🇸🇪", "DK": "🇩🇰",
    "CZ": "🇨🇿", "SK": "🇸🇰", "HU": "🇭🇺", "GB": "🇬🇧",
    "FI": "🇫🇮", "NO": "🇳🇴", "NL": "🇳🇱", "ES": "🇪🇸",
}


def _flag(country_code: str) -> str:
    return COUNTRY_FLAGS.get(country_code.upper(), "🏳️")


def _format_date(timestamp_s: int) -> str:
    """Format Unix-seconds timestamp as DD.MM.YYYY (local time)."""
    if not timestamp_s:
        return "?"
    dt = datetime.fromtimestamp(timestamp_s)
    return dt.strftime("%d.%m.%Y")


def format_stats(player: dict, stats: dict) -> str:
    """Format player stats card message."""
    nickname = player.get("nickname", "?")
    country = player.get("country", "??").upper()
    game_data = player.get("games", {}).get("cs2", {})
    elo = game_data.get("faceit_elo", 0)
    level = game_data.get("skill_level", 0)
    level_emoji = LEVEL_EMOJI.get(level, "❓")
    flag = _flag(country)

    lifetime = stats.get("lifetime", {})
    kd = lifetime.get("Average K/D Ratio", "—")
    hs = lifetime.get("Average Headshots %", "—")
    win_rate = lifetime.get("Win Rate %", "—")
    matches = lifetime.get("Matches", "—")
    avg_kills = lifetime.get("Average Kills", "—")

    return (
        f"👤 <b>{nickname}</b>  {flag}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏆 ELO: <b>{elo}</b>  |  Уровень: <b>{level}</b> {level_emoji}\n"
        f"⚔️ K/D: <b>{kd}</b>\n"
        f"🎯 Хедшоты: <b>{hs}%</b>\n"
        f"🏅 Win Rate: <b>{win_rate}%</b>\n"
        f"💀 Avg kills: <b>{avg_kills}</b>\n"
        f"📊 Матчей: <b>{matches}</b>\n"
    )


def format_last_matches(nickname: str, matches_data: list) -> str:
    """Format last N matches list."""
    if not matches_data:
        return f"😔 Нет матчей для <b>{nickname}</b>"

    lines = [f"📋 <b>Последние матчи — {nickname}</b>\n"]

    for m in matches_data:
        result = m.get("result", "?")
        icon = "✅" if result == "1" else "❌"
        map_name = m.get("map", "?").replace("de_", "")
        score = m.get("score", "?")
        kd = m.get("kd", "?")
        when = _format_date(m.get("started_at", 0))
        lines.append(f"{icon} <b>{map_name:<10}</b> | {score} | K/D: {kd} | {when}")

    return "\n".join(lines)


def format_recent(nickname: str, matches: list, current_elo: int) -> str:
    """Aggregate stats over the recent matches list produced by handlers/last.py."""
    if not matches:
        return f"😔 Нет недавних матчей для <b>{nickname}</b>"

    n = len(matches)
    wins = sum(1 for m in matches if str(m.get("result")) == "1")
    losses = n - wins
    win_rate = round(wins / n * 100, 1)

    kds = [m.get("kd") for m in matches if isinstance(m.get("kd"), (int, float))]
    avg_kd = round(sum(kds) / len(kds), 2) if kds else "—"

    # Per-map breakdown
    map_stats: dict[str, list[int]] = {}
    for m in matches:
        mp = (m.get("map") or "?").replace("de_", "")
        map_stats.setdefault(mp, [0, 0])
        if str(m.get("result")) == "1":
            map_stats[mp][0] += 1
        else:
            map_stats[mp][1] += 1

    top_maps = sorted(map_stats.items(), key=lambda kv: kv[1][0] + kv[1][1], reverse=True)[:5]
    map_lines = [
        f"  • <b>{mp:<10}</b> {w}W / {l}L"
        for mp, (w, l) in top_maps
    ]

    streak_icon = "🔥" if wins >= n * 0.7 else "🧊" if wins <= n * 0.3 else "📊"

    return (
        f"{streak_icon} <b>{nickname}</b> — последние {n} матчей\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏆 ELO сейчас: <b>{current_elo}</b>\n"
        f"✅ Побед: <b>{wins}</b>  ❌ Поражений: <b>{losses}</b>\n"
        f"📈 Win Rate: <b>{win_rate}%</b>\n"
        f"⚔️ Средний K/D: <b>{avg_kd}</b>\n"
        f"\n"
        f"🗺 По картам:\n" + "\n".join(map_lines)
    )


def format_compare(p1: dict, s1: dict, p2: dict, s2: dict) -> str:
    """Format side-by-side comparison of two players."""
    n1 = p1.get("nickname", "Player1")
    n2 = p2.get("nickname", "Player2")

    def elo(p):
        return p.get("games", {}).get("cs2", {}).get("faceit_elo", 0)

    def stat(s, key):
        try:
            return float(s.get("lifetime", {}).get(key, 0))
        except (ValueError, TypeError):
            return 0.0

    e1, e2 = elo(p1), elo(p2)
    kd1 = stat(s1, "Average K/D Ratio")
    kd2 = stat(s2, "Average K/D Ratio")
    wr1 = stat(s1, "Win Rate %")
    wr2 = stat(s2, "Win Rate %")
    hs1 = stat(s1, "Average Headshots %")
    hs2 = stat(s2, "Average Headshots %")

    def cmp(v1, v2):
        if v1 > v2:
            return "🟢", "⚪"
        if v1 < v2:
            return "⚪", "🟢"
        return "🟡", "🟡"

    e_c1, e_c2 = cmp(e1, e2)
    kd_c1, kd_c2 = cmp(kd1, kd2)
    wr_c1, wr_c2 = cmp(wr1, wr2)
    hs_c1, hs_c2 = cmp(hs1, hs2)

    wins1 = sum([e1 > e2, kd1 > kd2, wr1 > wr2, hs1 > hs2])
    wins2 = sum([e2 > e1, kd2 > kd1, wr2 > wr1, hs2 > hs1])

    verdict = (
        f"🏆 <b>{n1}</b> лидирует {wins1}/4"
        if wins1 > wins2 else
        f"🏆 <b>{n2}</b> лидирует {wins2}/4"
        if wins2 > wins1 else
        "🤝 Ничья!"
    )

    return (
        f"⚔️ <b>{n1}</b> vs <b>{n2}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"         {n1:<12} {n2}\n"
        f"ELO:  {e_c1} {e1:<8}  {e_c2} {e2}\n"
        f"K/D:  {kd_c1} {kd1:<8}  {kd_c2} {kd2}\n"
        f"Win%: {wr_c1} {wr1:<8}  {wr_c2} {wr2}\n"
        f"HS%:  {hs_c1} {hs1:<8}  {hs_c2} {hs2}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{verdict}"
    )
