from google.genai import types
from config import MAX_CHARS
import os


schema_get_file_content = types.FunctionDeclaration(
    name="get_file_content",
    description="Gets (reads) the contents of a specified file, relative to the working directory",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The path of the file to retrieve contents from, relative to the working directory",
            ),
        },
        required = ["file_path"],
    ),
)


def get_file_content(working_directory, file_path):
    working_dir_abs = os.path.abspath(working_directory)
    target_path = os.path.normpath(os.path.join(working_dir_abs, file_path))
    is_valid_target_dir = os.path.commonpath([working_dir_abs, target_path]) == working_dir_abs 

    try:
        if not is_valid_target_dir:
            return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'
        elif not os.path.isfile(target_path):
            return f'Error: File not found or is not a regular file: "{file_path}"'

        with open(target_path, 'r') as file:
            content = file.read(MAX_CHARS)

            if file.read(1):
                content += f'[...File "{file_path}" truncated at {MAX_CHARS} characters]'
                
            return content

    except Exception as e:
        return f"Error: {e}"