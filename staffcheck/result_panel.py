"""Update compact result sections on StaffcheckView."""

SECTION_IDLE_TOOLTIPS = {
    "user_report": (
        "User Report\n"
        "Checks:\n"
        "• Account age (minimum 60 days)\n"
        "• Needs warning talk\n"
        "• Gamertag in notes\n"
        "• Needs to be spoken to\n"
        "• Needs mic check\n"
        "• Anti-alliance note"
    ),
    "search": (
        "Search\n"
        "Checks:\n"
        "• Gamertag exists\n"
        "• Total friends\n"
        "• Completion / gamerscore\n"
        "• Partial matches (of total)\n"
        "• Exact matches (of total)\n"
        "• Alts found\n"
        "• Has verified"
    ),
    "invite_tracker": (
        "Invite Tracker\n"
        "Checks:\n"
        "• Invited by\n"
        "• Has joined Ashen (times)\n"
        "• People invited"
    ),
    "sot_official": (
        "SOT Official\n"
        "Checks:\n"
        "• All messages\n"
        "• Alliance messages\n"
        "• Hourglass messages\n"
        "• Other flagged messages"
    ),
}


def _section(view, key):
    return view.result_sections[key]


def reset_all(view) -> None:
    for section in view.result_sections.values():
        section.reset()
    _hide_flagged_messages(view)


def _hide_flagged_messages(view) -> None:
    sec = view.result_sections.get("flagged_messages")
    if sec is not None:
        sec.setVisible(False)


def _flagged_messages_detail(messages: list) -> str:
    lines = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = str(msg.get("content") or "").strip()
        if content:
            lines.append(content)
    return "\n".join(lines)


def _apply_flagged_messages(view, response: dict) -> None:
    """Show Flagged Messages only when count > 0; otherwise hide."""
    sec = view.result_sections.get("flagged_messages")
    if sec is None:
        return

    try:
        count = int(response.get("flagged_alert_count") or 0)
    except (TypeError, ValueError):
        count = 0
    messages = response.get("flagged_alert_messages") or []
    if not isinstance(messages, list):
        messages = []

    if count <= 0:
        sec.reset()
        sec.setVisible(False)
        return

    detail = _flagged_messages_detail(messages) or f"Flagged messages: {count}"
    sec.clear_fields()
    sec.set_field(
        "flagged_count",
        "Flagged messages",
        str(count),
        is_issue=True,
        detail=detail,
    )
    sec.set_success_or_issues()
    sec.setVisible(True)


def mutual_servers_apply(view, guilds: list[str]) -> None:
    view.result_sections["mutual_servers"].set_guilds(guilds)


def mutual_servers_reset(view) -> None:
    if "mutual_servers" in view.result_sections:
        view.result_sections["mutual_servers"].reset()


def user_report_failed(view, message: str) -> None:
    sec = _section(view, "user_report")
    sec.clear_fields()
    sec.set_state("failed", error_message=message)


def user_report_apply(view, response: dict, *, xbox_gt) -> None:
    sec = _section(view, "user_report")
    sec.clear_fields()
    r = response

    sec.set_field(
        "account_age",
        "Account age",
        f"{r['account_age']} days",
        is_issue=r["account_age"] < 60,
        detail=f"Account age: {r['account_age']} days (minimum 60)",
    )
    sec.set_field(
        "needs_warning_talk",
        "Needs warning talk",
        str(r["needs_warning_talk"]),
        is_issue=bool(r["needs_warning_talk"]),
        detail=f"Needs warning talk: {r['needs_warning_talk']}",
    )
    sec.set_field(
        "gamertag_in_notes",
        "Gamertag in notes",
        str(r["gamertag_in_notes"]),
        is_issue=not r["gamertag_in_notes"] and bool(xbox_gt),
        detail=f"Gamertag in notes: {r['gamertag_in_notes']}",
    )
    sec.set_field(
        "needs_to_be_spoken_to",
        "Needs to be spoken to",
        str(r["needs_to_be_spoken_to"]),
        is_issue=bool(r["needs_to_be_spoken_to"]),
        detail=f"Needs to be spoken to: {r['needs_to_be_spoken_to']}",
    )
    sec.set_field(
        "needs_mic_check",
        "Needs mic check",
        str(r["needs_mic_check"]),
        is_issue=bool(r["needs_mic_check"]),
        detail=f"Needs mic check: {r['needs_mic_check']}",
    )
    sec.set_field(
        "anti_alliance_note",
        "Anti-alliance note",
        str(r["anti_alliance_note"]),
        is_issue=bool(r["anti_alliance_note"]),
        detail=f"Anti-alliance note: {r['anti_alliance_note']}",
    )
    sec.set_success_or_issues()

    issues = {
        "Account Age": r["account_age"] < 60,
        "Needs Warning Talk": r["needs_warning_talk"],
        "Gamertag in Notes": not r["gamertag_in_notes"] and xbox_gt,
        "Needs to be Spoken To": r["needs_to_be_spoken_to"],
        "Needs Mic Check": r["needs_mic_check"],
        "Anti Alliance Note": r["anti_alliance_note"],
    }
    view.loghistory_issues = [k for k, v in issues.items() if v]


