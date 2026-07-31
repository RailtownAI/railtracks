from __future__ import annotations

import json

from pydantic import BaseModel

from .encodable import Encodable


class RTJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Encodable):
            return o.encode()
        if isinstance(o, BaseModel):
            return o.model_dump(mode="json")
        try:
            return super().default(o)
        except TypeError:
            return f"< Unable to serialize {type(o)} > " + str(o)
