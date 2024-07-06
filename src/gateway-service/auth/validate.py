import os
import requests

def token(request):
    if not "Authorization" in request.headers:
        return None, ("missing credentials", 401)

    token = request.headers["Authorization"]

    if not token:
        return None, ("missing credentials", 401)

    auth_service_address = os.getenv('AUTH_SERVICE_ADDRESS')
    print(f"Auth Service Address: {auth_service_address}")
    
    if not auth_service_address:
        return None, ("AUTH_SERVICE_ADDRESS environment variable not set", 500)

    response = requests.post(
        f"http://{auth_service_address}/validate",
        headers={"Authorization": token},
    )

    if response.status_code == 200:
        return response.text, None
    else:
        return None, (response.text, response.status_code)
