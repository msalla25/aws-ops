import json
import boto3

# Initialize the ECS client
ecs_client = boto3.client('ecs')

def lambda_handler(event, context):
    # Extract necessary information from the event
    cluster_name = "your-cluster-name"
    service_name = "service-a"  # Adjust this based on the event or setup
    
    # Call the deployment function
    trigger_deployment(cluster_name, service_name)

def trigger_deployment(cluster_name, service_name):
    try:
        # Check if any tasks are in PENDING status
        services = ecs_client.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )

        if any(deployment['status'] == 'PRIMARY' and deployment['desiredCount'] != deployment['runningCount']
               for deployment in services['services'][0]['deployments']):
            print(f"Service {service_name} is currently updating, skipping deployment.")
            return

        # If no deployment is in progress, update the service to trigger a new deployment
        ecs_client.update_service(
            cluster=cluster_name,
            service=service_name,
            forceNewDeployment=True
        )

        # Optionally wait and check service status until it's stable
        wait_for_service_stability(cluster_name, service_name)

    except Exception as e:
        print(f"Failed to trigger deployment: {str(e)}")

def wait_for_service_stability(cluster_name, service_name):
    waiter = ecs_client.get_waiter('services_stable')
    waiter.wait(
        cluster=cluster_name,
        services=[service_name]
    )
    print(f"Service {service_name} has stabilized.")
