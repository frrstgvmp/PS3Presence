"""Release metadata and the final, calibrated garland positions."""

VERSION = "0.7.1 beta"
RELEASE_VERSION = VERSION.replace(" ", "-")

# Public author contact; separate from the player's PSN/Discord account.
AUTHOR_DISCORD_USERNAME = "lapamivverh"
AUTHOR_DISCORD_USER_ID = "308300626062737411"
GITHUB_REPOSITORY_URL = "https://github.com/frrstgvmp/PS3Presence"
GITHUB_ISSUES_URL = GITHUB_REPOSITORY_URL + "/issues"

# Defaults shipped with the app, without copying the user's private settings.
# Previously saved per-user adjustments remain valid and override these values.
DEFAULT_LIGHT_OFFSETS = {
    "0": (-2, 1), "1": (-2, -1), "2": (-6, 1), "3": (3, 2),
    "4": (-3, 2), "5": (-3, 1), "6": (-3, 3), "7": (0, 0),
    "8": (-1, -12), "9": (-6, -7), "10": (-8, -2), "11": (-8, 0),
    "12": (-8, -12), "13": (-9, -6), "14": (-9, -6),
    "15": (-12, -6), "16": (-13, -3), "17": (6, -5),
    # Botanical-only low-left bulb: halo centre is 13 px above its hit centre.
    "18": (0, 13),
}
