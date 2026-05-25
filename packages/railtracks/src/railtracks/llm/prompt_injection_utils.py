import string


class KeyOnlyFormatter(string.Formatter):
    """
    A simple formatter which will only use keyword arguments to fill placeholders.
    """

    def vformat(self, format_string, args, kwargs):
        try:
            parsed_format = self.parse(format_string)
            return "".join(
                self._format_part(
                    literal_text, field_name, format_spec, conversion, kwargs
                )
                for literal_text, field_name, format_spec, conversion in parsed_format
            )
        except ValueError:
            return format_string

    def _format_part(self, literal_text, field_name, format_spec, conversion, kwargs):
        if field_name is None:
            return literal_text

        original_placeholder = f"{{{field_name}"
        if conversion:
            original_placeholder += f"!{conversion}"
        if format_spec:
            original_placeholder += f":{format_spec}"
        original_placeholder += "}"

        if conversion or format_spec or field_name not in kwargs:
            return f"{literal_text}{original_placeholder}"

        return f"{literal_text}{kwargs[field_name]}"

    def get_value(self, key, args, kwargs):
        try:
            return kwargs[str(key)]
        except KeyError:
            return f"{{{key}}}"


class ValueDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"  # Return the placeholder if not found
