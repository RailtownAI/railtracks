import json
from pathlib import Path

def extract_run_data(file_path: str) -> list[tuple[str, str, str, str]]:
    """Load session data from a railtracks session JSON file.
    
    Extracts run information and returns a list of tuples containing:
    (run_id, agent_name, input, output)
    
    Args:
        file_path: Path to the session JSON file.
        
    Returns:
        List of tuples with (run_id, agent_name, input, output).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        session = json.load(f)
    
    results = []
    
    for run in session.get('runs', []):
        run_id = run.get('run_id', '')
        agent_name = run.get('name', '')
        
        for edge in run.get('edges', []):
            details = edge.get('details', {})
            
            input_args = details.get('input_args', [])
            agent_input = input_args[0] if input_args else ''
            
            output = details.get('output', '')
            if isinstance(output, str) and output.startswith('ERROR:'):
                agent_output = output
            else:
                agent_output = str(output) if output else ''
            
            if agent_input or agent_output:
                results.append((run_id, agent_name, agent_input, agent_output))
    
    return results

if __name__=='__main__':
    data = extract_run_data("/Users/amirr/dev/railtracks/.railtracks/5c2c0bea-f1d6-4282-ad4d-ec74a351f682.json")
    for run_id, agent_name, agent_input, agent_output in data:
        print(f"{agent_name} ({run_id}):\nInput:\n{agent_input}\nOutput:\n{agent_output}")