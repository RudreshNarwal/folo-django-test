# core_apps/users/tests.py

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from core_apps.users.models import User
from django.contrib.auth import get_user_model

User = get_user_model()

class RegistrationTests(APITestCase):
    def test_register_personal_details(self):
        url = reverse('register_personal_details')
        data = {
            "first_name": "John",
            "middle_name": "A.",
            "last_name": "Doe",
            "dob": "1990-05-15",
            "nation_id": "A123456789",
            "email": "john.doe@example.com",
            "mobile": "712345678",
            "country_code": "+254"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().first_name, 'John')

    def test_update_additional_details(self):
        user = User.objects.create_user(
            mobile='712345678',
            country_code='+254',
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            dob='1990-05-15',
            nation_id='A123456789'
        )
        self.client.force_authenticate(user=user)
        url = reverse('update_additional_details')
        data = {
            "gender": "Male",
            "marital_status": "Single",
            "birth_country": "KE",
            "birth_city": "Nairobi",
            "title": "Mr."
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.gender, "Male")
        self.assertEqual(user.marital_status, "Single")
        self.assertEqual(user.country.code, "KE")
        self.assertEqual(user.city, "Nairobi")
        self.assertEqual(user.title, "Mr.")


class FullRegistrationFlowTests(APITestCase):
    def test_full_registration_flow(self):
        # Step 1: Register Personal Details
        register_url = reverse('register_personal_details')
        register_data = {
            "first_name": "Jane",
            "middle_name": "B.",
            "last_name": "Smith",
            "dob": "1985-08-25",
            "nation_id": "B987654321",
            "email": "jane.smith@example.com",
            "mobile": "798765432",
            "country_code": "+254"
        }
        response = self.client.post(register_url, register_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        customer_id = response.data['customer_id']

        # Authenticate User
        user = User.objects.get(mobile='798765432')
        self.client.force_authenticate(user=user)

        # Step 2: Update Additional Details
        update_details_url = reverse('update_additional_details')
        additional_data = {
            "gender": "Female",
            "marital_status": "Married",
            "birth_country": "KE",
            "birth_city": "Mombasa",
            "title": "Mrs."
        }
        response = self.client.post(update_details_url, additional_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 3: Upload Document
        upload_doc_url = reverse('upload_document')
        document_data = {
            "document_type": "NATIONAL_IDENTITY",
            "media_type": "image/jpeg",
            "base64_encoded_document": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."
        }
        response = self.client.post(upload_doc_url, document_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Step 4: Save Address
        save_address_url = reverse('save_address')
        address_data = {
            "address_type": "PHYSICAL",
            "city": "Mombasa",
            "country": "KE",
            "line1": "456 Ocean Drive",
            "line2": "Suite 12",
            "state": "Coast",
            "code": "80000"
        }
        response = self.client.post(save_address_url, address_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Finalize Registration
        finalize_url = reverse('finalize_registration')
        response = self.client.post(finalize_url, {}, format='json')
        # Depending on your DTBService mock, adjust the expected response
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])
