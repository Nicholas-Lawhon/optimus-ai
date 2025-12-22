from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import system_prompt
from functions.call_function import available_functions, call_function
import argparse
import os


load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("Failed to load API key.")

client = genai.Client(api_key=api_key)


def main():
    cli_parser = argparse.ArgumentParser(description="Chatbot")
    cli_parser.add_argument("user_prompt", type=str, help="User prompt")
    cli_parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = cli_parser.parse_args()

    messages = [types.Content(role="user", parts=[types.Part(text=args.user_prompt)])]
    
    for _ in range(20):
        try:
            response = generate_content(client, messages, args.verbose, args.user_prompt)
            finished = is_model_finished(response)
            
            if finished:
                print("Final response:")
                print(response.text)
                break
                    
        except Exception as e:
            print(f"Error: {e}")
            
    else:
        print("Model reached the max iteration limit")
            
            
def is_model_finished(response):
    # Checks if the model is finished by checking if any part has a function_call
    
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call is not None:
                return False
            
    return bool(response.text)
            

def generate_content(client, messages, verbose, user_prompt):
    response = client.models.generate_content(
    model='gemini-2.5-flash', 
    contents=messages,
    config=types.GenerateContentConfig(tools=[available_functions], system_instruction=system_prompt),
    )
    
    prompt_token_count = response.usage_metadata.prompt_token_count # type: ignore
    response_token_count = response.usage_metadata.candidates_token_count # type: ignore
    
    if not prompt_token_count or not response_token_count:
        raise RuntimeError("No prompt or response token count. This is likely due to a failed API call.")
    
    if verbose:
        print(f"User prompt: {user_prompt}\n"
            f"Prompt tokens: {prompt_token_count}\n"
            f"Response tokens: {response_token_count}\n")
    
    function_call_parts = []
    
    if response.function_calls:
        for function_call in response.function_calls:
            function_call_result = call_function(function_call, verbose=verbose)
            part = function_call_result.parts[0]
            
            if not hasattr(part, "function_response") or not part.function_response.response:
                raise Exception("Function call did not return a valid response")
            
            if verbose:
                print(f"-> {part.function_response.response}")

            function_call_parts.append(part)
    else:
        print(f"Response:\n", response.text)
        
    for ai_response in response.candidates:
        messages.append(ai_response.content)
        
    if function_call_parts:
        tool_response_message = types.Content(
            role="user",
            parts=function_call_parts,
        )
        messages.append(tool_response_message)
        
    return response


if __name__ == "__main__":
    main()
