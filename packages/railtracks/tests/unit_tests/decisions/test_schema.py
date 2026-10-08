"""DecisionSchema: question validation, collection, inheritance and typed answers."""

import pytest
import railtracks as rt
from railtracks.decisions import (
    ChoiceAnswer,
    DecisionSchema,
    PredicateAnswer,
    SchemaDefinitionError,
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


class Triage(DecisionSchema):
    is_urgent = DecisionSchema.Predicate(instructions="The message conveys urgency")
    department = DecisionSchema.Choice(
        instructions="Which team should handle this", choices=DEPARTMENTS
    )
    frustration = DecisionSchema.Score(
        instructions="How frustrated the customer is", levels=FRUSTRATION
    )


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
    assert rt.decisions.PredicateAnswer is PredicateAnswer
    assert rt.decisions.ChoiceAnswer is ChoiceAnswer
    assert rt.decisions.ScoreAnswer is ScoreAnswer


# ================= Question validation =================


class TestPredicate:
    def test_minimal(self):
        q = DecisionSchema.Predicate(instructions="Is it urgent?")
        assert q.instructions == "Is it urgent?"
        assert q.kind == "predicate"
        assert q.answer_type is PredicateAnswer

    def test_noul_is_an_alias_of_predicate(self):
        assert DecisionSchema.Noul is DecisionSchema.Predicate
        assert isinstance(DecisionSchema.Noul(instructions="x"), PredicateQuestion)

    @pytest.mark.parametrize("instructions", ["", "  ", None])
    def test_blank_instructions_rejected(self, instructions):
        with pytest.raises(SchemaDefinitionError, match="instructions"):
            DecisionSchema.Predicate(instructions=instructions)

    def test_true_false_criteria_not_accepted(self):
        with pytest.raises(TypeError):
            DecisionSchema.Noul(instructions="x", criteria={"true": "y"})  # type: ignore[call-arg]


class TestChoice:
    def test_mapping_keeps_descriptions_in_order(self):
        q = DecisionSchema.Choice(instructions="Which team", choices=DEPARTMENTS)
        assert q.choices == DEPARTMENTS
        assert list(q.choices) == ["billing", "technical", "sales"]
        assert q.kind == "choice"

    def test_list_has_no_descriptions(self):
        q = DecisionSchema.Choice(instructions="x", choices=["a", "b"])
        assert q.choices == {"a": None, "b": None}

    def test_choices_copied(self):
        choices = dict(DEPARTMENTS)
        q = DecisionSchema.Choice(instructions="Which team", choices=choices)
        choices["legal"] = "Contracts"
        assert list(q.choices) == ["billing", "technical", "sales"]

    def test_255_choices_allowed(self):
        choices = [f"label_{i}" for i in range(255)]
        assert (
            len(DecisionSchema.Choice(instructions="x", choices=choices).choices) == 255
        )

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
            DecisionSchema.Choice(instructions="x", choices=choices)


class TestScore:
    def test_list_levels_in_order(self):
        q = DecisionSchema.Score(instructions="How frustrated", levels=FRUSTRATION)
        assert list(q.levels) == FRUSTRATION
        assert q.kind == "score"

    def test_mapping_keeps_criteria(self):
        q = DecisionSchema.Score(
            instructions="x", levels={"Low": "Fine", "High": "Bad"}
        )
        assert q.levels == {"Low": "Fine", "High": "Bad"}

    def test_levels_copied(self):
        levels = list(FRUSTRATION)
        q = DecisionSchema.Score(instructions="How frustrated", levels=levels)
        levels.append("Furious")
        assert list(q.levels) == FRUSTRATION

    @pytest.mark.parametrize("count", [2, 10])
    def test_level_bounds_allowed(self, count):
        q = DecisionSchema.Score(
            instructions="x", levels=[f"level {i}" for i in range(count)]
        )
        assert len(q.levels) == count

    @pytest.mark.parametrize(
        "count, match", [(0, "at least 2"), (1, "at least 2"), (11, "at most 10")]
    )
    def test_level_bounds_rejected(self, count, match):
        with pytest.raises(SchemaDefinitionError, match=match):
            DecisionSchema.Score(
                instructions="x", levels=[f"level {i}" for i in range(count)]
            )

    @pytest.mark.parametrize(
        "levels, match",
        [("Calm", "list"), (["Calm", ""], "non-empty"), (["Low", "Low"], "unique")],
        ids=["bare-string", "blank", "duplicate"],
    )
    def test_invalid_levels_rejected(self, levels, match):
        with pytest.raises(SchemaDefinitionError, match=match):
            DecisionSchema.Score(instructions="x", levels=levels)


def test_invalid_question_fails_at_class_definition():
    with pytest.raises(SchemaDefinitionError):

        class Broken(DecisionSchema):
            only = DecisionSchema.Choice(instructions="x", choices=["a"])


# ================= Schema collection =================


class TestCollection:
    def test_questions_in_definition_order(self):
        assert list(Triage.__questions__) == ["is_urgent", "department", "frustration"]

    def test_question_records_attribute_name(self):
        assert Triage.__questions__["department"].name == "department"

    def test_class_access_returns_the_question(self):
        assert isinstance(Triage.is_urgent, PredicateQuestion)
        assert isinstance(Triage.department, ChoiceQuestion)
        assert isinstance(Triage.frustration, ScoreQuestion)

    def test_noul_declares_a_predicate(self):
        class Spam(DecisionSchema):
            is_spam = DecisionSchema.Noul(instructions="The message is spam")

        assert isinstance(Spam.is_spam, PredicateQuestion)
        assert (
            Spam({"is_spam": PredicateAnswer(probability=0.2)}).is_spam.probability
            == 0.2
        )

    def test_subclass_inherits_parent_questions_first(self):
        class Extended(Triage):
            is_spam = DecisionSchema.Predicate(instructions="The message is spam")

        assert list(Extended.__questions__) == [
            "is_urgent",
            "department",
            "frustration",
            "is_spam",
        ]
        assert list(Triage.__questions__) == ["is_urgent", "department", "frustration"]

    def test_subclass_override_keeps_position(self):
        class Overridden(Triage):
            is_urgent = DecisionSchema.Predicate(instructions="Needs a reply today")

        assert list(Overridden.__questions__) == [
            "is_urgent",
            "department",
            "frustration",
        ]
        assert Overridden.is_urgent.instructions == "Needs a reply today"

    def test_empty_schema_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="no questions"):

            class Empty(DecisionSchema):
                pass

    @pytest.mark.parametrize("name", ["encode", "Predicate", "Noul", "Choice", "Score"])
    def test_name_clash_with_schema_attribute_rejected(self, name):
        with pytest.raises(SchemaDefinitionError, match=name):
            type(
                "Clashing",
                (DecisionSchema,),
                {name: DecisionSchema.Predicate(instructions="x")},
            )

    def test_question_reused_under_two_names_rejected(self):
        shared = DecisionSchema.Predicate(instructions="x")
        with pytest.raises(SchemaDefinitionError, match="more than one"):

            class Reused(DecisionSchema):
                first = shared
                second = shared

    def test_question_reused_in_another_schema_leaves_the_first_intact(self):
        shared = DecisionSchema.Predicate(instructions="x")

        class First(DecisionSchema):
            is_urgent = shared

        with pytest.raises(SchemaDefinitionError, match="First.is_urgent"):

            class Second(DecisionSchema):
                urgent = shared

        assert First.is_urgent.name == "is_urgent"
        first = First({"is_urgent": PredicateAnswer(probability=0.9)})
        assert first.is_urgent.probability == 0.9


