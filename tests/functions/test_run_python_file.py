from functions.run_python_file import run_python_file


def test_run_python_file_no_args():
    result = run_python_file("calculator", "main.py")
    print(result)
    assert result is not None


def test_run_python_file_with_args():
    result = run_python_file("calculator", "main.py", ["3 + 5"])
    print(result)
    assert result is not None


def test_run_python_file_tests():
    result = run_python_file("calculator", "tests.py")
    print(result)
    assert result is not None


def test_run_python_file_parent_traversal_blocked():
    result = run_python_file("calculator", "../main.py")
    print(result)
    # Should fail or return error for parent directory traversal


def test_run_python_file_nonexistent():
    result = run_python_file("calculator", "nonexistent.py")
    print(result)
    # Should handle missing file gracefully


def test_run_python_file_non_python():
    result = run_python_file("calculator", "lorem.txt")
    print(result)
    # Should fail or return error for non-Python files
