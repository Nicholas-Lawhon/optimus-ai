from genericpath import isdir
from google.genai import types
import os


schema_write_file = types.FunctionDeclaration(
    name="write_file",
    description="Writes to a specified file, relative to the working directory",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The path of the file to write to, relative to the working directory",
            ),
            "content": types.Schema(
                type=types.Type.STRING,
                description="The content to write to the specified file",
            ),
        },
        required = ["file_path", "content"],
    ),
)


def write_file(working_directory, file_path, content):
    working_dir_abs = os.path.abspath(working_directory)
    target_path = os.path.normpath(os.path.join(working_dir_abs, file_path))
    is_valid_target_dir = os.path.commonpath([working_dir_abs, target_path]) == working_dir_abs 
    
    try:
        if not is_valid_target_dir:
            return f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'
        elif os.path.isdir(target_path):
            return f'Error: Cannot write to "{file_path}" as it is a directory'
        
        os.makedirs(os.path.dirname(target_path), exist_ok=True)  
        
        with open(target_path, "w") as file:
            file.write(content)
            
            return f'Successfully wrote to "{file_path}" ({len(content)} characters written)'
        
    except Exception as e:
        return f"Error: {e}"