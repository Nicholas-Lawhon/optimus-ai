from google.genai import types
import os
import subprocess


schema_run_python_file = types.FunctionDeclaration(
    name="run_python_file",
    description="Runs a specified python file, relative to the working directory",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The path of the file to run, relative to the working directory",
            ),
            "args": types.Schema(
                type=types.Type.ARRAY,
                description="Optional list of command-line arguments to pass to the Python file",
                items=types.Schema(
                    type=types.Type.STRING,
                    description="Single command-line argument",
                ),
            ),
        },
        required = ["file_path"],
    ),
)


def run_python_file(working_directory, file_path, args=None):
    working_dir_abs = os.path.abspath(working_directory)
    target_path = os.path.normpath(os.path.join(working_dir_abs, file_path))
    is_valid_target_dir = os.path.commonpath([working_dir_abs, target_path]) == working_dir_abs 
    
    try:
        if not is_valid_target_dir:
            return f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'
        elif not os.path.isfile(target_path):
            return f'Error: "{file_path}" does not exist or is not a regular file'
        elif not file_path.endswith(".py"):
            return f'Error: "{file_path}" is not a Python file'
        
        command = ["python", target_path]
        
        if args:
            command.extend(args)
            
        run_process = subprocess.run(command, cwd=working_dir_abs, capture_output=True, text=True, timeout=30)
        run_process_output = ""
        
        if run_process.returncode != 0:
            run_process_output += f"Process exited with code {run_process.returncode}\n" 
        elif not run_process.stdout and not run_process.stderr:
            run_process_output += "No output produced\n"
            
        if run_process.stdout:
            run_process_output += f'STDOUT: {run_process.stdout}'
        if run_process.stderr:
            run_process_output += f'STDERR: {run_process.stderr}'
        
        return run_process_output
            
    except Exception as e:
        return f"Error: executing Python file: {e}"