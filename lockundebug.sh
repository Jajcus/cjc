#!/bin/sh

find . -name "*.py" | xargs perl -pi -e \
  's/^(\s+).*lockdebug.*; ([\w.]+\.(acquire|release)\(\));[^\n]*$/\1\2/'
