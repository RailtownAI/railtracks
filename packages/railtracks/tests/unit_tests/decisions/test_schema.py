"""DecisionSchema: question validation, schema assembly and answers indexed by question."""

import pytest
import railtracks as rt
from railtracks.decisions import (
    Choice,
    ChoiceAnswer,
    DecisionAnswers,
    DecisionSchema,
    Noul,
    Predicate,
    PredicateAnswer,
    SchemaDefinitionError,
    Score,
    ScoreAnswer,
)
from railtracks.decisions.schema import (
    ChoiceQuestion,
    PredicateQuestion,
    ScoreQuestion,
)

DEPARTMENTS = {
    "billing": "Charges, refunds, invoices, or plan changes",
    "technical": "Bugs, outages, errors, or integration problems",
    "sales": "Pricing questions, upgrades, or new purchases",
}
FRUSTRATION = ["Calm", "Frustrated but civil", "Very angry"]

is_urgent = Predicate(name="is_urgent", instructions="The message conveys urgency")
department = Choice(
    name="department", instructions="Which team should handle this", choices=DEPARTMENTS
)
frustration = Score(
    name="frustration",
    instructions="How frustrated the customer is",
    levels=FRUSTRATION,
)
triage = DecisionSchema(predicate=[is_urgent], choice=[department], score=[frustration])


def _answers() -> dict:
    return {
        "is_urgent": PredicateAnswer(probability=0.93),
        "department": ChoiceAnswer(
            choice="technical",
            confidence=0.8,
            probabilities={"billing": 0.02, "technical": 0.88, "sales": 0.1},
        ),
        "frustration": ScoreAnswer(
            score=1.7,
            confidence=0.6,
            probabilities={0: 0.05, 1: 0.2, 2: 0.75},
            legend=dict(enumerate(FRUSTRATION)),
        ),
    }


def test_exported_from_rt_decisions():
    assert rt.decisions.DecisionSchema is DecisionSchema
    assert rt.decisions.DecisionAnswers is DecisionAnswers
    assert rt.decisions.Predicate is PredicateQuestion
    assert rt.decisions.Choice is ChoiceQuestion
    assert rt.decisions.Score is ScoreQuestion
    assert rt.decisions.PredicateAnswer is PredicateAnswer
    assert rt.decisions.ChoiceAnswer is ChoiceAnswer
    assert rt.decisions.ScoreAnswer is ScoreAnswer


# ================= Question validation =================


class TestQuestionName:
    @pytest.mark.parametrize("name", ["", "  ", None, 3])
    def test_blank_or_non_string_name_rejected(self, name):
        with pytest.raises(SchemaDefinitionError, match="name"):
            Predicate(name=name, instructions="x")

    def test_name_is_kept(self):
        assert department.name == "department"

    def test_name_is_read_only(self):
        with pytest.raises(AttributeError):
            is_urgent.name = "other"  # type: ignore[misc]


class TestPredicate:
    def test_minimal(self):
        q = Predicate(name="urgent", instructions="Is it urgent?")
        assert q.instructions == "Is it urgent?"
        assert q.kind == "predicate"
        assert q.answer_type is PredicateAnswer

    def test_noul_is_an_alias_of_predicate(self):
        assert Noul is Predicate
        assert isinstance(Noul(name="x", instructions="x"), PredicateQuestion)

    @pytest.mark.parametrize("instructions", ["", "  ", None])
    def test_blank_instructions_rejected(self, instructions):
        with pytest.raises(SchemaDefinitionError, match="instructions"):
            Predicate(name="x", instructions=instructions)

    def test_true_false_criteria_not_accepted(self):
        with pytest.raises(TypeError):
            Noul(name="x", instructions="x", criteria={"true": "y"})  # type: ignore[call-arg]


