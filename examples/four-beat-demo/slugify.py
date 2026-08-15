"""The prop: the file the agent's PR touched. The exhibit is the gate."""
import re


def slugify(text: str) -> str:
    """Lowercase, collapse every non-alphanumeric run to one hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
