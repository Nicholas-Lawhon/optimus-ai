from functions.get_files_info import get_files_info


print(f"{get_files_info("calculator", ".")}\n")
print(f"{get_files_info("calculator", "pkg")}\n")
print(f"{get_files_info("calculator", "/bin")}\n")
print(f"{get_files_info("calculator", "../")}\n")