import os



def get_files_info(working_directory, directory="."):
    working_dir_abs = os.path.abspath(working_directory)
    target_dir = os.path.normpath(os.path.join(working_dir_abs, directory))
    valid_target_dir = os.path.commonpath([working_dir_abs, target_dir]) == working_dir_abs 

    if not valid_target_dir:
        raise Exception(f'Error: Cannot list "{directory}" as it is outside the permitted working directory')
    elif not os.path.isdir(directory):
        raise Exception(f'Error: "{directory}" is not a directory')