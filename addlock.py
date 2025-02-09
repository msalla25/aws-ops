import os
import json
import boto3
import requests
from base64 import b64encode

# Fetch AWS credentials from GitLab CI variables
aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
secret_name = os.environ.get("SECRET_NAME")
region = os.environ.get("AWS_DEFAULT_REGION")

# Initialize AWS Secrets Manager client
session = boto3.Session(
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=region
)
secrets_client = session.client("secretsmanager")

# Fetch Basic Auth credentials from AWS Secrets Manager
def get_secret():
    response = secrets_client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    return secret["username"], secret["password"]

# Get Bearer token
def get_bearer_token(username, password):
    token_url = "https://api.example.com/oauth/token"  # Replace with your token URL
    credentials = f"{username}:{password}"
    encoded_creds = b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_creds}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(token_url, headers=headers, json={})
    return response.json()["access_token"]

# Execute API calls
def test_apis(bearer_token):
    with open(os.environ.get("INPUT_FILE"), "r") as f:
        apis = json.load(f)
    
    for api in apis:
        url = api["url"]
        method = api["method"]
        body = api["body"]
        
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.request(method, url, headers=headers, json=body)
        print(f"API: {url} | Status Code: {response.status_code}")
        print("Response:", response.json())

# Main flow
if __name__ == "__main__":
    username, password = get_secret()
    bearer_token = get_bearer_token(username, password)
    test_apis(bearer_token)