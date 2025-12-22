from functions.get_files_info import get_files_info


def test_get_files_info_root_dir():
    result = get_files_info("calculator", ".")
    print(f"{result}\n")
    assert result is not None


def test_get_files_info_subdirectory():
    result = get_files_info("calculator", "pkg")
    print(f"{result}\n")
    assert result is not None


def test_get_files_info_absolute_path_blocked():
    result = get_files_info("calculator", "/bin")
    print(f"{result}\n")
    # Should fail or return error for absolute paths outside project


def test_get_files_info_parent_traversal_blocked():
    result = get_files_info("calculator", "../")
    print(f"{result}\n")
    # Should fail or return error for parent directory traversal
