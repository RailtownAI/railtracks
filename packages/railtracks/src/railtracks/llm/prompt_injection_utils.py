import string


class KeyOnlyFormatter(string.Formatter):
    """
    A simple formatter which will only use keyword arguments to fill placeholders.
    """

    def get_value(self, key, args, kwargs):
        try:
            return kwargs[str(key)]
        except KeyError:
            return f"{{{key}}}"


class ValueDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"  # Return the placeholder if not found
