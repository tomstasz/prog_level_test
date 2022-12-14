import threading
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.urls import reverse
from django.views import View
from django.utils.translation import activate
from django.utils.html import strip_tags
from rest_framework import viewsets

from quiz.models import Question, Quiz, SENIORITY_CHOICES, Score, Technology
from quiz.forms import QuizForm, UserEmailForm
from quiz.utils import (
    template_choice,
    update_score,
    del_session_keys,
    draw_questions,
    calculate_score_for_serie,
    save_results,
    calculate_percentage,
    calculate_if_higher_seniority,
    store_used_ids,
    check_if_current_pk_used,
    prepare_session_scores,
)
from quiz.serializers import QuizSerializer

TIMEZONES = {
    "----": "",
    "Warsaw": "Europe/Warsaw",
    "New York": "America/New_York",
}

MAX_SENIORITY_LEVEL = len(SENIORITY_CHOICES)


class QuizView(View):
    def get(self, request):
        form = QuizForm()
        del_session_keys(request)
        return render(
            request, "index.html", {"quiz_form": form, "timezones": TIMEZONES}
        )

    def post(self, request):
        ctx = {}
        if (
            "timezone" in request.POST
            and request.session.get("django_timezone") != request.POST.get("timezone")
            and not "email" in request.POST
        ):
            request.session["django_timezone"] = request.POST["timezone"]
            return redirect("/")
        form = QuizForm(request.POST)
        if form.is_valid():
            category = form.cleaned_data["category"]
            technology = form.cleaned_data["technology"]
            seniority = form.cleaned_data["seniority"]
            user_name = form.cleaned_data["user_name"]
            email = form.cleaned_data["email"]
            number_of_questions = form.cleaned_data["number_of_questions"]
            quiz = Quiz.objects.create(
                seniority=seniority,
                user_name=user_name,
                email=email,
                number_of_questions=number_of_questions,
            )
            quiz.category.set(category)
            quiz.technology.set(technology)
            for tech in quiz.technology.all():
                Score.objects.create(technology=tech, quiz=quiz)
            first_question = Question.objects.filter(
                category__in=category, technology__in=technology, seniority=seniority
            ).first()
            if first_question is None:
                raise Http404("Question not found.")
            ctx["first_question_pk"] = first_question.pk
            ctx["quiz_pk"] = quiz.pk
        form = QuizForm()
        ctx["quiz_form"] = form
        ctx["timezones"] = TIMEZONES
        return render(request, "index.html", ctx)


