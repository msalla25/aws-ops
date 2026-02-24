#!/bin/bash

# Ensure an input string is provided
if [ -z "$1" ]; then
    echo "Usage: $0 \"<your natural language query>\""
    echo "Example: $0 \"For abc cluster give me the log for top 10 failure rate services\""
    exit 1
fi

# Convert the input to lowercase for easier keyword matching
INPUT_QUERY=$(echo "$1" | tr '[:upper:]' '[:lower:]')

# --- Default DQL Parameters ---
DQL_FETCH="logs"
DQL_CLUSTER=""
DQL_LIMIT=10
DQL_FILTER=""
DQL_SUMMARIZE=""

# --- 1. Extract the Data Source (Intent) ---
if [[ "$INPUT_QUERY" == *"metric"* ]]; then
    DQL_FETCH="metrics"
elif [[ "$INPUT_QUERY" == *"span"* ]] || [[ "$INPUT_QUERY" == *"trace"* ]]; then
    DQL_FETCH="spans"
elif [[ "$INPUT_QUERY" == *"event"* ]]; then
    DQL_FETCH="events"
else
    # Defaulting to logs if unspecified, or if "log" is explicitly mentioned
    DQL_FETCH="logs"
fi

# --- 2. Extract the Cluster Name (Entity Extraction) ---
# Looks for any word immediately preceding the word "cluster"
if [[ "$INPUT_QUERY" =~ ([a-z0-9_-]+)\ cluster ]]; then
    DQL_CLUSTER="${BASH_REMATCH[1]}"
fi

# --- 3. Extract Limits (Modifier Extraction) ---
# Looks for "top X" where X is a number
if [[ "$INPUT_QUERY" =~ top\ ([0-9]+) ]]; then
    DQL_LIMIT="${BASH_REMATCH[1]}"
fi

# --- 4. Extract Conditions (Context Extraction) ---
# Checks for keywords like "failure", "error", or "cpu"
if [[ "$INPUT_QUERY" == *"failure rate"* ]] || [[ "$INPUT_QUERY" == *"error"* ]]; then
    if [ "$DQL_FETCH" == "logs" ]; then
        DQL_FILTER="loglevel == \"ERROR\" OR status == \"error\""
        DQL_SUMMARIZE="| summarize FailureCount = count(), by: {dt.entity.service} | sort FailureCount desc"
    elif [ "$DQL_FETCH" == "spans" ]; then
        DQL_FILTER="span.status == \"ERROR\""
        DQL_SUMMARIZE="| summarize FailureCount = count(), by: {dt.entity.service} | sort FailureCount desc"
    fi
elif [[ "$INPUT_QUERY" == *"cpu"* ]] && [[ "$DQL_FETCH" == "metrics" ]]; then
     DQL_FILTER="metric.key == \"dt.host.cpu.usage\""
     DQL_SUMMARIZE="| summarize AvgCPU = avg(value), by: {dt.entity.host} | sort AvgCPU desc"
fi

# --- 5. Construct the DQL Query ---
DQL_STATEMENT="fetch $DQL_FETCH"

# Append Cluster Filter
if [ -n "$DQL_CLUSTER" ]; then
    DQL_STATEMENT="$DQL_STATEMENT | filter dt.kubernetes.cluster.name == \"$DQL_CLUSTER\""
fi

# Append Context Filters (Errors, CPU, etc.)
if [ -n "$DQL_FILTER" ]; then
    if [ -n "$DQL_CLUSTER" ]; then
        DQL_STATEMENT="$DQL_STATEMENT and ($DQL_FILTER)"
    else
        DQL_STATEMENT="$DQL_STATEMENT | filter $DQL_FILTER"
    fi
fi

# Append Summarize & Sort logic
if [ -n "$DQL_SUMMARIZE" ]; then
    DQL_STATEMENT="$DQL_STATEMENT $DQL_SUMMARIZE"
fi

# Append Limit
DQL_STATEMENT="$DQL_STATEMENT | limit $DQL_LIMIT"

# --- 6. Output Results ---
echo -e "\n🔍 Input Query: \"$1\""
echo -e "⚙️  Parsed Context:"
echo "   - Source : $DQL_FETCH"
echo "   - Cluster: ${DQL_CLUSTER:-None specified}"
echo "   - Limit  : $DQL_LIMIT"
echo -e "\n🚀 Generated DQL Query:"
echo "------------------------------------------------------------------"
echo "$DQL_STATEMENT"
echo -e "------------------------------------------------------------------\n"
