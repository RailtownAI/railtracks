from itertools import chain
from typing import List, Dict, Type, Set


from ..state.node import (
    NodeForest,
)
from ..state.request import (
    RequestTemplate,
    RequestForest,
)
from ..tools.profiling import Stamp


from .markdown_utils import (
    format_multiline_for_markdown,
)
from ...nodes.nodes import Node


# TODO migrate this logic into agent-viewer


class SystemStateManager:
    """
    The system state manager is a housing to contain some debugging tools to view many details about any arbitrary
     request graph
    """

    def __init__(self, stamps: List[Stamp], request_heap: RequestForest, node_heap: NodeForest):
        """
        Creates a new instance of a `SystemStateManager` object.

        Args:
            request_graph (RequestGraph): The request graph that you would like to inspect.
        """
        self.stamps = stamps
        self.request_heap = request_heap
        self.node_heap = node_heap

    def view_at_step(self, step: int):
        """
        The view at step creates a markdown view of the request graph at the given step.
        """
        raise NotImplementedError("View at step has not been implemented")
        requests_templates, nodes = self.graph.all_data(step)
        requests, failed_tree, insertion_request = convert_into_requests()

        all_requests = requests + list(chain(*failed_tree)) if failed_tree is not None else [] + [insertion_request]
        all_nodes = collect_nodes(all_requests)

        node_str = "\n".join([self.node_details(node, insertion_request, requests, failed_tree) for node in all_nodes])
        step_log_str = "\n".join([x.identifier for x in self.stamps if x.step == step])

        _str = f"""# Step: {step}
## Currently Executing
{step_log_str}

## Request Ledger
{self.request_info_table(insertion_request, requests, failed_tree)}

## Node Details
{node_str}


"""
        return _str

    def view_full_system_review(self):
        """
        This method creates a markdown string containing details about the entire general system in its current state.


        """
        # TODO implement this in our new system.
        raise NotImplementedError(
            "The system review function has been disabled becuase it needs to fit within the new framework approach"
        )
        request_heap, node_heap = (self.request_heap, self.node_heap)
        request_heap: RequestForest
        node_heap: NodeForest

        execution_detail_data = {"Step": [], "Time (s.)": [], "Info": []}

        node_str = "\n".join(
            [
                self.node_details(node.node, request_heap.heap().values(), node_heap.id_type_mapping)
                for node in node_heap.heap().values()
            ]
        )

        start_time = min([x.time for x in self.stamps])
        for stamp in self.stamps:
            execution_detail_data["Step"].append(str(stamp.step))
            execution_detail_data["Time (s.)"].append(f"{round(stamp.time - start_time, 4)}")
            execution_detail_data["Info"].append(stamp.identifier)

        return f"""# Full System Review
## Execution Detail 
{self.get_table(execution_detail_data)}

## Request Ledger 
{self.request_info_table(active_requests=list(request_heap.heap().values()), dead_requests=request_heap.failure_tree(), id_node_type_mapping=node_heap.id_type_mapping)}

## Node Library
{node_str}

## Time Analysis
TBD

"""

    @classmethod
    def node_details(
        cls,
        node: Node,
        all_request_templates: List[RequestTemplate],
        id_mapping: Dict[str, Type[Node]],
    ):

        _str = f"""{cls.simple_node_details(node, all_request_templates, id_mapping)}
#### Run Details:
{cls.node_run_detail(node)}
"""
        return _str

    @classmethod
    def simple_node_details(
        cls,
        node: Node,
        all_request_templates: List[RequestTemplate],
        id_mapping: Dict[str, Type[Node]],
    ):

        relevant_requests = []
        relevant_requests.extend(
            [r for r in all_request_templates if r.source_id == str(node.uuid) or r.sink_id == str(node.uuid)]
        )

        # note that we have to flatten the failed tree since it is a list of list of requests
        if len(relevant_requests) > 0:
            up, down = cls.request_info_table_for_node(node, relevant_requests, id_mapping)
            request_detail = "\n".join([up, down])
        else:
            request_detail = "*No connected requests*"

        _str = f"""### {node.pretty_name()}
id: {node.uuid} 
#### Current State:
{cls.get_table({'Attribute': list(node.state_details().keys()), 'Data': list(node.state_details().values())})}
#### Requests:
{request_detail}
"""
        return _str

    @classmethod
    def node_run_detail(cls, node: Node):
        profiled = node.profiling_data
        if len(profiled) == 0:
            return "*No History*"

        table = "| Result? | Duration | Exception? |\n"
        table += "| :--- | :---: | :---: |\n"
        table += "\n".join(
            [
                f"| {prettify_node_response(x.final_data) if x.final_data is not None else None} | {round(x.duration, 5)} | {x.exception} |"
                for x in profiled
            ]
        )

        return table

    @classmethod
    def get_table(cls, data) -> str:
        """Creates a table from the provided data dictionary in markdown format."""
        list_len = len(data[list(data.keys())[0]])
        table = "| " + " | ".join(data.keys()) + " |\n"
        table += "| " + " | ".join([":---" for _ in data.keys()]) + " |\n"
        table += "\n".join(["| " + " | ".join([data[k][i] for k in data.keys()]) + " |" for i in range(list_len)])

        return table

    @classmethod
    def request_info_table_for_node(
        cls,
        current_node: Node,
        requests: List[RequestTemplate],
        id_mapping: Dict[str, Type[Node]],
    ):
        upstream = "###### Upstream\n"
        downstream = "###### Downstream\n"

        upstream += "| Source | Duration (s) | Result | ID |\n"
        downstream += "| Sink | Duration (s) | Result | ID |\n"

        table_deliminiter = "| :---: | --- | --- | --- |\n"

        upstream += table_deliminiter
        downstream += table_deliminiter

        has_up = False
        has_down = False
        for r in requests:
            duration = f"{round(r.duration_detail, 5) if r.output is not None else 'N/A'}"
            output_str = format_multiline_for_markdown(repr(r.output))

            if r.sink_id == str(current_node.uuid):
                if r.source_id is None:
                    upstream += f"| START | {duration} | {output_str} | {r.identifier[:5]} |\n"

                else:
                    upstream += f"| {id_mapping[r.source_id].pretty_name()} - ({r.source_id[:5]}) | {duration} | {output_str} | {r.identifier[:5]} |\n"
                has_up = True
                continue
            elif r.source_id == str(current_node.uuid):
                downstream += f"| {id_mapping[r.sink_id].pretty_name()} - ({r.sink_id[:5]}) | {duration} | {output_str} | {r.identifier[:5]} |\n"
                has_down = True

        return upstream if has_up else "", downstream if has_down else ""

    @classmethod
    def request_info_table(
        cls,
        active_requests: List[RequestTemplate],
        dead_requests: Set[Set[RequestTemplate]],
        id_node_type_mapping: Dict[str, Type[Node]],
    ):
        info = "##### Insertion\n"
        insertion_request = [x for x in active_requests if x.source_id is None][0]

        info += cls.get_table(
            {
                "Source": ["START"],
                "Sink": [node_name(insertion_request.sink_id, id_node_type_mapping)],
                "Current Status": [insertion_request.status],
                "Duration": (
                    [str(round(insertion_request.duration_detail, 4))]
                    if insertion_request.output is not None
                    else ["N/A"]
                ),
                "Output?": (
                    [format_multiline_for_markdown(repr(insertion_request.output))]
                    if insertion_request.output is not None
                    else ["None"]
                ),
                "Id": [insertion_request.identifier[:5]],
            }
        )

        active_requests.remove(insertion_request)

        info += "\n"
        info += "##### Normal\n"
        info += cls.get_table(
            {
                "Source": [node_name(x.source_id, id_node_type_mapping) for x in active_requests],
                "Sink": [node_name(x.sink_id, id_node_type_mapping) for x in active_requests],
                "Current Status": [x.status for x in active_requests],
                "Duration": [
                    (str(round(x.duration_detail, 5)) if x.output is not None else "N/A") for x in active_requests
                ],
                "Output?": [
                    (format_multiline_for_markdown(repr(x.output)) if x.output is not None else "None")
                    for x in active_requests
                ],
                "Id": [x.identifier for x in active_requests],
            }
        )

        info += "\n"
        info += "##### Failed\n"
        for i, failed in enumerate(dead_requests):
            info += f"###### Failure {i}\n"

            info += cls.get_table(
                {
                    "Source": [node_name(x.source_id, id_node_type_mapping) for x in failed],
                    "Sink": [node_name(x.sink_id, id_node_type_mapping) for x in failed],
                    "Current Status": [x.status for x in failed],
                    "Duration": [(str(round(x.duration_detail, 5)) if x.output is not None else "N/A") for x in failed],
                    "Output?": [
                        (format_multiline_for_markdown(repr(x.output)) if x.output is not None else "None")
                        for x in failed
                    ],
                    "Id": [x.identifier for x in failed],
                }
            )

        return info

    def time_analysis(self):
        sorted_steps = sorted(list(set([x.step for x in self.stamps])))

        initial_state = self.simplified_view_at_step(0)

        states = [self.simplified_view_at_step(x) for x in sorted_steps]
        diff_detail = ""
        for i in range(len(states) - 1):
            diff_detail += f"## Step {i} -> {i+1}\n"
            diff_detail += f"{', '.join([x.identifier for x in self.stamps if x.step == i])}"

            diff_detail += "Example change" + "\n"

        return f"""
#### Original State
{initial_state}

#### State Changes
{diff_detail}

"""

    def simplified_view_at_step(self, step: int):
        insertion_request, requests, failed_tree = self.graph.time_machine(step)
        all_requests = []
        all_requests += requests
        all_requests += list(chain(*failed_tree)) if failed_tree is not None else []
        all_requests += [insertion_request]
        all_nodes = collect_nodes(all_requests)

        node_str = "\n".join(
            [self.simple_node_details(node, insertion_request, requests, failed_tree) for node in all_nodes]
        )

        return f"""## Request Ledger 
{self.request_info_table(insertion_request, requests, failed_tree)}

## Node Library
{node_str}

"""


def node_name(identifier: str, node_id_mapping: Dict[str, Type[Node]]):
    return f"{node_id_mapping[identifier].pretty_name()} - ({identifier[:5]}...)"


if __name__ == "__main__":
    import dill

    with open("data/c3-runs/2024-09-10-16-44-38.pickle", "rb") as f:

        json_payload = dill.load(f)

    ssm = SystemStateManager(json_payload["stamps"], json_payload["runtime_graph"])

    print(ssm.view_at_step(5))
