import requests

def send_verification_code(mobile, code):
    api_url = "https://api.africastalking.com/version1/messaging"
    api_key = "dfb804d5dfe09d5d1f4bd5da2be97ed3e8d1e357fd64c54a40e918d253c66d92"
    username = "folomoney"
    sender_id = "Folo"
    message = f"Your Folo verification code is: {code}"

    headers = {
        "apiKey": api_key,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "username": username,
        "to": mobile,
        "message": message,
        "from": sender_id,
    }

    response = requests.post(api_url, headers=headers, data=data)
    return response.json()  # Assuming the API responds with JSON
