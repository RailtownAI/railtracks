import string
import requestcompletion as rc
from ..context.central import get_config
from ..llm import MessageHistory, Message

import regex
import logging
from abc import abstractmethod
import datetime

logger = logging.getLogger(__name__)


class KeyOnlyFormatter(string.Formatter):
    def get_value(self, key, args, kwargs):
        try:
            return kwargs[str(key)]
        except KeyError:
            return f"{{{key}}}"


class _ContextDict(dict):
    def __getitem__(self, key):
        return rc.context.get(key)

    def __missing__(self, key):
        return f"{{{key}}}"  # Return the placeholder if not found


def fill_prompt(prompt: str) -> str:
    return KeyOnlyFormatter().vformat(prompt, (), _ContextDict())


def inject_context(message_history: MessageHistory):
    """
    Injects the context from the current request into the prompt.

    Args:
        message_history (MessageHistory): The prompts to inject context into.

    """
    if get_config().prompt_injection:
        for i, message in enumerate(message_history):
            if message.inject_prompt and isinstance(message.content, str):
                try:
                    message_history[i] = Message(
                        role=message.role.value,
                        content=fill_prompt(message.content),
                        inject_prompt=False,
                    )
                except ValueError:
                    pass

    return message_history


class PromptBase:
    """
    Abstract base class for prompt templates, enforcing custom creation via several sub-methods.
    Child classes must implement the set_* methods that initialize key members and metadata.
    Instantiation directly is possible (with all args), but discouraged in favor of subclassing.
    """

    def __init__(
        self,
        description: str = "",
        description_long: str = "",
        prompt_base: str = "",
        prompt_pieces_available: list = None,
        prompt_pieces_default_value: dict = None,
        prompt_predefine_value: dict = None,
        name: str = "",
        tags: list = None,
        author: str = "",
        version: str = "",
        timestamp: str = "",
        tools: list = None,
        expected_config: dict = None,
        example: dict = None,
        verbose: bool = False,
    ):
        self.verbose = verbose

        # Instance field setup with safe defaults
        self.description = description
        self.description_long = description_long

        self.prompt_base = prompt_base or ""
        self.prompt_pieces_available = prompt_pieces_available if prompt_pieces_available is not None else []
        self.prompt_pieces_default_value = prompt_pieces_default_value if prompt_pieces_default_value is not None else {}
        self.prompt_predefine_value = prompt_predefine_value if prompt_predefine_value is not None else {}

        self.name = name
        self.tags = tags if tags is not None else []
        self.author = author
        self.version = version or "0"
        self.timestamp = timestamp
        self.tools = tools if tools is not None else []
        self.expected_config = expected_config if expected_config is not None else {}
        self.example = example if example is not None else {"sample_piece": "", "sample_response": ""}

        self.associated_prompt = {}
        self.associated_prompt_names = []

        # Delegate to subclass "set_*" logic if not given in init
        self.set_tools()
        self.set_associated_prompt()
        self.associated_prompt_names = list(self.associated_prompt.keys())

        if not self.prompt_base:
            self.set_prompt_base()
        if not self.name:
            self.set_name()
        if not self.prompt_pieces_available:
            self.set_prompt_pieces_available()
        if not self.prompt_pieces_default_value:
            self.set_prompt_pieces_default_value()
        if not self.prompt_predefine_value:
            self.set_prompt_predefine_value()

        # Post-processing and required validation
        self._check_default_prompt_pieces()
        self._check_required_fields()

    ###### Abstract set_* methods for subclass implementation #######

    @abstractmethod
    def set_prompt_base(self):
        """
        Subclass defines self.prompt_base (template str).
        """
        raise NotImplementedError("Implement set_prompt_base in the subclass.")

    @abstractmethod
    def set_prompt_predefine_value(self):
        """
        Subclass defines self.prompt_predefine_value (dict with keys to replace in prompt).
        """
        self.prompt_predefine_value = {
            "<<DATETIME>>": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @abstractmethod
    def set_prompt_pieces_default_value(self):
        """
        Subclass defines self.prompt_pieces_default_value (dict with defaults for prompt pieces).
        """
        # Safe fallback: all available keys get an ""
        for piece in self.prompt_pieces_available:
            if piece not in self.prompt_pieces_default_value:
                self.prompt_pieces_default_value[piece] = ""
                if self.verbose:
                    logger.warning(
                        f"Default for '{piece}' not set in class '{self.name}'; using empty string."
                    )

    @abstractmethod
    def set_prompt_pieces_available(self):
        """
        Subclass defines self.prompt_pieces_available as a list.
        Default: extract {key} names from prompt_base.
        """
        self.prompt_pieces_available = regex.findall(r"\{(.*?)\}", self.prompt_base)
        if self.verbose:
            logger.info(f"Pieces for {self.name}: {self.prompt_pieces_available}")

    @abstractmethod
    def set_name(self):
        """
        Subclass sets self.name. Default: class name.
        """
        self.name = self.__class__.__name__
        if self.verbose:
            logger.info(f"No name set; using class name: {self.name}")

    @abstractmethod
    def set_tools(self):
        """
        Subclass sets self.tools (identifiers of allowed tools).
        """
        self.tools = []

    @abstractmethod
    def set_associated_prompt(self):
        """
        Subclass sets .associated_prompt (other PromptBase instances by key).
        """
        self.associated_prompt = {}

    ###### Validation logic #######

    def _check_default_prompt_pieces(self):
        """
        Ensure default/available prompt pieces coverage and validity.
        """
        # Fill in any missing prompt_pieces_default_value with empty string.
        for key in self.prompt_pieces_available:
            if key not in self.prompt_pieces_default_value:
                self.prompt_pieces_default_value[key] = ""
                if self.verbose:
                    logger.warning(
                        f"Piece '{key}' is available but had no default; setting '' for {self.name}."
                    )

        # Error if anything in defaults isn't in allowed
        for key in self.prompt_pieces_default_value.keys():
            if key not in self.prompt_pieces_available:
                raise ValueError(
                    f"Prompt piece '{key}' in defaults, but not in prompt_pieces_available. Allowed: {self.prompt_pieces_available}"
                )

    def _check_required_fields(self):
        """
        Ensure all mandatory fields are set.
        """
        for param in ["prompt_base", "name", "version"]:
            val = getattr(self, param)
            if not val:
                raise ValueError(f"Required parameter '{param}' not set for '{type(self).__name__}'.")

    ###### API #######

    def get_metadata(self) -> dict:
        """
        Return a (JSON serializable) dictionary describing this PromptBase.
        """
        # Validate types
        for attr, expected in [
            ("expected_config", dict),
            ("example", dict),
            ("tags", list),
            ("tools", list),
            ("associated_prompt", dict),
        ]:
            if not isinstance(getattr(self, attr), expected):
                raise ValueError(f"{attr} must be of type {expected.__name__} for '{self.name}'.")

        return {
            "prompt_base": self.prompt_base,
            "description": self.description,
            "description_long": self.description_long,
            "name": self.name,
            "default_prompt_pieces": self.prompt_pieces_default_value,
            "predefine_prompt_pieces": self.prompt_predefine_value,
            "tags": self.tags,
            "author": self.author,
            "version": self.version,
            "timestamp": self.timestamp,
            "tools": self.tools,
            "expected_config": self.expected_config,
            "example": self.example,
            "associated_prompt_names": list(self.associated_prompt.keys())
        }

    def get_prompt(self, prompt_pieces: dict = None, no_warning: bool = False) -> str:
        """
        Fill the prompt_base string's placeholders with provided (or default) prompt_pieces and predef macros.
        """
        prompt_pieces = prompt_pieces or {}

        # Validate prompt input keys
        for key in prompt_pieces:
            if key not in self.prompt_pieces_default_value:
                logger.error(
                    f"Invalid piece '{key}' in prompt input for {self.name}. Allowed: {list(self.prompt_pieces_default_value.keys())}"
                )
                raise ValueError(
                    f"Key '{key}' is not allowed in prompt_pieces for {self.name}."
                )

        result = self.prompt_base

        # Substitute all {var}
        for key in self.prompt_pieces_available:
            if key in prompt_pieces and prompt_pieces[key] is not None:
                value = str(prompt_pieces[key])
            elif key in self.prompt_pieces_default_value and self.prompt_pieces_default_value[key] is not None:
                value = str(self.prompt_pieces_default_value[key])
            else:
                logger.error(
                    f"Prompt piece '{key}' required in prompt input for {self.name}; none given and no default."
                )
                raise ValueError(
                    f"Prompt piece '{key}' must be provided for {self.name}."
                )
            result = result.replace(f"{{{key}}}", value)

        # Substitute all <<VAR>>
        for key, v in self.prompt_predefine_value.items():
            result = result.replace(key, str(v))

        # Warn about remaining <<VAR>>
        if not no_warning:
            for unmatched in regex.findall(r"<<(.*?)>>", result):
                if f"<<{unmatched}>>" not in self.prompt_predefine_value:
                    logger.warning(
                        f"Unresolved macro '<<{unmatched}>>' in rendered prompt for {self.name}."
                    )
        return result

    @staticmethod
    def _escape_braces(line: str) -> str:
        """
        Make unmatched { or } into double braces for safe formatting.
        """
        # Replace single {, unless already part of {{
        escaped = regex.sub(r'(?<!{){(?!{)', '{{', line)
        escaped = regex.sub(r'(?<!})}(?!})', '}}', escaped)
        return escaped

    @property
    def get_prompt_base(self) -> str:
        return self.prompt_base