def user_report_skipped(view) -> None:
    sec = _section(view, "user_report")
    sec.clear_fields()
    sec.set_field(
        "gamertag_in_notes",
        "Gamertag in notes",
        "Not checked",
        is_issue=True,
        detail="Gamertag in notes: not checked (wrong channel)",
    )
    sec.set_state("issues")
    view.loghistory_issues = ["Gamertag in Notes"]


def search_failed(view, message: str = "Failed") -> None:
    sec = _section(view, "search")
    sec.clear_fields()
    sec.set_state("failed", error_message=message)


def search_skipped(view) -> None:
    sec = _section(view, "search")
    sec.clear_fields()
    sec.set_state("failed", error_message="Not sent (#on-duty-commands only)")


def _completion_detail(r: dict) -> str:
    if "gamerscore_current" in r and "gamerscore_required" in r:
        return (
            f"Gamerscore: {r['gamerscore_current']}/{r['gamerscore_required']} "
            f"(achieved: {r['completion_achieved']})"
        )
    if "gamerscore" in r:
        return f"Gamerscore: {r['gamerscore']} (achieved: {r['completion_achieved']})"
    return f"Completion achieved: {r['completion_achieved']}"


def search_apply(view, response: dict) -> None:
    sec = _section(view, "search")
    sec.clear_fields()
    r = response

    total_matches = int(r["total_matches"])
    partial_matches = int(r["partial_matches"])
    exact_matches = int(r["exact_matches"])
    match_total = str(total_matches)

    sec.set_field(
        "gamertag_exists",
        "Gamertag exists",
        str(r["gamertag_exists"]),
        is_issue=not r["gamertag_exists"],
        detail=f"Gamertag exists: {r['gamertag_exists']}",
    )
    sec.set_field(
        "total_friends",
        "Total friends",
        str(r["total_friends"]),
        is_issue=False,
        detail=f"Total friends: {r['total_friends']}",
    )
    sec.set_field(
        "completion",
        "Completion",
        str(r["completion_achieved"]),
        is_issue=not r["completion_achieved"],
        detail=_completion_detail(r),
    )
    sec.set_field(
        "partial_matches",
        "Partial matches",
        f"{partial_matches}/{match_total}",
        is_issue=partial_matches > 0,
        detail=f"Partial matches: {partial_matches}/{match_total}",
    )
    sec.set_field(
        "exact_matches",
        "Exact matches",
        f"{exact_matches}/{match_total}",
        is_issue=exact_matches > 0,
        detail=f"Exact matches: {exact_matches}/{match_total}",
    )
    sec.set_field(
        "alts_found",
        "Alts found",
        str(r["alts_found"]),
        is_issue=r["alts_found"] != "0",
        detail=f"Alts found: {r['alts_found']}",
    )
    sec.set_field(
        "has_verified",
        "Has verified",
        str(r["has_verified"]),
        is_issue=not r["has_verified"],
        detail=f"Has verified: {r['has_verified']}",
    )
    sec.set_success_or_issues()


def invite_failed(view) -> None:
    sec = _section(view, "invite_tracker")
    sec.clear_fields()
    sec.set_state("failed", error_message="Failed")


def invite_apply(view, response: dict) -> None:
    sec = _section(view, "invite_tracker")
    sec.clear_fields()
    r = response

    inviter = "Unknown"
    for name in r["inviters_names"]:
        if name != "Unknown":
            inviter = name
            break

    times = len(r["inviters_names"])
    invited_count = len(r["invitees_ids"])

    sec.set_field(
        "invited_by",
        "Invited by",
        inviter,
        is_issue=False,
        detail=f"Invited by: {inviter}",
    )
    sec.set_field(
        "times_invited",
        "Has joined Ashen",
        f"{times} time{'s' if times != 1 else ''}",
        is_issue=len(r["inviters_ids"]) >= 5,
        detail=f"Has joined Ashen: {times} time(s)",
    )
    sec.set_field(
        "num_invited",
        "People invited",
        str(invited_count),
        is_issue=len(r["invitees_ids"]) >= 5,
        detail=f"People invited: {invited_count}",
    )
    sec.set_success_or_issues()


def sot_failed(view, message: str = "Failed", response: dict | None = None) -> None:
    sec = _section(view, "sot_official")
    sec.clear_fields()
    sec.set_state("failed", error_message=message)
    if response is not None:
        _apply_flagged_messages(view, response)
    else:
        _hide_flagged_messages(view)


def sot_apply(view, response: dict) -> None:
    sec = _section(view, "sot_official")
    sec.clear_fields()
    r = response

    sec.set_field(
        "total_messages",
        "All messages",
        str(r["total_messages"]),
        is_issue=False,
        detail=f"All messages: {r['total_messages']}",
    )
    sec.set_field(
        "alliance",
        "Alliance messages",
        str(len(r["alliance_messages"])),
        is_issue=False,
        detail=f"Alliance messages: {len(r['alliance_messages'])}",
    )
    sec.set_field(
        "hourglass",
        "Hourglass messages",
        str(len(r["hourglass_messages"])),
        is_issue=len(r["hourglass_messages"]) > 0,
        detail=f"Hourglass messages: {len(r['hourglass_messages'])}",
    )
    sec.set_field(
        "bad_words",
        "Other flagged messages",
        str(len(r["other_messages"])),
        is_issue=len(r["other_messages"]) > 0,
        detail=f"Other flagged messages: {len(r['other_messages'])}",
    )
    sec.set_success_or_issues()
    _apply_flagged_messages(view, response)
