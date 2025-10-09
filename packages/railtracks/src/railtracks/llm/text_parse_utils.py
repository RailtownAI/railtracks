import json
from typing import Any, List, Dict, Optional
import re
import litellm

def _generate_cohere_system_prompt(schema: Type[BaseModel]) -> str:
    """Generate an optimized system prompt for Cohere based on the schema."""
    schema_info = schema.schema()
    
    # Build field descriptions
    field_descriptions = []
    for field_name, field_info in schema_info["properties"].items():
        field_type = field_info.get("type", "unknown")
        description = field_info.get("description", "")
        field_descriptions.append(f"- {field_name} ({field_type}): {description}")
    
    fields_text = "\n".join(field_descriptions)
    
    prompt = f"""
    You are a structured data API. You MUST respond with ONLY valid JSON that matches this exact schema:
    
    {schema_info}
    
    Field details:
    {fields_text}
    
    CRITICAL INSTRUCTIONS:
    1. Return ONLY the JSON object, no additional text, explanations, or markdown
    2. Do not include ```json ``` code blocks
    3. The response must be directly parseable by json.loads()
    4. All fields must be present and of the correct type
    5. If a field is optional, you may omit it only if no relevant information is available
    6. Do not use **bold**, *italic*, or any other markdown formatting
    7. Do not use numbered lists (1. 2. 3.) or bullet points
    8. Do not include headers, titles, or section names


        FORMATTING PROHIBITIONS:
    - NO **asterisks** for bold
    - NO *asterisks* for italic  
    - NO numbered lists like "1. value"
    - NO bullet points like "- value" or "• value"
    - NO markdown code blocks
    - NO extra text before or after JSON
    
    Example of valid response:
    {json.dumps({k: self._get_example_value(v) for k, v in schema_info["properties"].items()}, indent=2)}

    Example of INVALID response (DO NOT DO THIS):
    Here are the results:
    ```json
    {{
    "numbers": [**282**, **247**, **290**]
    }}
    ```
    
    Example of INVALID response (DO NOT DO THIS):
    1. **282**
    2. **247** 
    3. **290**
    """
    
    return prompt

def _get_example_value(field_info: Dict) -> Any:
    """Generate example values for the schema."""
    field_type = field_info.get("type")
    
    if field_type == "string":
        return "example_string"
    elif field_type == "integer":
        return 42i
    elif field_type == "number":
        return 3.14
    elif field_type == "boolean":
        return True
    elif field_type == "array":
        return ["item1", "item2"]
    elif field_type == "object":
        return {"key": "value"}
    else:
        return None
    
