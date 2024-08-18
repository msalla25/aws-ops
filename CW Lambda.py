# Lambda function for CloudWatch Alarm Trigger
import json
import boto3

def lambda_handler(event, context):
    stepfunctions = boto3.client('stepfunctions')
    
    # Example CloudWatch event parsing. Adjust according to your specific event structure
    alarm_details = event['detail']
    cluster_name = "your-cluster-name"  # Fixed or derived from another source
    service_name = alarm_details['Dimensions'][0]['value']  # Assuming the service name is passed here
    
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
