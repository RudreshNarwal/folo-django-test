# urls.py
from django.urls import path
from .views import CountryListView, StateListView, OccupationListView


urlpatterns = [
    path('countries/', CountryListView.as_view(), name='country-list'),
    path('states/', StateListView.as_view(), name='state-list'),
    path('occupations/', OccupationListView.as_view(), name='occupation-list'),
]
