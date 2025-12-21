from functions.get_file_content import get_file_content


def main():
    print(f"{get_file_content("calculator", "main.py")}\n")
    print(f"{get_file_content("calculator", "pkg/calculator.py")}\n")
    print(f"{get_file_content("calculator", "/bin/cat")}\n")
    print(f"{get_file_content("calculator", "pkg/does_not_exist.py")}\n")


if __name__ == "__main__":
    main()