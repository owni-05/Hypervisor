import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_service():
    # 1. Create a user
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpass123"
    }
    response = requests.post(f"{BASE_URL}/users/", json=user_data)
    print("User Creation:", response.json())

    # 2. Get access token
    token_response = requests.post(
        f"{BASE_URL}/token",
        data={"username": "test@example.com", "password": "testpass123"}
    )
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create an organization
    org_data = {"name": "Test Organization 3"}
    org_response = requests.post(
        f"{BASE_URL}/organizations/",
        headers=headers,
        json=org_data
    )
    org_id = org_response.json()["id"]
    print("Organization Creation:", org_response.json())

    # 4. Create a cluster
    cluster_data = {
        "name": "Test Cluster",
        "organization_id": org_id,
        "total_ram": 32.0,
        "total_cpu": 8.0,
        "total_gpu": 2.0
    }
    cluster_response = requests.post(
        f"{BASE_URL}/clusters/",
        headers=headers,
        json=cluster_data
    )
    cluster_id = cluster_response.json()["id"]
    print("Cluster Creation:", cluster_response.json())

    # 5. Create deployments with different priorities
    deployments = [
        {
            "name": "High Priority Deploy",
            "docker_image": "nginx:latest",
            "cluster_id": cluster_id,
            "priority": 9,
            "required_ram": 4.0,
            "required_cpu": 2.0,
            "required_gpu": 0.0
        },
        {
            "name": "Medium Priority Deploy",
            "docker_image": "redis:latest",
            "cluster_id": cluster_id,
            "priority": 5,
            "required_ram": 2.0,
            "required_cpu": 1.0,
            "required_gpu": 0.0
        }
    ]

    deployment_ids = []
    for deploy in deployments:
        response = requests.post(
            f"{BASE_URL}/deployments/",
            headers=headers,
            json=deploy
        )
        deployment_ids.append(response.json()["id"])
        print(f"Deployment Creation ({deploy['name']}):", response.json())

    # 6. Check queue metrics
    metrics_response = requests.get(
        f"{BASE_URL}/deployments/queue/metrics",
        headers=headers
    )
    print("Queue Metrics:", metrics_response.json())

    # 7. Process deployments
    process_response = requests.post(
        f"{BASE_URL}/clusters/{cluster_id}/process-deployments",
        headers=headers
    )
    print("Process Deployments:", process_response.json())

    # 8. Check cluster resources
    resources_response = requests.get(
        f"{BASE_URL}/clusters/{cluster_id}/resources",
        headers=headers
    )
    print("Cluster Resources:", resources_response.json())

    # 9. Complete a deployment
    if deployment_ids:
        complete_response = requests.post(
            f"{BASE_URL}/deployments/{deployment_ids[0]}/complete",
            headers=headers,
            json={"success_details": {"message": "Deployment completed successfully"}}
        )
        print("Complete Deployment:", complete_response.json())

if __name__ == "__main__":
    test_service()