import json
import boto3

ecs_client = boto3.client('ecs')

def lambda_handler(event, context):
    try:
        # Parse input from the API Gateway event
        body = json.loads(event['body'])
        cluster = body['cluster']
        service = body['service']  # Only one service per cluster

        # Restart the service in the cluster
        ecs_client.update_service(
            cluster=cluster,
            service=service,
            forceNewDeployment=True
        )
        print(f"Restarted service: {service} in cluster: {cluster}")

        # Return a success response
        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Service {service} restarted successfully in cluster {cluster}'})
        }

    except Exception as e:
        # Return an error response if something goes wrong
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
       

#!/bin/bash

# Configuration
CSV_FILE="input.csv"
TEMPLATE_XML="template.xml"
OUTPUT_FILE="output.txt"

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

# Function to modify XML attributes and minify
modify_xml() {
    local xml_content="$1"
    local a_value="$2"
    local b_value="$3"
    
    # Replace attribute a (handles both single and double quotes)
    xml_content=$(echo "$xml_content" | sed "s/a=['\"][^'\"]*['\"]/a=\"$a_value\"/g")
    
    # Replace attribute b (handles both single and double quotes)
    xml_content=$(echo "$xml_content" | sed "s/b=['\"][^'\"]*['\"]/b=\"$b_value\"/g")
    
    # Minify XML: remove newlines, extra spaces, and trim
    xml_content=$(echo "$xml_content" | tr -d '\n' | tr -s ' ' | sed 's/> </></g' | sed 's/^ *//;s/ *$//')
    
    echo "$xml_content"
}

# Clear output file if it exists
> "$OUTPUT_FILE"

echo "Processing CSV file: $CSV_FILE"
echo "Generating XML payloads to: $OUTPUT_FILE"
echo "=========================================="

# Read CSV and process each row
{
    read header # Skip header row
    row_count=0
    while IFS=, read -r a_value b_value other_columns
    do
        # Remove carriage return characters and trim whitespace
        a_value=$(echo "$a_value" | tr -d '\r' | xargs)
        b_value=$(echo "$b_value" | tr -d '\r' | xargs)
        
        row_count=$((row_count + 1))
        echo "Processing row $row_count: a='$a_value', b='$b_value'"
        
        # Modify the XML template with current values
        modified_xml=$(modify_xml "$TEMPLATE_CONTENT" "$a_value" "$b_value")
        
        # Append to output file
        echo "$modified_xml" >> "$OUTPUT_FILE"
        
    done
} < "$CSV_FILE"

echo "=========================================="
echo "Processing completed!"
echo "Total rows processed: $row_count"
echo "Output written to: $OUTPUT_FILE"

# Display sample of the output
if [ $row_count -gt 0 ]; then
    echo ""
    echo "First 2 lines of output:"
    head -n 2 "$OUTPUT_FILE"
    if [ $row_count -gt 2 ]; then
        echo "..."
    fi
fi

split -l 3500 -a 2 --numeric-suffixes=1 -d your_file_name.txt new_file_name_prefix.
