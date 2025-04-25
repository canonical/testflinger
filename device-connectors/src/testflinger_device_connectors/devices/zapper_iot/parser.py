"""provision yaml verify."""

import logging
from typing import List

import validators

logger = logging.getLogger(__name__)


def validate_urls(urls: List[str]):
    """Validate whether the provided URL
    is valid in terms of format.

    We cannot assert for resource availability here,
    since this is not the host downloading the content.
    """
    for url in urls:
        if not validators.url(url):
            raise ValueError("url format is not correct")
