from dotenv import load_dotenv
from google import genai
from google.genai import types
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

    response = client.models.generate_content(
    model='gemini-2.5-flash', contents=messages)

    prompt_token_count = response.usage_metadata.prompt_token_count
    response_token_count = response.usage_metadata.candidates_token_count

    if not prompt_token_count or not response_token_count:
        raise RuntimeError("No prompt or response token count. This is likely due to a failed API call.")
    
    if args.verbose:
        print(f"User prompt: {args.user_prompt}\n"
            f"Prompt tokens: {prompt_token_count}\n"
            f"Response tokens: {response_token_count}\n")
    
    print(f"Response:\n", response.text)


if __name__ == "__main__":
    main()
