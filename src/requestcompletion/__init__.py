#   -------------------------------------------------------------
#   Copyright (c) Railtown AI. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------
"""Railtown AI Request Completion Framework for building resilient agentic systems"""

from __future__ import annotations
from dotenv import load_dotenv

from . import nodes
from . import run
from . import exceptions
from . import llm

__all__ = ["nodes", "run", "exceptions", "llm"]

load_dotenv()
# Only change the MAJOR.MINOR if you need to. Do not change the PATCH. (vMAJOR.MINOR.PATCH).
__version__ = "0.1.0"
