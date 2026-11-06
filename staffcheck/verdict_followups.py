"""Follow-up commands the compact Verdict card can run after a Not good verdict."""

FOLLOWUP_NONE = ""
FOLLOWUP_VERIFY = "verify"  # /verify in #on-duty-chat (after posting)
FOLLOWUP_UNPRIVATE = "unprivate"  # modmail + recall Unprivate Xbox (after posting)
FOLLOWUP_JOIN_AWR = "join_awr"  # /joinawr (after posting)
# No-Xbox path only: /verify in the check channel, *before* posting.
FOLLOWUP_LINK_XBOX = "link_xbox"
FOLLOWUP_TELL_VERIFY = "tell_verify"
