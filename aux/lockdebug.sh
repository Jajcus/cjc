#!/bin/sh

find . -name "*.py" | xargs perl -pi -e \
  's/^(\s+)([\w.]+\.(acquire|release)\(\))[ \t]*$/\1logging.getLogger("lockdebug").debug("\2..."); \2; logging.getLogger("lockdebug").debug("...\2")/'
