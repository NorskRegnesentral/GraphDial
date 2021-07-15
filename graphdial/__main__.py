from . import system
import sys

if __name__ == "__main__":
    args = sys.argv
    if len(args) < 2:
        raise RuntimeError("Must specify domain config file")
    system.DialogueSystem(args[1])
