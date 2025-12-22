from functions.get_file_content import get_file_content


def test_get_file_content_valid_file():
    result = get_file_content("calculator", "main.py")
    print(f"{result}\n")
    assert result is not None


def test_get_file_content_nested_file():
    result = get_file_content("calculator", "pkg/calculator.py")
    print(f"{result}\n")
    assert result is not None


def test_get_file_content_absolute_path_blocked():
    result = get_file_content("calculator", "/bin/cat")
    print(f"{result}\n")
    # Should fail or return error for absolute paths outside project


def test_get_file_content_nonexistent_file():
    result = get_file_content("calculator", "pkg/does_not_exist.py")
    print(f"{result}\n")
    # Should handle missing file gracefully
