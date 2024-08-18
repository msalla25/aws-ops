import json
import boto3

def lambda_handler(event, context):
    # Extract relevant information from the CloudWatch event
    cluster_name = event['detail']['clusterName']
    service_name = event['detail']['serviceName']
    
    # Initialize Step Functions client
    client = boto3.client('stepfunctions')
    
    # Define input for Step Function execution
    input_data = {
        "ClusterName": cluster_name,
        "ServiceToRestart": service_name
    }
    
    # Start the Step Function execution
    response = client.start_execution(
        stateMachineArn='arn:aws:states:REGION:ACCOUNT_ID:stateMachine:YOUR_STATE_MACHINE_NAME',
        name='cloudwatch-trigger-' + context.aws_request_id,
        input=json.dumps(input_data)
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps('State machine execution started')
    }
