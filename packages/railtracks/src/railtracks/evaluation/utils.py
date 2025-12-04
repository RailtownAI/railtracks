import json
# from .data import DataPoint
from railtracks.evaluation.data.point import DataPoint

def extract_run_data(file_path: str, tool_info=False) -> list[DataPoint]:
    """Load session data from a railtracks session JSON file.

    Extracts run information and returns a list of tuples containing:
    (run_id, agent_name, input, output)

    Args:
        file_path: Path to the session JSON file.

    Returns:
        List of tuples with (run_id, agent_name, input, output).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        session = json.load(f)

    data_points = []
    runs = session.get("runs", [])

    for run in runs:
        nodes = run.get("nodes", [])
        for node in nodes:
            
            
            # JSON parsing shenanigans
            details = node.get("details", {})
            internals = details.get("internals", {})
            llm_details = internals.get("llm_details", [])
            
            for detail in llm_details:
                agent_input = detail.get("input", [])
                agent_output = detail.get("output", {})


                if isinstance(agent_input, list):
                    agent_input = json.dumps(agent_input, indent=2)
                if isinstance(agent_output, dict):
                    agent_output = json.dumps(agent_output, indent=2)
                dp = DataPoint(agent_input=agent_input, agent_output=agent_output)

                data_points.append(
                        dp
                )

    return data_points


if __name__ == "__main__":
    import railtracks.evaluation as evals
    from rich import print


    files = [
        ".railtracks/Terminal_3814d67b-e369-4b33-bfba-74d5ec6a345f.json", # Terminal
        ".railtracks/Structured_a08bb0e6-c31b-4aed-a8a1-103d5c548d63.json", # SO
        ".railtracks/ToolCall_c559a2c8-c7af-4d26-84f2-417c809e71c4.json", # Tool
        ".railtracks/STToolCall_ef70b4a8-39f9-4fdb-949d-6f23ec173de9.json", # SOT
    ]
    for file in files:
        data = extract_run_data(file)
        for dp in data:
            print(dp)
        print("\n\n")
