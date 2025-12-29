import time
import sys

def main():
    print("Fake test script starting...")
    print("Arguments received:", sys.argv)
    sys.stdout.flush()

    for i in range(1, 11):
        print(f"Running step {i}/10...")
        sys.stdout.flush()
        time.sleep(1)

    print("Fake test script completed.")
    sys.stdout.flush()

if __name__ == "__main__":
    main()