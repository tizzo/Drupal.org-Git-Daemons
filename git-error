#!/usr/bin/env python
import sys

def format_git_error(string):
    # Four packet size bytes, string
    string = "ERR " + string
    print("{0:04x}{1}".format(len(string)+4,string))

if __name__ == "__main__":
    message = " ".join(sys.argv[1:])
    format_git_error(message)
