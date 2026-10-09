import json
from collections.abc import Mapping, Sequence

USER_ATTRIBUTES_HEADER = "X-Lightdash-User-Attributes"

AttributeValue = str | Sequence[str]


def build_header(*, attributes: Mapping[str, AttributeValue]) -> dict[str, str]:
    """
    Return the header Lightdash uses to narrow row-level security for a request.
    """
    return {USER_ATTRIBUTES_HEADER: json.dumps(attributes)}