class QuestionView(View):
    def get(self, request, pk):
        question = get_object_or_404(Question, pk=pk)
        if request.session.get("general_score") is None:
            prepare_session_scores(request)
            request.session["starting_seniority_level"] = question.seniority
            request.session["seniority_level"] = question.seniority
        if request.session.get("used_ids") is None:
            request.session["used_ids"] = list()
        check_if_current_pk_used(request, pk)
        ctx = {}
        answers = question.get_answers()
        ctx["question"] = question
        ctx["time"] = question.time
        if question.question_type == "multiple choice":
            ctx["answers"] = list(answers)
        template = template_choice(question.question_type)
        return render(request, template, ctx)

    def post(self, request, pk):
        question = Question.objects.get(pk=pk)
        answers = question.get_answers()
        quiz_pk = request.GET.get("q")
        if request.session.get("num_in_series") is None:
            quiz = Quiz.objects.get(pk=quiz_pk)
            num_in_series = int(quiz.number_of_questions / MAX_SENIORITY_LEVEL)
            request.session["num_in_series"] = num_in_series
            request.session["max_num_of_questions"] = quiz.number_of_questions
            request.session["current_num_of_questions"] = quiz.number_of_questions
            request.session["used_technologies"] = {}
            request.session["categories"] = [
                category.id for category in quiz.category.all()
            ]
            request.session["technologies"] = [
                technology.id for technology in quiz.technology.all()
            ]
            request.session["current_technology"] = question.technology.id
        # different question types check
        if question.question_type == "open" or question.question_type == "true/false":
            ans = strip_tags(answers[0].text)
            user_answer = request.POST.get("ans")
            if ans == user_answer:
                update_score(request)
        if question.question_type == "multiple choice":
            data = list(request.POST)
            data.remove("csrfmiddlewaretoken")
            data.sort()
            correct_answers_ids = [
                str(ans.pk) for ans in answers if ans.is_correct == True
            ]
            correct_answers_ids.sort()
            if data == correct_answers_ids:
                update_score(request)
        if (
            len(request.session["used_ids"]) % int(request.session["num_in_series"])
            == 0
        ):  # single serie of questions ends
            current_seniority = request.session.get("seniority_level")
            current_technology = request.session.get("current_technology")
            store_used_ids(request, current_technology)
            with threading.Lock():
                request.session.get("finished_series")[str(current_seniority)] += 1
            results = calculate_score_for_serie(request)
            save_results(results, quiz_pk, current_technology)
            seniority_change_flag = calculate_if_higher_seniority(request, results)
            current_seniority_finished_series = request.session.get("finished_series")[
                str(current_seniority)
            ]
            higher_seniority_finished_series = (
                request.session.get("finished_series")[str(current_seniority + 1)]
                if current_seniority != MAX_SENIORITY_LEVEL
                else 0
            )
            if (  # Upgrade seniority
                seniority_change_flag
                and current_seniority != MAX_SENIORITY_LEVEL
                and current_seniority_finished_series == 1
                and higher_seniority_finished_series == 0
            ):
                with threading.Lock():
                    request.session["seniority_level"] += 1
                request.session["used_ids"] = request.session.get("used_technologies")[
                    str(current_technology)
                ]
            if (
                not seniority_change_flag and current_seniority != 1
            ):  # Downgrade seniority
                with threading.Lock():
                    request.session["seniority_level"] -= 1
                request.session["used_ids"] = request.session.get("used_technologies")[
                    str(current_technology)
                ]
            if (  # Technology is finished
                request.session["max_num_of_questions"]
                - len(request.session["used_ids"])
                <= 0
            ):
                request.session["previous_technology"] = current_technology
                request.session["technologies"].remove(current_technology)
                if len(request.session["technologies"]) == 0:  #  Quiz is finished
                    return redirect(reverse("quiz:quiz-view"))
                else:
                    request.session["current_technology"] = request.session[
                        "technologies"
                    ][
                        0
                    ]  # We take next technology in list and make it current
                    request.session["seniority_level"] = request.session[
                        "starting_seniority_level"
                    ]
                    request.session["used_ids"] = list()
                    prepare_session_scores(request)
            request.session["num_in_series"] = int(
                request.session["max_num_of_questions"] / MAX_SENIORITY_LEVEL
            )
        next_question_pk = draw_questions(
            seniority_level=request.session.get("seniority_level"),
            categories=request.session.get("categories"),
            technology=request.session.get("current_technology"),
            used_ids=request.session.get("used_ids"),
        )
        next_question = get_object_or_404(Question, pk=next_question_pk)
        return redirect(
            reverse("quiz:question-view", kwargs={"pk": next_question_pk})
            + f"?q={quiz_pk}"
        )


class ResultsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer


class ResultFormView(View):
    def get(self, request):
        form = UserEmailForm()
        return render(request, "results.html", {"quiz_form": form})

    def post(self, request):
        form = UserEmailForm()
        ctx = {}
        if "email" in request.POST:
            quiz = Quiz.objects.filter(email=request.POST["email"]).first()
            ctx["results"] = calculate_percentage(request, quiz)
            ctx["quiz"] = quiz
        ctx["quiz_form"] = form
        for k, v in SENIORITY_CHOICES:
            if k == quiz.seniority:
                ctx["seniority"] = v
        return render(request, "results.html", ctx)
