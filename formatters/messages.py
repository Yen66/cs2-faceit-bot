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
    """Format Unix-seconds timestamp as DD.MM (local time)."""
    if not timestamp_s:
        return "?"
    dt = datetime.fromtimestamp(timestamp_s)
    return dt.strftime("%d.%m")


def format_stats(player: dict, stats: dict, avg_kills: float | None = None) -> str:
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
    adr = lifetime.get("ADR", "—")

    kills_line = (
        f"💀 Avg kills (20 м): <b>{avg_kills}</b>\n"
        if avg_kills is not None
        else ""
    )

    return (
        f"👤 <b>{nickname}</b>  {flag}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏆 ELO: <b>{elo}</b>  |  Уровень: <b>{level}</b> {level_emoji}\n"
        f"⚔️ K/D: <b>{kd}</b>\n"
        f"💥 ADR: <b>{adr}</b>\n"
        f"🎯 Хедшоты: <b>{hs}%</b>\n"
        f"🏅 Win Rate: <b>{win_rate}%</b>\n"
        f"{kills_line}"
        f"📊 Матчей: <b>{matches}</b>\n"
    )


def format_last_matches(nickname: str, matches_data: list, avg_kills: float | None = None) -> str:
    """Format last N matches as a monospace table."""
    if not matches_data:
        return f"😔 Нет матчей для <b>{nickname}</b>"

    header = f"📋 <b>Последние матчи — {nickname}</b>\n\n"

    def _round1(v):
        if v in (None, "—", "?"):
            return "—"
        try:
            return str(round(float(v), 1))
        except (ValueError, TypeError):
            return "—"

    col_header = f"   <code>{'Карта':<6} {'Счёт':<5} {'K':>2} {'D':>2} {'A':>2} {'ADR':>5} {'K/D':>4}</code>\n"
    separator = f"   <code>{'─' * 33}</code>\n"

    rows = ""
    for m in matches_data:
        icon = "🟢" if m.get("result") == "1" else "🔴"
        map_name = m.get("map", "?").replace("de_", "")[:6]
        score = (m.get("score") or "?").replace(" ", "")
        k = str(m.get("kills", "—"))
        d = str(m.get("deaths", "—"))
        a = str(m.get("assists", "—"))
        adr = _round1(m.get("adr"))
        kd = _round1(m.get("kd"))

        data = f"{map_name:<6} {score:<5} {k:>2} {d:>2} {a:>2} {adr:>5} {kd:>4}"
        rows += f"{icon} <code>{data}</code>\n"

    footer = ""
    if avg_kills is not None:
        footer = f"\n💀 Avg kills за {len(matches_data)} матчей: <b>{avg_kills}</b>"

    return header + col_header + separator + rows + footer


def format_recent(nickname: str, matches: list, current_elo: int) -> str:
    """Aggregate stats over the recent matches list produced by handlers/last.py."""
    if not matches:
        return f"😔 Нет недавних матчей для <b>{nickname}</b>"

    n = len(matches)
    wins = sum(1 for m in matches if str(m.get("result")) == "1")
    losses = n - wins
    win_rate = round(wins / n * 100, 1)

    kds = [m.get("kd") for m in matches if isinstance(m.get("kd"), (int, float))]
    avg_kd = round(sum(kds) / len(kds), 1) if kds else "—"

    adrs = [m.get("adr") for m in matches if isinstance(m.get("adr"), (int, float))]
    avg_adr = round(sum(adrs) / len(adrs), 1) if adrs else "—"

    kills_vals = [m.get("kills") for m in matches if isinstance(m.get("kills"), int)]
    avg_kills = round(sum(kills_vals) / len(kills_vals), 1) if kills_vals else "—"

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
        f"💥 Средний ADR: <b>{avg_adr}</b>\n"
        f"💀 Средние kills: <b>{avg_kills}</b>\n"
        f"\n"
        f"🗺 По картам:\n" + "\n".join(map_lines)
    )


def format_compare_recent(p1: dict, a1: dict, p2: dict, a2: dict) -> str:
    """Side-by-side comparison based on aggregated last-N matches."""
    n1 = p1.get("nickname", "Player1")
    n2 = p2.get("nickname", "Player2")

    def elo(p):
        return p.get("games", {}).get("cs2", {}).get("faceit_elo", 0)

    e1, e2 = elo(p1), elo(p2)
    kd1, kd2 = a1.get("avg_kd", 0.0), a2.get("avg_kd", 0.0)
    wr1, wr2 = a1.get("win_rate", 0.0), a2.get("win_rate", 0.0)
    hs1, hs2 = a1.get("avg_hs", 0.0), a2.get("avg_hs", 0.0)
    adr1, adr2 = a1.get("avg_adr", 0.0), a2.get("avg_adr", 0.0)
    k1, k2 = a1.get("avg_kills", 0.0), a2.get("avg_kills", 0.0)
    samples1 = a1.get("n", 0)
    samples2 = a2.get("n", 0)

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
    adr_c1, adr_c2 = cmp(adr1, adr2)
    k_c1, k_c2 = cmp(k1, k2)

    wins1 = sum([e1 > e2, kd1 > kd2, adr1 > adr2, k1 > k2, wr1 > wr2, hs1 > hs2])
    wins2 = sum([e2 > e1, kd2 > kd1, adr2 > adr1, k2 > k1, wr2 > wr1, hs2 > hs1])

    verdict = (
        f"🏆 <b>{n1}</b> лидирует {wins1}/6"
        if wins1 > wins2 else
        f"🏆 <b>{n2}</b> лидирует {wins2}/6"
        if wins2 > wins1 else
        "🤝 Ничья!"
    )

    return (
        f"⚔️ <b>{n1}</b> vs <b>{n2}</b>\n"
        f"<i>по последним 20 матчам</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"         {n1:<12} {n2}\n"
        f"ELO:  {e_c1} {e1:<8}  {e_c2} {e2}\n"
        f"K/D:  {kd_c1} {kd1:<8}  {kd_c2} {kd2}\n"
        f"ADR:  {adr_c1} {adr1:<8}  {adr_c2} {adr2}\n"
        f"Kills:{k_c1} {k1:<8}  {k_c2} {k2}\n"
        f"Win%: {wr_c1} {wr1:<8}  {wr_c2} {wr2}\n"
        f"HS%:  {hs_c1} {hs1:<8}  {hs_c2} {hs2}\n"
        f"Выборка: {samples1} / {samples2} матчей\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{verdict}"
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
