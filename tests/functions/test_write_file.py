from functions.write_file import write_file


def test_write_file_root():
    result = write_file("calculator", "lorem.txt", "wait, this isn't lorem ipsum")
    print(result)
    assert result is not None


def test_write_file_subdirectory():
    result = write_file("calculator", "pkg/morelorem.txt", "lorem ipsum dolor sit amet")
    print(result)
    assert result is not None


def test_write_file_absolute_path_blocked():
    result = write_file("calculator", "/tmp/temp.txt", "this should not be allowed")
    print(result)
    # Should fail or return error for absolute paths outside project
