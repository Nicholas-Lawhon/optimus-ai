import os



def get_files_info(working_directory, directory="."):
    working_dir_abs = os.path.abspath(working_directory)
    target_dir = os.path.normpath(os.path.join(working_dir_abs, directory))
    is_valid_target_dir = os.path.commonpath([working_dir_abs, target_dir]) == working_dir_abs 

    try:
        if not is_valid_target_dir:
            return f'Error: Cannot list "{directory}" as it is outside the permitted working directory'
        elif not os.path.isdir(target_dir):
            return f'Error: "{directory}" is not a directory'
        
        dir_contents = os.listdir(target_dir)
        contents_list = []
        for i in dir_contents:
            full_path = os.path.join(target_dir, i)
            name = i
            file_size = os.path.getsize(full_path)
            is_dir = os.path.isdir(full_path)
            contents_list.append(str(f"- {name}: file_size={file_size} bytes, is_dir={is_dir}"))
    except Exception as e:
        return f"Error: {e}"

    return "\n".join(contents_list)

