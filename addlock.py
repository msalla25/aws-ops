#!/bin/bash

# Check if input file is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <input_file>"
    exit 1
fi

input_file="$1"
lines_per_file=10000
output_prefix="output_payload"

# Split the file
split -l $lines_per_file --numeric-suffixes=1 --suffix-length=1 --additional-suffix=".txt" "$input_file" "$output_prefix_"

# Rename files to have consistent numbering (e.g., 01, 02, etc. if more than 9 files)
count=1
for file in ${output_prefix}_*.txt; do
    new_name="${output_prefix}_${count}.txt"
    if [ "$file" != "$new_name" ]; then
        mv "$file" "$new_name"
    fi
    ((count++))
done

echo "Split $input_file into $((count-1)) files with $lines_per_file lines each."