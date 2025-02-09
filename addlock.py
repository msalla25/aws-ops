#!/bin/bash

# Exit on any error
set -e

# Get environment variables
SECRET_NAME="${SECRET_NAME}"
REGION="${AWS_DEFAULT_REGION}"
INPUT_FILE="${INPUT_FILE}"
TOKEN_URL="https://api.example.com/oauth/token"  # Replace with your token URL

# Fetch Basic Auth credentials from AWS Secrets Manager
get_secret() {
    SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --region "$REGION" --query SecretString --output text)
    USERNAME=$(echo "$SECRET_JSON" | jq -r .username)
    PASSWORD=$(echo "$SECRET_JSON" | jq -r .password)
}

# Get Bearer token using Basic Authentication
get_bearer_token() {
    ENCODED_CREDS=$(echo -n "$USERNAME:$PASSWORD" | base64)
    
    RESPONSE=$(curl -s -X POST "$TOKEN_URL" \
        -H "Authorization: Basic $ENCODED_CREDS" \
        -H "Content-Type: application/json" \
        -d '{}' )
    
    if echo "$RESPONSE" | jq -e .access_token > /dev/null; then
        BEARER_TOKEN=$(echo "$RESPONSE" | jq -r .access_token)
    else
        echo "Error getting bearer token: $RESPONSE"
        exit 1
    fi
}

# Execute API calls
test_apis() {
    if [[ ! -f "$INPUT_FILE" ]]; then
        echo "Error: Input file not found!"
        exit 1
    fi

    APIS=$(cat "$INPUT_FILE")
    
    echo "$APIS" | jq -c '.[]' | while read -r API; do
        URL=$(echo "$API" | jq -r .url)
        METHOD=$(echo "$API" | jq -r .method)
        BODY=$(echo "$API" | jq -c .body)
        
        RESPONSE=$(curl -s -X "$METHOD" "$URL" \
            -H "Authorization: Bearer $BEARER_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$BODY")
        
        STATUS_CODE=$(echo "$RESPONSE" | jq -r .status_code)
        
        echo "API: $URL | Status Code: $STATUS_CODE"
        echo "Response: $RESPONSE"
    done
}

# Main execution
main() {
    get_secret
    get_bearer_token
    test_apis
}

main
