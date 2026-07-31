import datetime

from pydantic import BaseModel

from railtracks.utils.json.encoder import RTJSONEncoder


class RTObserverEncoder(RTJSONEncoder):
    """
    Custom JSON encoder for Railtracks objects.
    """

    def default(self, o):
        try:
            if isinstance(o, datetime.datetime):
                return o.isoformat()
            if isinstance(o, type) and issubclass(o, BaseModel):
                return {
                    "name": o.__name__,
                    "fields": [
                        {"name": k, "type": self._type_name(v.annotation)}
                        for k, v in o.model_fields.items()
                    ],
                }
            return super().default(o)
        except TypeError:
            return str(o)
        except Exception as e:
            return f"Error encoding object of type {type(o).__name__}: {str(e)}"

    def _type_name(self, tp) -> str:
        return getattr(tp, "__name__", None) or str(tp)
