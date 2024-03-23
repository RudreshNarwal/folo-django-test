import requests

def get_access_token():
    """Function to call the external service and get an access token."""
    try:
        response = requests.get(
            'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            headers={
                'Authorization': 'Basic dWt3eUZ3M0VUR283ak54UWlWQ1lBdzc2WEdMRzZLQ0I6UVBCN0VkSlNvaEd6d3FpWQ==',
                # 'Cookie': 'incap_ses_738_2742146=aL8EZxbvOW8ZueHJvug9Cm4A/2UAAAAAYd250UHuQFyc8bkoS6NRUw==; incap_ses_747_2742146=n+V+BxGFcgHADE5CAuddChhO/WUAAAAAIJlMEXtn573UOo0xPj/afg==; visid_incap_2742146=pzQd1+2zRoirtUF7P0eFseSW+mUAAAAAQUIPAAAAAABexnxFkk9ZhIoQs6P5N+5J'
            }
        )
        response.raise_for_status()  # Raises an HTTPError if the response code was unsuccessful
        return response.json().get('access_token'), None
    except requests.exceptions.RequestException as e:
        # Return None and the error
        return None, e