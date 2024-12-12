import boto3

def lambda_handler(event, context):
    step_function_arn = event['stepFunctionArn']

    client = boto3.client('stepfunctions')

    response = client.start_execution(
        stateMachineArn=step_function_arn
    )

    return {
        'statusCode': 200,
        'body': f"Step Function execution started: {response['executionArn']}"
    }