# ================= Instances hold the answers =================


class TestInstance:
    def test_instance_access_returns_the_answer(self):
        triage = Triage(_answers())
        assert triage.is_urgent.probability == 0.93
        assert triage.department.probabilities["technical"] == 0.88
        assert triage.frustration.legend[2] == "Very angry"

    def test_missing_answer_rejected(self):
        answers = _answers()
        del answers["frustration"]
        with pytest.raises(ValueError, match="frustration"):
            Triage(answers)

    def test_unexpected_answer_rejected(self):
        answers = _answers()
        answers["extra"] = PredicateAnswer(probability=0.1)
        with pytest.raises(ValueError, match="extra"):
            Triage(answers)

    def test_wrong_answer_type_rejected(self):
        answers = _answers()
        answers["is_urgent"] = answers["department"]
        with pytest.raises(ValueError, match="is_urgent"):
            Triage(answers)

    def test_encode_is_plain_json_in_definition_order(self):
        encoded = Triage(_answers()).encode()
        assert list(encoded) == ["is_urgent", "department", "frustration"]
        assert encoded["is_urgent"] == {"probability": 0.93}
        assert encoded["frustration"]["legend"] == {
            "0": "Calm",
            "1": "Frustrated but civil",
            "2": "Very angry",
        }

    def test_equality(self):
        assert Triage(_answers()) == Triage(_answers())


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