class TestChoice:
    def test_mapping_keeps_descriptions_in_order(self):
        assert department.choices == DEPARTMENTS
        assert list(department.choices) == ["billing", "technical", "sales"]
        assert department.kind == "choice"

    def test_list_has_no_descriptions(self):
        q = Choice(name="x", instructions="x", choices=["a", "b"])
        assert q.choices == {"a": None, "b": None}

    def test_choices_copied(self):
        choices = dict(DEPARTMENTS)
        q = Choice(name="team", instructions="Which team", choices=choices)
        choices["legal"] = "Contracts"
        assert list(q.choices) == ["billing", "technical", "sales"]

    def test_255_choices_allowed(self):
        choices = [f"label_{i}" for i in range(255)]
        assert len(Choice(name="x", instructions="x", choices=choices).choices) == 255

    @pytest.mark.parametrize(
        "choices, match",
        [
            (["only"], "at least 2"),
            ([f"label_{i}" for i in range(256)], "at most 255"),
            (["a", "a"], "unique"),
            (["a", ""], "non-empty"),
            (["a", 1], "non-empty"),
            ("ab", "list"),
            ({"a": "fine", "b": 2}, "description"),
        ],
        ids=[
            "one",
            "too-many",
            "duplicate",
            "blank",
            "not-a-string",
            "bare-string",
            "bad-description",
        ],
    )
    def test_invalid_choices_rejected(self, choices, match):
        with pytest.raises(SchemaDefinitionError, match=match):
            Choice(name="x", instructions="x", choices=choices)


class TestScore:
    def test_list_levels_in_order(self):
        assert list(frustration.levels) == FRUSTRATION
        assert frustration.kind == "score"

    def test_mapping_keeps_criteria(self):
        q = Score(name="x", instructions="x", levels={"Low": "Fine", "High": "Bad"})
        assert q.levels == {"Low": "Fine", "High": "Bad"}

    def test_levels_copied(self):
        levels = list(FRUSTRATION)
        q = Score(name="x", instructions="How frustrated", levels=levels)
        levels.append("Furious")
        assert list(q.levels) == FRUSTRATION

    @pytest.mark.parametrize("count", [2, 10])
    def test_level_bounds_allowed(self, count):
        q = Score(
            name="x", instructions="x", levels=[f"level {i}" for i in range(count)]
        )
        assert len(q.levels) == count

    @pytest.mark.parametrize(
        "count, match", [(0, "at least 2"), (1, "at least 2"), (11, "at most 10")]
    )
    def test_level_bounds_rejected(self, count, match):
        with pytest.raises(SchemaDefinitionError, match=match):
            Score(
                name="x", instructions="x", levels=[f"level {i}" for i in range(count)]
            )

    @pytest.mark.parametrize(
        "levels, match",
        [("Calm", "list"), (["Calm", ""], "non-empty"), (["Low", "Low"], "unique")],
        ids=["bare-string", "blank", "duplicate"],
    )
    def test_invalid_levels_rejected(self, levels, match):
        with pytest.raises(SchemaDefinitionError, match=match):
            Score(name="x", instructions="x", levels=levels)


# ================= Schema assembly =================


class TestSchema:
    def test_questions_ordered_predicate_choice_score(self):
        schema = DecisionSchema(
            score=[frustration], choice=[department], predicate=[is_urgent]
        )
        assert list(schema.questions) == ["is_urgent", "department", "frustration"]

    def test_list_order_kept_within_a_kind(self):
        spam = Predicate(name="is_spam", instructions="The message is spam")
        schema = DecisionSchema(predicate=[spam, is_urgent])
        assert list(schema.questions) == ["is_spam", "is_urgent"]

    def test_questions_keyed_by_name(self):
        assert triage.questions["department"] is department

    def test_questions_are_read_only(self):
        with pytest.raises(TypeError):
            triage.questions["other"] = is_urgent  # type: ignore[index]

    def test_lists_are_copied(self):
        predicates = [is_urgent]
        schema = DecisionSchema(predicate=predicates)
        predicates.append(Predicate(name="later", instructions="x"))
        assert list(schema.questions) == ["is_urgent"]

    def test_noul_goes_in_the_predicate_list(self):
        spam = Noul(name="is_spam", instructions="The message is spam")
        schema = DecisionSchema(predicate=[spam])
        assert isinstance(schema.questions["is_spam"], PredicateQuestion)

    def test_question_reused_across_schemas(self):
        first = DecisionSchema(predicate=[is_urgent])
        second = DecisionSchema(predicate=[is_urgent], choice=[department])
        assert first.questions["is_urgent"] is second.questions["is_urgent"]
        assert is_urgent.name == "is_urgent"

    def test_empty_schema_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="no questions"):
            DecisionSchema()

    def test_duplicate_names_rejected(self):
        other = Choice(name="is_urgent", instructions="x", choices=["a", "b"])
        with pytest.raises(SchemaDefinitionError, match="is_urgent"):
            DecisionSchema(predicate=[is_urgent], choice=[other])

    def test_same_question_twice_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="is_urgent"):
            DecisionSchema(predicate=[is_urgent, is_urgent])

    @pytest.mark.parametrize(
        "kwargs, wrong",
        [
            ({"predicate": [department]}, "ChoiceQuestion"),
            ({"choice": [is_urgent]}, "PredicateQuestion"),
            ({"score": [department]}, "ChoiceQuestion"),
            ({"predicate": ["is_urgent"]}, "str"),
        ],
        ids=["choice-as-predicate", "predicate-as-choice", "choice-as-score", "str"],
    )
    def test_question_of_the_wrong_kind_rejected(self, kwargs, wrong):
        with pytest.raises(SchemaDefinitionError, match=wrong):
            DecisionSchema(**kwargs)

    @pytest.mark.parametrize("value", [is_urgent, "is_urgent", None])
    def test_list_argument_must_be_a_list(self, value):
        with pytest.raises(SchemaDefinitionError, match="list"):
            DecisionSchema(predicate=value)

    def test_arguments_are_keyword_only(self):
        with pytest.raises(TypeError):
            DecisionSchema([is_urgent])  # type: ignore[misc]

    def test_repr_names_the_questions(self):
        assert repr(triage) == (
            "DecisionSchema(predicate=['is_urgent'], choice=['department'], "
            "score=['frustration'])"
        )


