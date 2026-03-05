#!/bin/bash

# Check if a directory path argument was provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <directory_path>"
    exit 1
fi

# Verify that the provided path is a directory
directory_path="$1"
if [ ! -d "$directory_path" ]; then
    echo "Error: '$directory_path' is not a directory."
    exit 1
fi

# Change to the specified directory
cd "$directory_path" || exit 1

# Loop through all directories in the specified directory
for dir in */; do
    if [ -d "$dir" ]; then
        echo "Running 'npm install' in $dir"
        cd "$dir" || exit 1
        npm install
        cd ..
        echo "'npm install' completed in $dir"
    fi
done
