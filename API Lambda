# Lambda function for API Gateway Trigger
import json
import boto3

def lambda_handler(event, context):
    stepfunctions = boto3.client('stepfunctions')
    
    body = json.loads(event['body'])
    cluster_name = body['ClusterName']
    service_name = body['ServiceName']
    
    response = stepfunctions.start_execution(
        stateMachineArn='arn:aws:states:region:account-id:stateMachine:your-state-machine-name',
        input=json.dumps({
            'ClusterName': cluster_name,
            'ServiceName': service_name
        })
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps('Step Function triggered successfully!')
    }
