import datetime
import os
from typing import List

import pickle

from src.requestcompletion.context import BaseContext
from .profiling import Stamp

from ..state.node import NodeForest
from ..state.request import RequestForest

FILENAME_TEMPLATE = "data/c3-runs/{0}.pickle"


# TODO update this to the new normalized execution info object.
def save_run(
    all_stamps: List[Stamp],
    request_heap: RequestForest,
    node_heap: NodeForest,
    context: BaseContext,
    version: str,
    save_path: str,
):
    """
    Saves the given RC state and any relevant content to a file in the given directory with the following naming
     convention: {your path}/"%Y-%m-%d-%H-%M-%S".pickle
    """
    save_path += "/{0}.pickle"
    file_name = save_path.format(datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
    with open(file_name, "wb") as f:
        save = {
            "stamps": all_stamps,
            "request_heap": request_heap,
            "node_heap": node_heap,
            "version": version,
            "date": datetime.datetime.now(),
            "env_vars": os.environ,
            "context": context,
        }

        pickle.dump(
            save,
            f,
        )
