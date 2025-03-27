#!/bin/bash

# Check if input file is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <input_csv_file>"
    exit 1
fi

input_file="$1"
output_prefix="output_"

# Check if input file exists
if [ ! -f "$input_file" ]; then
    echo "Error: File '$input_file' not found!"
    exit 1
fi

# Calculate number of lines (excluding header)
total_lines=$(tail -n +2 "$input_file" | wc -l)
lines_per_file=$(( (total_lines + 9) / 10 ))

# Get header
header=$(head -n 1 "$input_file")

# Split the file
echo "Splitting '$input_file' into 10 parts..."
awk -v lpf="$lines_per_file" -v header="$header" -v out_prefix="$output_prefix" '
    BEGIN { file_num=1 }
    NR == 1 { next }  # Skip header (we already have it)
    (NR-2) % lpf == 0 {
        close(outfile)
        outfile = out_prefix file_num ".csv"
        print header > outfile
        file_num++
    }
    { print > outfile }
' "$input_file"

echo "Done! Created files:"
ls "${output_prefix}"*.csv