def extract_structured_response(text: str, schema: Type[BaseModel]) -> Dict[str, Any]:
    """
    Extract structured data from Cohere's text response for any schema.
    
    Args:
        text: Raw text response from Cohere
        schema: Pydantic model class defining the expected structure
        
    Returns:
        Dictionary with extracted data matching the schema
    """
    print('===========EXTRACTING STRUCTURED RESPONSE==========================')
    print(f"Input text: {text}")
    print(f"Target schema: {schema.__name__}")
    
    # Try to extract JSON first
    json_data = self._extract_json(text)
    if json_data and self._validate_against_schema(json_data, schema):
        print("Successfully extracted JSON matching schema")
        return json_data
    
    # Text-based extraction for the schema
    extracted_data = self._extract_from_text_by_schema(text, schema)
    if extracted_data and self._validate_against_schema(extracted_data, schema):
        print("Successfully extracted data from text")
        return extracted_data
    
    # Fallback - use LLM to fix the response (advanced)
    fixed_data = self._fix_response_with_llm(text, schema)
    if fixed_data:
        print("Successfully fixed response with LLM")
        return fixed_data
        
    raise ValueError(f"Could not extract structured data from response: {text}")

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from text using multiple strategies."""
    # Direct JSON parsing
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # Extract JSON object/array using regex
    json_patterns = [
        r'\{[^{}]*\{[^{}]*\}[^{}]*\}',  # Nested objects
        r'\{[^{}]*\[[^]]*\][^{}]*\}',   # Objects with arrays
        r'\{.*\}',                      # Simple objects
        r'\[.*\]',                      # Arrays
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    return None

def _extract_from_text_by_schema(text: str, schema: Type[BaseModel]) -> Dict[str, Any]:
    """
    Extract data from text based on schema field types and names.
    """
    schema_info = schema.schema()
    properties = schema_info["properties"]
    extracted_data = {}
    
    for field_name, field_info in properties.items():
        field_type = field_info.get("type")
        field_description = field_info.get("description", "")
        
        print(f"Extracting field: {field_name} (type: {field_type})")
        
        # Extract based on field type
        if field_type == "array":
            extracted_data[field_name] = self._extract_array_field(text, field_name, field_info)
        elif field_type == "string":
            extracted_data[field_name] = self._extract_string_field(text, field_name, field_info)
        elif field_type in ["integer", "number"]:
            extracted_data[field_name] = self._extract_numeric_field(text, field_name, field_info)
        elif field_type == "boolean":
            extracted_data[field_name] = self._extract_boolean_field(text, field_name, field_info)
        elif field_type == "object":
            extracted_data[field_name] = self._extract_object_field(text, field_name, field_info)
        else:
            # Try generic extraction
            extracted_data[field_name] = self._extract_generic_field(text, field_name, field_info)
    
    return extracted_data

def _extract_array_field(text: str, field_name: str, field_info: Dict) -> List:
    """Extract array fields based on context."""
    items_info = field_info.get("items", {})
    
    # Look for numbered lists
    numbered_items = re.findall(r'(?:\d+\.\s*)([^\n\.]+)', text)
    if numbered_items:
        return [item.strip() for item in numbered_items]
    
    # Look for bullet points
    bullet_items = re.findall(r'(?:[-•*]\s*)([^\n]+)', text)
    if bullet_items:
        return [item.strip() for item in bullet_items]
    
    # Look for items in brackets
    bracket_items = re.findall(r'\[([^]]+)\]', text)
    if bracket_items:
        items = [item.strip() for item in bracket_items[0].split(',')]
        return items
    
    # Extract based on item type
    if items_info.get("type") == "integer":
        numbers = re.findall(r'\b\d+\b', text)
        return [int(n) for n in numbers[:10]]  # Limit to first 10
    elif items_info.get("type") == "number":
        # Match floats and integers (e.g., 3, 3.14, .5, 0.001)
        floats = re.findall(r'\b\d+\.\d+|\b\d+\b', text)
        return [float(n) for n in floats[:10]]
    
    return []

def _extract_string_field(text: str, field_name: str, field_info: Dict) -> str:
    """Extract string fields based on context."""
    # Look for field name followed by value
    pattern = rf"{field_name}[\s:]+([^\n\.]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # For names, look for capitalized words
    if "name" in field_name.lower():
        name_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        names = re.findall(name_pattern, text)
        if names:
            return names[0]
    
    return ""

def _extract_numeric_field(text: str, field_name: str, field_info: Dict) -> Optional[float]:
    """Extract numeric fields."""
    # Look for field name followed by number
    pattern = rf"{field_name}[\s:]+(\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    # Extract all numbers and take the most relevant one
    numbers = re.findall(r'\b\d+\b', text)
    if numbers:
        return float(numbers[0])
    
    return None

def _extract_boolean_field(text: str, field_name: str, field_info: Dict) -> bool:
    """Extract boolean fields."""
    # Look for yes/no, true/false patterns
    true_patterns = [r'\byes\b', r'\btrue\b', r'\bcorrect\b', r'\baccurate\b', r'\bright\b']
    false_patterns = [r'\bno\b', r'\bfalse\b', r'\bincorrect\b', r'\bwrong\b']
    
    for pattern in true_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    for pattern in false_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    return False

def _extract_object_field(text: str, field_name: str, field_info: Dict) -> Dict:
    """Extract nested object fields."""
    # Look for JSON-like structures for the object
    json_data = self._extract_json(text)
    if json_data and field_name in json_data:
        return json_data[field_name]
    
    return {}

def _extract_generic_field(text: str, field_name: str, field_info: Dict) -> Any:
    """Generic field extraction as fallback."""
    # Try to find the field name followed by some value
    pattern = rf"{field_name}[\s:]+([^\n\.]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None

def _validate_against_schema(data: Dict[str, Any], schema: Type[BaseModel]) -> bool:
    """Validate extracted data against schema."""
    try:
        # Try to create an instance of the schema
        schema(**data)
        return True
    except Exception as e:
        print(f"Validation failed: {e}")
        return False

def _fix_response_with_llm(text: str, schema: Type[BaseModel]) -> Optional[Dict[str, Any]]:
    """
    Use the LLM itself to fix malformed responses (advanced fallback).
    """
    try:
        schema_json = schema.schema_json(indent=2)
        
        fix_prompt = f"""
        The following text was supposed to be a response matching this JSON schema:
        {schema_json}
        
        But the response was malformed:
        {text}
        
        Please extract the relevant information and return ONLY valid JSON that matches the schema exactly.
        Do not include any explanations or additional text.
        """
        
        # Use a quick LLM call to fix the response
        fixed_response = litellm.completion(
            model=self._model_name,
            messages=[{"role": "user", "content": fix_prompt}],
            max_tokens=500,
            temperature=0.1
        )
        
        fixed_content = fixed_response.choices[0].message.content
        return json.loads(fixed_content)
        
    except Exception as e:
        print(f"LLM fixing failed: {e}")
        return None 
    