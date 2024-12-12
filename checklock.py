import boto3

def lambda_handler(event, context):
    client = boto3.client('events')

    response = client.put_rule_state(
        RuleName='your_rule_name',
        State='ENABLED'
    )

    # Optionally, trigger the rule immediately with an event
    response = client.put_targets(
        Rule='your_rule_name',
        Entries=[
            {
                'Id': '1',
                'Arn': 'arn:aws:lambda:us-east-1:123456789012:function:your_target_lambda'
            }
        ]
    )

    return {
        'statusCode': 200,
        'body': 'EventBridge rule triggered successfully'
    }

