import random

from quiz.models import Question, Quiz, SENIORITY_CHOICES


def template_choice(question_type):
    if question_type == "multiple choice":
        return "single_question.html"
    if question_type == "open":
        return "single_question_open.html"
    if question_type == "true/false":
        return "boolean_question.html"


def update_score(request):
    request.session["general_score"] += 1
    current_seniority = request.session.get("seniority_level")
    if current_seniority == 1:
        request.session["junior_score"] += 1
    if current_seniority == 2:
        request.session["regular_score"] += 1
    if current_seniority == 3:
        request.session["senior_score"] += 1


def del_session_keys(request):
    """Utility function cleaning session keys
    for local testing purposes"""
    if request.session.get("general_score") is not None:
        del request.session["general_score"]
    if request.session.get("junior_score") is not None:
        del request.session["junior_score"]
    if request.session.get("regular_score") is not None:
        del request.session["regular_score"]
    if request.session.get("senior_score") is not None:
        del request.session["senior_score"]
    if request.session.get("seniority_level") is not None:
        del request.session["seniority_level"]
    if request.session.get("used_ids") is not None:
        del request.session["used_ids"]
    if request.session.get("num_in_series") is not None:
        del request.session["num_in_series"]
    if request.session.get("max_num_of_questions") is not None:
        del request.session["max_num_of_questions"]
    if request.session.get("current_num_of_questions") is not None:
        del request.session["current_num_of_questions"]
    if request.session.get("finished_series") is not None:
        del request.session["finished_series"]
    if request.session.get("used_technologies") is not None:
        del request.session["used_technologies"]
    if request.session.get("categories") is not None:
        del request.session["categories"]
    if request.session.get("technologies") is not None:
        del request.session["technologies"]
    if request.session.get("current_technology") is not None:
        del request.session["current_technology"]
    # if request.session.get("django_timezone") is not None:
    #     del request.session["django_timezone"]
    print("Session clear")


def draw_questions(seniority_level, categories, technology, used_ids):
    ids = list(
        Question.objects.filter(
            seniority=seniority_level, category__in=categories, technology=technology
        )
        .exclude(id__in=used_ids)
        .values_list("pk", flat=True)
    )
    if not ids:
        return
    random.shuffle(ids)
    if len(ids) > 0:
        return ids[0]
    return


def calculate_score_for_serie(request):
    """Prepares dict with number of finished series
    and score for each seniority level"""
    num_of_finished_series = request.session["finished_series"]
    gen_score = request.session.get("general_score")
    scores = dict()
    for k, v in SENIORITY_CHOICES:
        if num_of_finished_series[str(k)] > 0:
            scores[f"{v}_score"] = request.session.get(f"{v}_score")
            scores[f"number_of_{v}_series"] = num_of_finished_series[str(k)]
    scores["general_score"] = gen_score
    return scores


def save_results(results, quiz_pk):
    quiz = Quiz.objects.get(pk=quiz_pk)
    for key, value in results.items():
        vars(quiz)[key] = value
    quiz.save()


def calculate_percentage(request, quiz):
    """Calculate percentage of correct answers
    taking into account number of finished series
    from each seniority level"""
    single_serie_length = quiz.number_of_questions / len(SENIORITY_CHOICES)
    num_of_finished_series = {
        "1": quiz.number_of_junior_series,
        "2": quiz.number_of_regular_series,
        "3": quiz.number_of_senior_series,
    }
    general_multiplayer = 100 / quiz.number_of_questions
    seniority = quiz.seniority
    ctx = {}
    for k, v in SENIORITY_CHOICES:
        if seniority <= k:
            multiplayer = calculate_multiplayer(
                k, num_of_finished_series, single_serie_length
            )
            # vars allows direct operations on object fields values
            ctx[f"{v}_score"] = round(vars(quiz)[f"{v}_score"] * multiplayer, 1)
    ctx["general_score"] = round(quiz.general_score * general_multiplayer, 1)
    return ctx


def calculate_if_higher_seniority(request, results):
    """Calculates single serie punctation to check if certain percentage was achieved"""
    score = 0
    current_seniority = request.session["seniority_level"]
    single_serie_length = int(
        request.session["max_num_of_questions"] / len(SENIORITY_CHOICES)
    )
    num_of_finished_series = request.session["finished_series"]
    for k, v in SENIORITY_CHOICES:
        if k == current_seniority:
            multiplayer = calculate_multiplayer(
                k, num_of_finished_series, single_serie_length
            )
            current_serie_score = results[f"{v}_score"]
    score = current_serie_score * multiplayer
    return True if score >= 66 else False


def calculate_multiplayer(key, num_of_finished_series, single_serie_length):
    """Calculates multiplayer for single serie, or for larger number of series
    if seniority was not changed (first serie result didnt meet the match)"""
    multiplayer = (
        100 / (num_of_finished_series[str(key)] * single_serie_length)
        if num_of_finished_series[str(key)] > 1
        else 100 / single_serie_length
    )
    return multiplayer


def remove_duplicates(data):
    """Makes set out of list from request.session
    to remove potential duplicates in used ids"""
    new_set = set(data)
    return list(new_set)
