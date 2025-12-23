import pytest
import asyncio
from infrastructure.adapters.cloud.local_cloud_adapter import LocalCloudAdapter

@pytest.mark.asyncio
async def test_local_docker_execution():
    # 1. Initialisation de l'adaptateur
    adapter = LocalCloudAdapter(image_name="benchmark-worker-local")
    
    # 2. Test du Provisioning (Lancement du conteneur)
    instance = await adapter.provision_instance()
    assert "url" in instance
    assert "localhost:8001" in instance["url"]
    
    try:
        # 3. Test d'exécution de code Python
        test_payload = {
            "code": "x = 10\ny = 20\nresult = x + y",
            "language": "python"
        }
        
        response = await adapter.send_task_to_worker(instance["url"], test_payload)
        
        # Vérification des résultats et métriques
        assert response["status"] == "success"
        assert response["captured_state"]["result"] == "30"
        assert "ram" in response
        assert "exec_time" in response
        print(f"\nTest réussi ! RAM utilisée: {response['ram']:.2f} MB")

    finally:
        adapter.terminate_instance(instance["pod_id"])
        print("✅ Conteneur nettoyé.")

if __name__ == "__main__":
    asyncio.run(test_local_docker_execution())