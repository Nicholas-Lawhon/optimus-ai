from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import SYSTEM_PROMPT
from functions.call_function import available_functions, call_function
from memory.manager import MemoryManager
import argparse
import os


load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("Failed to load API key.")

client = genai.Client(api_key=api_key)


def main() -> None:
    """
    Main entry point for the Optimus AI agent.
    
    Handles argument parsing, memory initialization, and the primary
    agentic loop (up to 20 iterations).
    """
    cli_parser = argparse.ArgumentParser(description="Chatbot")
    cli_parser.add_argument("user_prompt", type=str, help="User prompt")
    cli_parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = cli_parser.parse_args()

    messages = [types.Content(role="user", parts=[types.Part(text=args.user_prompt)])]
    mem_manager = MemoryManager.initialize()
    
    for _ in range(20):
        try:
            # Build Context & Config
            context = mem_manager.build_context_string(max_chars=8000)
            full_system_instructions = f"{SYSTEM_PROMPT}\n\n{context}"
            config = types.GenerateContentConfig(tools=[available_functions], system_instruction=full_system_instructions)
            
            # Generate Response
            response = generate_content(client, messages, config, args.verbose, args.user_prompt)
            
            finished = is_model_finished(response)
            
            if finished:
                # The prompt that triggered this might be a human or a tool result
                
                ai_text = response.text or "No response text."
                
                # Check previous message to see if it was a tool output
                last_event = messages[-2]
                if last_event.parts and last_event.parts[0].function_response:
                    user_text = f"Tool Output: {last_event.parts[0].function_response}"    
                elif last_event.parts:
                    user_text = last_event.parts[0].text or ""
                else:
                    user_text = "Unknown User Input"
                    
                # Store as CHAT
                mem_manager.store_conversation(
                    user_message=user_text,
                    assistant_response=ai_text,
                    tags=["chat"]
                )
                
                print("Final Response")
                print(ai_text)
                break
            
            else:
                # The AI wants to run a tool call
                
                # Extract Function Name Safely
                last_msg = messages[-2]
                print(f"messages[-1]: {last_msg}")  # For Debugging
                fn_name = "Unknown Tool"
                if last_msg.parts and last_msg.parts[0].function_call:
                    fn_name = last_msg.parts[0].function_call.name
                
                tool_log = f"Called Function: {fn_name}"
                
                # The user message that prompted the tool call
                last_event = messages[-3]
                if last_event.parts and last_event.parts[0].function_response:
                    user_text = f"Tool Output: {last_event.parts[0].function_response.response}"
                elif last_event.parts:
                    user_text = last_event.parts[0].text or ""
                else:
                    user_text = "Unknown User Input"
            
                # Store as TOOL_USE
                mem_manager.store_conversation(
                    user_message=user_text,
                    assistant_response=tool_log,
                    tags=["tool_use"]
                )
                    
        except Exception as e:
            print(f"Error: {e}")
            
    else:
        print("Model reached the max iteration limit")
            
            
def is_model_finished(response: types.GenerateContentResponse) -> bool:
    """
    Check if the model has completed its task or needs to run a tool.

    Args:
        response: The API response object from Gemini.

    Returns:
        True if the model produced a text response (finished).
        False if the model requested a function call (not finished).
    """
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call is not None:
                return False
            
    return bool(response.text)
            

def generate_content(
    client: genai.Client, 
    messages: list[types.Content], 
    config: types.GenerateContentConfig, 
    verbose: bool, 
    user_prompt: str
) -> types.GenerateContentResponse:
    """
    Send the conversation history to the model and handle the response.

    This function handles the API call, validation of the response, logging
    token usage (if verbose), and executing any requested tool calls.

    Args:
        client: The initialized Gemini API client.
        messages: The history of messages in the conversation.
        config: Configuration containing tools and system instructions.
        verbose: Whether to print debug information.
        user_prompt: The original user prompt (for logging purposes).

    Returns:
        The updated response object after processing tool calls.
    
    Raises:
        RuntimeError: If API response is missing critical metadata.
        Exception: If tool execution fails.
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=messages,
        config=config,
    )
    
    if not response.usage_metadata:
        raise RuntimeError("No usage metadata. This is likely due to a failed API call.")

    prompt_token_count = response.usage_metadata.prompt_token_count
    response_token_count = response.usage_metadata.candidates_token_count

    if not prompt_token_count or not response_token_count:
        raise RuntimeError("No prompt or response token count. This is likely due to a failed API call.")
    
    if verbose:
        print(f"User prompt: {user_prompt}\n"
            f"Prompt tokens: {prompt_token_count}\n"
            f"Response tokens: {response_token_count}\n")
    
    function_call_parts = []
    
    # Handle Tool Execution
    if response.function_calls:
        for function_call in response.function_calls:
            function_call_result = call_function(function_call, verbose=verbose)

            if not function_call_result.parts:
                raise Exception("Function call did not return any parts")

            part = function_call_result.parts[0]

            if not hasattr(part, "function_response") or part.function_response is None or part.function_response.response is None:
                raise Exception("Function call did not return a valid response")
            
            if verbose:
                print(f"-> {part.function_response.response}")

            function_call_parts.append(part)
    else:
        print(f"Response:\n", response.text)
    
    # Append Assistant Responses to History
    for ai_response in response.candidates:
        messages.append(ai_response.content)
    
    # Append Tool Results to History (if any)
    if function_call_parts:
        tool_response_message = types.Content(
            role="user",
            parts=function_call_parts,
        )
        messages.append(tool_response_message)
        
    return response


if __name__ == "__main__":
    main()
