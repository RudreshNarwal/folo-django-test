from django.http import JsonResponse

from . import services
from .models import CreditReport



def register(request):
	if request.method == "POST":
		# Assuming you're receiving JSON data
		data = request.POST
		
		# Call the 3rd party API
		api_response = services.register_with_third_party_api(data)
		
		# Save the response to the database
		CreditReport.objects.create(
			username=data.get("username"),
			document_number=data.get("documentNumber"),
			telephone_mobile=data.get("telephoneMobile"),
			response_code=api_response.get("responseCode"),
			data=api_response.get("data", None),
			message=api_response.get("message")
		)
		
		# Return the API response
		return JsonResponse(api_response)
	else:
		return JsonResponse({"error": "This endpoint only supports POST requests."}, status=405)
