from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import SYSTEM_PROMPT
from functions.call_function import available_functions, call_function
from memory.manager import MemoryManager
from typing import Optional
import argparse
import sys
import os


load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("Failed to load API key.")

client = genai.Client(api_key=api_key)


# === UI / Formatting ===
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def print_tool_log(message: str):
    print(f"{Colors.YELLOW}{Colors.DIM}  → {message}{Colors.ENDC}")

def print_ai(message: str):
    print(f"\n{Colors.BLUE}Optimus:{Colors.ENDC} {message}")

def print_user(message: str):
    print(f"\n{Colors.GREEN}You:{Colors.ENDC} {message}") 


# === Main Logic ===

def main() -> None:
    """
    Main entry point for the Optimus AI agent.
    
    Handles argument parsing, memory initialization, and the primary
    agentic loop (up to 20 iterations).
    """
    cli_parser = argparse.ArgumentParser(description="Chatbot")
    cli_parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = cli_parser.parse_args()

    mem_manager = MemoryManager.initialize()
    
    messages = []
    
    print(f"{Colors.BOLD}Optimus AI is ready.{Colors.ENDC} Type 'exit' to quit, or 'correction' to fix.")
    
    # === OUTER LOOP: The Conversation Session ===
    while True:
        try:
            # Get User Input
            user_input = input(f"\n{Colors.GREEN}You:{Colors.ENDC} ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
            
            # Correction Logic
            if user_input.lower() == 'correction':
                last_ai_content = None
                last_ai_index = -1
                
                for i, m in enumerate(reversed(messages)):
                    if m.role == "model":
                        last_ai_content = m.parts[0].text
                        last_ai_index = len(messages) - 1 - i
                        break
                
                if not last_ai_content:
                    print(f"{Colors.RED}>> No previous AI response to correct.{Colors.ENDC}")
                    continue

                print(f"{Colors.DIM}I said: {last_ai_content[:50]}...{Colors.ENDC}")
                correction = input(f"{Colors.YELLOW}Correction: {Colors.ENDC}").strip()
                
                mem_manager.store_learned_correction(
                    original_response=last_ai_content,
                    correction=correction
                )
                
                # Soft delete the bad memory
                # This ensures future sessions won't remember it
                mem_manager.soft_delete_last_conversation()
                
                # Hard delete the bad memory from the active session
                # This ensures the next prompt won't see it
                if last_ai_index != -1:
                    messages.pop(last_ai_index)
                    
                    # Try to remove the user message that triggered the correction
                    if last_ai_index > 0 and messages[last_ai_index - 1].role == "user":
                        messages.pop(last_ai_index - 1)
                
                print(f"{Colors.DIM}>> Correction stored.{Colors.ENDC}")
                continue 

            #print() # Visual Separator

            messages.append(types.Content(role="user", parts=[types.Part(text=user_input)]))
            
            # === INNER LOOP ===
            agent_turn_finished = False
            for _ in range(20):
                # Build Context
                context = mem_manager.build_context_string(max_chars=30000)
                full_system_instructions = f"{SYSTEM_PROMPT}\n\n{context}"
                config = types.GenerateContentConfig(
                    tools=[available_functions], 
                    system_instruction=full_system_instructions
                )
                
                # Generate Response
                response = generate_content(
                    client, 
                    messages, 
                    config, 
                    args.verbose, 
                    user_prompt=user_input, 
                    mem_manager=mem_manager
                )
                
                finished = is_model_finished(response)
                
                if finished:
                    # Capture the final answer
                    ai_text = response.text or "No response text."
                    print(f"\n{Colors.BLUE}Optimus:{Colors.ENDC} {ai_text}")
                    
                    # --- MEMORY STORAGE (Chat) ---
                    last_user_text = "Unknown"
                    for m in reversed(messages[:-1]):
                        if m.role == "user":
                            # Check if it was a tool output or text
                            if m.parts and m.parts[0].function_response:
                                last_user_text = f"Tool Output: {m.parts[0].function_response}"
                            elif m.parts:
                                last_user_text = m.parts[0].text
                            break
                        
                    # Store as CHAT
                    mem_manager.store_conversation(
                        user_message=last_user_text,
                        assistant_response=ai_text,
                        tags=["chat"]
                    )
                    
                    agent_turn_finished = True
                    break
                
            # End of Inner Loop    
            if not agent_turn_finished:
                print(f"{Colors.RED}Agent reached max iteration limit.{Colors.ENDC}")
                    
        except KeyboardInterrupt:
            print("\nExiting...")
            break                
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.ENDC}")
            
            
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
    user_prompt: str,
    mem_manager: Optional[MemoryManager] = None
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
    
    # Verbose logging for tokens
    if verbose and response.usage_metadata:
        print(f"{Colors.DIM}[Tokens: Prompt={response.usage_metadata.prompt_token_count}, Resp={response.usage_metadata.candidates_token_count}]{Colors.ENDC}")
    
    function_call_parts = []
    
    # Handle Tool Execution
    if response.function_calls:
        for function_call in response.function_calls:

            cmd_name = function_call.name or ""
            cmd_args = function_call.args
            
            # --- CUSTOM UI LOGGING ---
            if verbose:
                print_tool_log(f"Running: {cmd_name}({cmd_args})")
            
            # Call function with verbose=False to suppress its internal print
            function_call_result = call_function(function_call, verbose=False)

            if not function_call_result.parts:
                raise Exception("Function call did not return any parts")

            part = function_call_result.parts[0]
            
            # Memory pattern logic
            if mem_manager and hasattr(part, "function_response"):
                response_dict = part.function_response.response
                is_success = "error" not in response_dict
                
                pattern_str = f"{cmd_name}({cmd_args})"
                mem_manager.store_tool_pattern(
                    tool_name=cmd_name,
                    pattern=pattern_str,
                    success=is_success,
                    importance=0.5 if is_success else 0.1
                )
                if verbose:
                    print_tool_log(f"Learned pattern: {pattern_str}")

            function_call_parts.append(part)
    
    # Append Assistant Responses to History
    if response.candidates:
        for ai_response in response.candidates:
            if ai_response.content:
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
