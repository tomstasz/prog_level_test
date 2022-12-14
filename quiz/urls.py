from django.urls import path, include
from rest_framework import routers
from .views import QuestionView, QuizView, ResultsViewSet, ResultFormView

router = routers.SimpleRouter()
router.register(r"api/result_list", ResultsViewSet)

app_name = "quiz"

urlpatterns = [
    path("", QuizView.as_view(), name="quiz-view"),
    path("<int:pk>/", QuestionView.as_view(), name="question-view"),
    path("", include(router.urls)),
    path("find/", ResultFormView.as_view(), name="result-view"),
]
