import os
import json
import boto3
import requests
from base64 import b64encode

# Get environment variables
secret_name = os.environ.get("SECRET_NAME")
region = os.environ.get("AWS_DEFAULT_REGION")

# Initialize AWS Secrets Manager client (uses IAM role from GitLab runner)
secrets_client = boto3.client("secretsmanager", region_name=region)

# Fetch Basic Auth credentials from AWS Secrets Manager
def get_secret():
    response = secrets_client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    return secret["username"], secret["password"]

# Get Bearer token using Basic Authentication
def get_bearer_token(username, password):
    token_url = "https://api.example.com/oauth/token"  # Replace with your token URL
    credentials = f"{username}:{password}"
    encoded_creds = b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_creds}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(token_url, headers=headers, json={})
    response.raise_for_status()  # Raise error if request fails
    return response.json()["access_token"]

# Execute API calls
def test_apis(bearer_token):
    input_file = os.environ.get("INPUT_FILE")
    
    with open(input_file, "r") as f:
        apis = json.load(f)
    
    for api in apis:
        url = api["url"]
        method = api["method"]
        body = api.get("body", {})

        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        response = requests.request(method, url, headers=headers, json=body)
        print(f"API: {url} | Status Code: {response.status_code}")
        print("Response:", response.json())

# Main execution
if __name__ == "__main__":
    try:
        username, password = get_secret()
        bearer_token = get_bearer_token(username, password)
        test_apis(bearer_token)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
