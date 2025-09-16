#!/bin/bash

# Configuration
CSV_FILE="input.csv"
TEMPLATE_XML="template.xml"
ENDPOINT_URL="https://your-api-endpoint.com/api/service"
CONTENT_TYPE="application/xml"
DELAY_BETWEEN_CALLS=1 # seconds delay between API calls

# Check if required commands are available
if ! command -v curl &> /dev/null; then
    echo "Error: curl is required but not installed!"
    exit 1
fi

# Check if required files exist
if [ ! -f "$CSV_FILE" ]; then
    echo "Error: CSV file $CSV_FILE not found!"
    exit 1
fi

if [ ! -f "$TEMPLATE_XML" ]; then
    echo "Error: XML template file $TEMPLATE_XML not found!"
    exit 1
fi

# Read the template XML
TEMPLATE_CONTENT=$(cat "$TEMPLATE_XML")
SUCCESS_COUNT=0
FAILURE_COUNT=0

# Function to modify XML attributes
modify_xml() {
    local xml_content="$1"
    local a_value="$2"
    local b_value="$3"
    
    # Replace attribute a (handles both single and double quotes)
    xml_content=$(echo "$xml_content" | sed "s/a=['\"][^'\"]*['\"]/a=\"$a_value\"/g")
    xml_content=$(echo "$xml_content" | sed "s/a=['\"][^'\"]*['\"]/a=\"$a_value\"/g")
    
    # Replace attribute b (handles both single and double quotes)
    xml_content=$(echo "$xml_content" | sed "s/b=['\"][^'\"]*['\"]/b=\"$b_value\"/g")
    xml_content=$(echo "$xml_content" | sed "s/b=['\"][^'\"]*['\"]/b=\"$b_value\"/g")
    
    echo "$xml_content"
}

# Function to make web service call
call_endpoint() {
    local xml_payload="$1"
    local row_num="$2"
    local response
    local http_status
    
    echo "=== Row $row_num: Making API call ==="
    
    # Make the API call using curl with timeout
    response=$(curl -s -S -w "\nHTTP_STATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: $CONTENT_TYPE" \
        -d "$xml_payload" \
        --connect-timeout 30 \
        --max-time 60 \
        "$ENDPOINT_URL" 2>&1)
    
    # Check if curl command succeeded
    if [ $? -ne 0 ]; then
        echo "CURL ERROR: $response"
        return 1
    fi
    
    # Extract HTTP status and response body
    http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d':' -f2 | tr -d '\r')
    response_body=$(echo "$response" | sed '/HTTP_STATUS:/d')
    
    echo "HTTP Status: $http_status"
    echo "Response: $response_body"
    
    # Check if HTTP status indicates success (2xx)
    if [[ "$http_status" =~ ^2[0-9][0-9]$ ]]; then
        echo "✅ SUCCESS: Call completed successfully"
        return 0
    else
        echo "❌ FAILURE: HTTP $http_status"
        return 1
    fi
}

# Main processing loop
echo "Starting web service calls for each row in $CSV_FILE"
echo "Endpoint: $ENDPOINT_URL"
echo "=========================================="

row_number=1
{
    read header # Skip header row
    while IFS=, read -r a_value b_value other_columns
    do
        # Clean up values
        a_value=$(echo "$a_value" | tr -d '\r' | xargs)
        b_value=$(echo "$b_value" | tr -d '\r' | xargs)
        
        echo "Processing row $row_number: a='$a_value', b='$b_value'"
        
        # Modify the XML template with current values
        modified_xml=$(modify_xml "$TEMPLATE_CONTENT" "$a_value" "$b_value")
        
        # Make the web service call
        if call_endpoint "$modified_xml" "$row_number"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            FAILURE_COUNT=$((FAILURE_COUNT + 1))
        fi
        
        row_number=$((row_number + 1))
        
        # Add delay between calls if not last row
        if [ $row_number -le $(wc -l < "$CSV_FILE") ]; then
            sleep $DELAY_BETWEEN_CALLS
        fi
        
        echo "" # Add empty line for readability
        
    done
} < "$CSV_FILE"

echo "=========================================="
echo "Processing completed!"
echo "Successful calls: $SUCCESS_COUNT"
echo "Failed calls: $FAILURE_COUNT"
echo "Total calls: $((SUCCESS_COUNT + FAILURE_COUNT))"