from django.urls import path
from .views import *
urlpatterns=[
 path('adoptions/',AdoptionListCreateView.as_view()), path('adoptions/<int:pk>/',AdoptionDetailView.as_view()), path('adoptions/<int:pk>/share/',ShareAdoptionView.as_view()), path('adoptions/<int:pk>/photos/',AdoptionPhotoView.as_view()),
 path('adoptions/<int:pk>/apply/',ApplicationCreateView.as_view()), path('adoptions/<int:pk>/help/',HelpOfferCreateView.as_view()), path('adoptions/<int:pk>/history/',StatusHistoryView.as_view()),
 path('adoptions/applications/mine/',MyApplicationsView.as_view()), path('adoptions/shelter/applications/',ShelterApplicationsView.as_view()), path('adoptions/applications/<int:pk>/status/',ApplicationStatusView.as_view()), path('adoptions/shelter/help-offers/',ShelterHelpOffersView.as_view()),
]
