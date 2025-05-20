import pytest
import json
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to allow imports from demo
sys.path.append(str(Path(__file__).parent.parent.parent))
print("start")
print(sys.path)
print("end")
from demo.sample_agents.grammar_agent import call_function, tools, update_messages, ask_agent, messages, SYSTEM_PROMPT, USER_PROMPT

# Mock responses for Notion tools
@pytest.fixture
def mock_notion_responses():
    return {
        "find_page": [{"id": "page123", "title": "Page To Be Edited"}],
        "get_text_blocks": ["block1", "block2"],
        "get_block_text": "This is a test text with some grammer mistakes.",
        "edit_block": "Called"
    }

# Mock OpenAI response1
@pytest.fixture
def mock_openai_response1():
    return {
        "output": [
            {
                "type": "function_call",
                "name": "find_page",
                "arguments": json.dumps({"query": "Page To Be Edited"}),
                "call_id": "call_1"
            }]}

# Mock OpenAI response2
@pytest.fixture
def mock_openai_response2():
    return {
        "output": [
            {
                "type": "function_call",
                "name": "get_text_blocks",
                "arguments": json.dumps({"page_id": "page123"}),
                "call_id": "call_2"
            }]}

# Mock OpenAI response3
@pytest.fixture
def mock_openai_response3():
    return {
        "output": [
            {
                "type": "function_call",
                "name": "get_block_text",
                "arguments": json.dumps({"page_id": "page123", "block_id": "block1"}),
                "call_id": "call_3"
            }]}

# Mock OpenAI response4
@pytest.fixture
def mock_openai_response4():
    return {
        "output": [
            {
                "type": "function_call",
                "name": "edit_block",
                "arguments": json.dumps({
                    "page_id": "page123",
                    "block_id": "block1",
                    "new_text": "This is a test text with some grammar mistakes."
                }),
                "call_id": "call_4"
            }
        ]
    }

def test_call_function_find_page(mocker, mock_notion_responses):
    mock_find_page = mocker.patch('demo.sample_agents.grammar_agent.find_page')
    mock_find_page.return_value = mock_notion_responses["find_page"]
    
    result = call_function("find_page", {"query": "Page To Be Edited"})
    
    assert result == mock_notion_responses["find_page"]
    mock_find_page.assert_called_once_with(query="Page To Be Edited")

def test_call_function_get_text_blocks(mocker, mock_notion_responses):
    mock_get_text_blocks = mocker.patch('demo.sample_agents.grammar_agent.get_text_blocks')
    mock_get_text_blocks.return_value = mock_notion_responses["get_text_blocks"]
    
    result = call_function("get_text_blocks", {"page_id": "page123"})
    
    assert result == mock_notion_responses["get_text_blocks"]
    mock_get_text_blocks.assert_called_once_with(page_id="page123")

def test_call_function_get_block_text(mocker, mock_notion_responses):
    mock_get_block_text = mocker.patch('demo.sample_agents.grammar_agent.get_block_text')
    mock_get_block_text.return_value = mock_notion_responses["get_block_text"]
    
    result = call_function("get_block_text", {"page_id": "page123", "block_id": "block1"})
    
    assert result == mock_notion_responses["get_block_text"]
    mock_get_block_text.assert_called_once_with(page_id="page123", block_id="block1")

def test_call_function_edit_block(mocker, mock_notion_responses):
    mock_edit_block = mocker.patch('demo.sample_agents.grammar_agent.edit_block')
    mock_edit_block.return_value = mock_notion_responses["edit_block"]
    
    result = call_function("edit_block", {
        "page_id": "page123",
        "block_id": "block1",
        "new_text": "This is a test text with some grammar mistakes."
    })
    
    assert result == mock_notion_responses["edit_block"]
    mock_edit_block.assert_called_once_with(
        page_id="page123",
        block_id="block1",
        new_text="This is a test text with some grammar mistakes."
    )

def test_grammar_agent_response1(mocker, mock_notion_responses, mock_openai_response1, mock_openai_response2, mock_openai_response3, mock_openai_response4):
    # Mock the OpenAI client responses
    mock_ask_agent = mocker.patch('demo.sample_agents.grammar_agent')
    mock_ask_agent.responses.create.return_value = mocker.Mock(**mock_openai_response1)
    
    # Mock the Notion tool functions
    mock_find_page = mocker.patch('demo.sample_agents.grammar_agent.find_page')
    mock_get_text_blocks = mocker.patch('demo.sample_agents.grammar_agent.get_text_blocks')
    mock_get_block_text = mocker.patch('demo.sample_agents.grammar_agent.get_block_text')
    mock_edit_block = mocker.patch('demo.sample_agents.grammar_agent.edit_block')
    
    # Set up mock return values
    mock_find_page.return_value = mock_notion_responses["find_page"]
    mock_get_text_blocks.return_value = mock_notion_responses["get_text_blocks"]
    mock_get_block_text.return_value = mock_notion_responses["get_block_text"]
    mock_edit_block.return_value = mock_notion_responses["edit_block"]
    
    prompt = messages

    result1 = ask_agent(prompt, tools)
    prompt = update_messages(prompt, result1)

    # Verify the initial messages
    print(prompt)
    assert len(prompt) == 4
    assert prompt[2] == "find_page"
    assert prompt[3]["output"] == "Page To Be Edited"


    mock_ask_agent = mocker.patch('demo.sample_agents.grammar_agent')
    mock_ask_agent.responses.create.return_value = mocker.Mock(**mock_openai_response2)
    result2 = ask_agent(prompt, tools)    
    prompt = update_messages(prompt, result2)

    # Verify the initial messages
    print(prompt)
    assert len(prompt) == 6
    assert prompt[4]["role"] == "system"
    assert prompt[4]["content"] == SYSTEM_PROMPT
    assert prompt[5]["role"] == "user"
    assert prompt[5]["content"] == USER_PROMPT

    
    mock_ask_agent = mocker.patch('demo.sample_agents.grammar_agent')
    mock_ask_agent.responses.create.return_value = mocker.Mock(**mock_openai_response3)
    result3 = ask_agent(prompt, tools)
    prompt = update_messages(prompt, result3)

    # Verify the initial messages
    print(prompt)
    assert len(prompt) == 8
    assert prompt[6]["role"] == "system"
    assert prompt[6]["content"] == SYSTEM_PROMPT
    assert prompt[7]["role"] == "user"
    assert prompt[7]["content"] == USER_PROMPT

    mock_ask_agent = mocker.patch('demo.sample_agents.grammar_agent')
    mock_ask_agent.responses.create.return_value = mocker.Mock(**mock_openai_response4)
    result4 = ask_agent(prompt, tools)    
    prompt = update_messages(prompt, result3)

    # Verify the initial messages
    print(prompt)
    assert len(prompt) == 10
    assert prompt[8]["role"] == "system"
    assert prompt[8]["content"] == SYSTEM_PROMPT
    assert prompt[9]["role"] == "user"
    assert prompt[9]["content"] == USER_PROMPT


    

def test_tools_structure():
    # Verify the structure of the tools list
    assert len(tools) == 4
    assert all("type" in tool for tool in tools)
    assert all("name" in tool for tool in tools)
    assert all("parameters" in tool for tool in tools)
    
    # Verify specific tool properties
    find_page_tool = next(tool for tool in tools if tool["name"] == "find_page")
    assert find_page_tool["parameters"]["required"] == ["query"]
    assert "query" in find_page_tool["parameters"]["properties"]
