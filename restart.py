import boto3
import time

# Initialize the ECS client
ecs_client = boto3.client('ecs')

def lambda_handler(event, context):
    # Determine if the request is coming from API Gateway or CloudWatch
    if 'body' in event:
        # This is an API Gateway request
        body = json.loads(event['body'])
        cluster_name = body['ClusterName']
        target_service_name = body['ServiceName']
    else:
        # This is a CloudWatch request
        # Assuming CloudWatch event structure
        cluster_name = "your-cluster-name"  # Replace with actual cluster name or derive from event
        target_service_name = event['detail']['Dimensions'][0]['value']  # Replace with correct path to service name

    # Step 1: Check if any service in the cluster is undergoing a deployment
    if not check_cluster_stability(cluster_name):
        print("Cluster is stable. Proceeding with the service restart.")
        
        # Step 2: Restart the specific service
        restart_service(cluster_name, target_service_name)
    else:
        print("A service is currently undergoing deployment. Aborting restart.")

def check_cluster_stability(cluster_name):
    try:
        # Describe all services in the cluster
        paginator = ecs_client.get_paginator('list_services')
        response_iterator = paginator.paginate(cluster=cluster_name)
        
        # Loop through each service to check its status
        for response in response_iterator:
            for service_arn in response['serviceArns']:
                service = ecs_client.describe_services(cluster=cluster_name, services=[service_arn])
                
                for deployment in service['services'][0]['deployments']:
                    if deployment['rolloutState'] != 'COMPLETED':
                        print(f"Service {service_arn} is currently undergoing a deployment.")
                        return True  # Deployment in progress, return True to abort the restart
        
        return False  # No deployment in progress, return False to proceed with the restart

    except Exception as e:
        print(f"Failed to check cluster stability: {str(e)}")
        raise

def restart_service(cluster_name, service_name):
    try:
        # Force a new deployment of the service
        ecs_client.update_service(
            cluster=cluster_name,
            service=service_name,
            forceNewDeployment=True
        )
        
        # Wait for the service to stabilize after deployment
        wait_for_service_stability(cluster_name, service_name)
        
    except Exception as e:
        print(f"Failed to restart service: {str(e)}")
        raise

def wait_for_service_stability(cluster_name, service_name):
    try:
        # Wait until the service is stable
        waiter = ecs_client.get_waiter('services_stable')
        waiter.wait(
            cluster=cluster_name,
            services=[service_name]
        )
        print(f"Service {service_name} has stabilized after the restart.")
    
    except Exception as e:
        print(f"Error while waiting for service to stabilize: {str(e)}")
        raise
