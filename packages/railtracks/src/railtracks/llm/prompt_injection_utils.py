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


def fill_prompt(prompt: str, value_dict: ValueDict) -> str:
    """
    Fills a prompt using the railtracks context object as its source of truth
    """
    return KeyOnlyFormatter().vformat(prompt, (), value_dict)
