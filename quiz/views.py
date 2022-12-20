from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.http import Http404
from django.urls import reverse
from django.views import View
from django.utils.translation import activate
from rest_framework import viewsets

from quiz.models import Question, Quiz, SENIORITY_CHOICES
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
)
from quiz.serializers import QuizSerializer

TIMEZONES = {
    "----": "",
    "Warsaw": "Europe/Warsaw",
    "New York": "America/New_York",
}


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
            prog_lang = form.cleaned_data["prog_language"]
            seniority = form.cleaned_data["seniority"]
            user_name = form.cleaned_data["user_name"]
            email = form.cleaned_data["email"]
            number_of_questions = form.cleaned_data["number_of_questions"]
            quiz = Quiz.objects.create(
                prog_language=prog_lang,
                seniority=seniority,
                user_name=user_name,
                email=email,
                number_of_questions=number_of_questions,
            )
            first_question = Question.objects.filter(
                prog_language=prog_lang, seniority=seniority
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
        try:
            question = Question.objects.get(pk=pk)
        except ObjectDoesNotExist:
            raise Http404("Question not found.")
        if request.session.get("general_score") is None:
            request.session["general_score"] = 0
            request.session["junior_score"] = 0
            request.session["regular_score"] = 0
            request.session["senior_score"] = 0
            request.session["seniority_level"] = question.seniority
        if request.session.get("used_ids") is None:
            request.session["used_ids"] = list()
        used_ids = request.session["used_ids"]
        if pk not in used_ids:
            used_ids.append(pk)
        request.session["used_ids"] = used_ids
        ctx = {}
        answers = question.get_answers()
        ctx["question"] = question
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
            num_in_series = int(quiz.number_of_questions / len(SENIORITY_CHOICES))
            request.session["num_in_series"] = num_in_series
            request.session["max_num_of_questions"] = quiz.number_of_questions
            request.session["current_num_of_questions"] = quiz.number_of_questions
            seniority_level = request.session["seniority_level"]
            request.session["finished_series"] = {1: 0, 2: 0, 3: 0}
        # different question types check
        if question.question_type == "open" or question.question_type == "true/false":
            ans = answers[0].text
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
        request.session["num_in_series"] -= 1
        request.session["current_num_of_questions"] -= 1
        next_question_pk = draw_questions(
            request.session.get("seniority_level"), used_ids=request.session["used_ids"]
        )
        if next_question_pk is None:
            raise Http404("Question not found.")
        next_question = Question.objects.get(pk=next_question_pk)
        # single serie of question ends
        if request.session["num_in_series"] <= 0:
            current_seniority = request.session.get("seniority_level")
            request.session.get("finished_series")[str(current_seniority)] += 1
            results = calculate_score_for_serie(request)
            save_results(results, quiz_pk)
            seniority_change_flag = calculate_if_higher_seniority(request, results)
            if (
                seniority_change_flag
                and request.session["seniority_level"] != len(SENIORITY_CHOICES)
                and request.session.get("finished_series")[str(current_seniority)] == 1
            ):
                request.session["seniority_level"] += 1
                request.session["used_ids"] = list()
            if (
                request.session["seniority_level"] > len(SENIORITY_CHOICES)
                or request.session["current_num_of_questions"] == 0
            ):
                print("Gratulacje - koniec testu!")
                return redirect(reverse("quiz:quiz-view"))
            request.session["num_in_series"] = int(
                request.session["max_num_of_questions"] / len(SENIORITY_CHOICES)
            )
            next_question_pk = draw_questions(
                request.session.get("seniority_level"),
                used_ids=request.session["used_ids"],
            )
            next_question = Question.objects.get(pk=next_question_pk)
            if next_question_pk is None:
                raise Http404("Question not found.")
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
        if "email" in request.POST:
            quiz = Quiz.objects.filter(email=request.POST["email"]).first()
            ctx = calculate_percentage(request, quiz)
            ctx["quiz"] = quiz
        ctx["quiz_form"] = form
        return render(request, "results.html", ctx)
