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
        }