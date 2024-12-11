import json
import boto3
import os
from botocore.exceptions import BotoCoreError, ClientError

# Initialize the Step Functions client
stepfunctions_client = boto3.client('stepfunctions')

# The state machine ARN is expected to be set as an environment variable
STATE_MACHINE_ARN = os.getenv('STATE_MACHINE_ARN')

def lambda_handler(event, context):
    """
    Lambda function to invoke a Step Functions state machine.
    :param event: Input event to the Lambda function. Expected to have the "input" key for Step Functions input.
    :param context: Lambda context object.
    :return: Response from Step Functions invocation.
    """
    try:
        # Extract input data for the Step Functions state machine
        step_input = event.get('input', {})
        
        # Generate a unique execution name (e.g., using a timestamp)
        execution_name = f"execution-{context.aws_request_id}"
        
        # Start the Step Functions execution
        response = stepfunctions_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(step_input)
        )
        
        return {
            "statusCode": 200,
            "message": "Step Function invoked successfully",
            "executionArn": response['executionArn']
        }
    
    except (BotoCoreError, ClientError) as error:
        # Handle errors from the Step Functions API
        return {
            "statusCode": 500,
            "message": "Failed to invoke Step Function",
            "error": str(error)
        }