# ================= Answers =================


class TestAnswers:
    def test_index_by_question_or_name(self):
        answers = DecisionAnswers(triage, _answers())
        assert answers[is_urgent].probability == 0.93
        assert answers[department].probabilities["technical"] == 0.88
        assert answers[frustration].legend[2] == "Very angry"
        assert answers["department"] is answers[department]

    def test_question_outside_the_schema_raises_key_error(self):
        answers = DecisionAnswers(triage, _answers())
        lookalike = Predicate(name="is_urgent", instructions="x")
        with pytest.raises(KeyError):
            answers[lookalike]
        with pytest.raises(KeyError):
            answers["nope"]

    def test_mapping_protocol_in_schema_order(self):
        answers = DecisionAnswers(triage, _answers())
        assert list(answers) == ["is_urgent", "department", "frustration"]
        assert len(answers) == 3
        assert "is_urgent" in answers and is_urgent in answers
        assert dict(answers.items())["is_urgent"].probability == 0.93
        assert answers.schema is triage

    def test_missing_answer_rejected(self):
        answers = _answers()
        del answers["frustration"]
        with pytest.raises(ValueError, match="frustration"):
            DecisionAnswers(triage, answers)

    def test_unexpected_answer_rejected(self):
        answers = _answers()
        answers["extra"] = PredicateAnswer(probability=0.1)
        with pytest.raises(ValueError, match="extra"):
            DecisionAnswers(triage, answers)

    def test_wrong_answer_type_rejected(self):
        answers = _answers()
        answers["is_urgent"] = answers["department"]
        with pytest.raises(ValueError, match="is_urgent"):
            DecisionAnswers(triage, answers)

    def test_encode_is_plain_json_in_schema_order(self):
        encoded = DecisionAnswers(triage, _answers()).encode()
        assert list(encoded) == ["is_urgent", "department", "frustration"]
        assert encoded["is_urgent"] == {"probability": 0.93}
        assert encoded["frustration"]["legend"] == {
            "0": "Calm",
            "1": "Frustrated but civil",
            "2": "Very angry",
        }

    def test_equality(self):
        assert DecisionAnswers(triage, _answers()) == DecisionAnswers(
            triage, _answers()
        )


# ================= Answer summaries =================


class TestAnswerStr:
    def test_predicate_yes(self):
        assert str(PredicateAnswer(probability=0.93)) == "yes 0.93"

    def test_predicate_no_still_shows_probability(self):
        assert str(PredicateAnswer(probability=0.12)) == "no 0.12"

    def test_predicate_half_is_yes(self):
        assert str(PredicateAnswer(probability=0.5)) == "yes 0.50"

    def test_choice_shows_probability_of_choice(self):
        assert str(_answers()["department"]) == "technical 0.88"

    def test_score_shows_expected_over_max_level(self):
        assert str(_answers()["frustration"]) == "1.7/2"
