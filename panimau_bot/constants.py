FILE_EMOJIS = {
    "photo": "📸",
    "video": "🎥",
    "audio": "🎵",
    "voice": "🎤",
    "document": "📄",
    "animation": "🎬",
    "sticker": "🎨",
    "youtube": "▶️",
    "instagram": "🎞️",
    "tiktok": "🎵",
}

SOCIAL_PLATFORM_LABELS = {
    "youtube": "шортс",
    "instagram": "рилс",
    "tiktok": "тикток",
}

SOCIAL_URL_FILTER_PATTERN = (
    r"(youtube\.com/shorts/|youtu\.be/|instagram\.com/(?:[^/\s]+/)?reels?/|"
    r"(?:vm|vt)\.tiktok\.com/|tiktok\.com/@[^/\s]+/video/)"
)

REACTION_CHOICES = ["🔥", "😎", "👍", "👎", "🤡"]
