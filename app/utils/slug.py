import re
import secrets

_NON_SLUG_CHARS = re.compile(r'[^a-z0-9]+')


def slugify(value: str, max_length: int = 200) -> str:
    """Lowercase, hyphen-separated, URL-safe form of a title."""
    slug = _NON_SLUG_CHARS.sub('-', (value or '').lower()).strip('-')
    slug = slug[:max_length].strip('-')
    return slug or 'course'


def slug_suffix(length: int = 6) -> str:
    """Short random suffix used to disambiguate colliding slugs."""
    return secrets.token_hex(length // 2)


async def generate_unique_slug(repo, title: str, attempts: int = 5) -> str:
    """Slugify a title, adding a short suffix if that slug is already taken.

    `repo` needs an async `slug_exists(slug) -> bool`.
    """
    base = slugify(title)
    if not await repo.slug_exists(base):
        return base

    for _ in range(attempts):
        candidate = f"{base}-{slug_suffix()}"
        if not await repo.slug_exists(candidate):
            return candidate

    raise RuntimeError(f"Could not generate a unique slug for {title!r}")
