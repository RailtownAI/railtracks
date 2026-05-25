import string


class KeyOnlyFormatter(string.Formatter):
    """
    A simple formatter which will only use keyword arguments to fill placeholders.
    """

    def vformat(self, format_string, args, kwargs):
        result: list[str] = []
        index = 0

        while index < len(format_string):
            char = format_string[index]

            if char == "{":
                if index + 1 < len(format_string) and format_string[index + 1] == "{":
                    result.append("{")
                    index += 2
                    continue

                end_index = format_string.find("}", index + 1)
                if end_index == -1:
                    result.append(char)
                    index += 1
                    continue

                key = format_string[index + 1:end_index]
                try:
                    result.append(str(kwargs[key]))
                except KeyError:
                    result.append(f"{{{key}}}")
                index = end_index + 1
                continue

            if char == "}":
                if index + 1 < len(format_string) and format_string[index + 1] == "}":
                    result.append("}")
                    index += 2
                    continue

            result.append(char)
            index += 1

        return "".join(result)

    def get_value(self, key, args, kwargs):
        try:
            return kwargs[str(key)]
        except KeyError:
            return f"{{{key}}}"


class ValueDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"  # Return the placeholder if not found
