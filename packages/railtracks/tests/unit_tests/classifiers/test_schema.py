"""TypeSafeSchema: question validation, collection, inheritance and typed answers."""

import pytest
from railtracks.classifiers import SchemaDefinitionError
from railtracks.classifiers.models.system_one.schema import (
    ChoiceAnswer,
    ChoiceQuestion,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
    TypeSafeSchema,
)

DEPARTMENTS = {
    "billing": "Charges, refunds, invoices, or plan changes",
    "technical": "Bugs, outages, errors, or integration problems",
    "sales": "Pricing questions, upgrades, or new purchases",
}
FRUSTRATION = ["Calm", "Frustrated but civil", "Very angry"]


class Triage(TypeSafeSchema):
    is_urgent = TypeSafeSchema.Noul(instructions="The message conveys urgency")
    department = TypeSafeSchema.Choice(
        instructions="Which team should handle this", criteria=DEPARTMENTS
    )
    frustration = TypeSafeSchema.Score(
        instructions="How frustrated the customer is", criteria=FRUSTRATION
    )


def _answers() -> dict:
    return {
        "is_urgent": NoulAnswer(noul=0.93),
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


# ================= Question validation =================


class TestNoul:
    def test_minimal(self):
        q = TypeSafeSchema.Noul(instructions="Is it urgent?")
        assert q.instructions == "Is it urgent?"
        assert q.criteria is None

    def test_true_false_descriptions(self):
        q = TypeSafeSchema.Noul(
            instructions="Repeat contact?",
            criteria={"true": "Mentions a prior ticket", "false": "No prior contact"},
        )
        assert q.criteria == {
            "true": "Mentions a prior ticket",
            "false": "No prior contact",
        }

    def test_unknown_criteria_key_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="maybe"):
            TypeSafeSchema.Noul(instructions="x", criteria={"maybe": "?"})  # type: ignore[typeddict-unknown-key]

    def test_blank_instructions_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="instructions"):
            TypeSafeSchema.Noul(instructions="  ")


class TestChoice:
    def test_criteria_copied(self):
        criteria = dict(DEPARTMENTS)
        q = TypeSafeSchema.Choice(instructions="Which team", criteria=criteria)
        criteria["legal"] = "Contracts"
        assert list(q.criteria) == ["billing", "technical", "sales"]

    def test_fewer_than_two_labels_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="at least 2"):
            TypeSafeSchema.Choice(instructions="x", criteria={"only": "one"})

    def test_255_labels_allowed(self):
        criteria = {f"label_{i}": f"option {i}" for i in range(255)}
        assert (
            len(TypeSafeSchema.Choice(instructions="x", criteria=criteria).criteria)
            == 255
        )

    def test_more_than_255_labels_rejected(self):
        criteria = {f"label_{i}": f"option {i}" for i in range(256)}
        with pytest.raises(SchemaDefinitionError, match="at most 255"):
            TypeSafeSchema.Choice(instructions="x", criteria=criteria)

    def test_blank_label_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="label"):
            TypeSafeSchema.Choice(instructions="x", criteria={"": "a", "b": "b"})


class TestScore:
    def test_levels_copied(self):
        levels = list(FRUSTRATION)
        q = TypeSafeSchema.Score(instructions="How frustrated", criteria=levels)
        levels.append("Furious")
        assert q.criteria == FRUSTRATION

    @pytest.mark.parametrize("count", [2, 10])
    def test_level_bounds_allowed(self, count):
        q = TypeSafeSchema.Score(
            instructions="x", criteria=[f"level {i}" for i in range(count)]
        )
        assert len(q.criteria) == count

    @pytest.mark.parametrize("count", [0, 1, 11])
    def test_level_bounds_rejected(self, count):
        with pytest.raises(SchemaDefinitionError, match="between 2 and 10"):
            TypeSafeSchema.Score(
                instructions="x", criteria=[f"level {i}" for i in range(count)]
            )

    def test_bare_string_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="list"):
            TypeSafeSchema.Score(instructions="x", criteria="Calm")

    def test_blank_level_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="level"):
            TypeSafeSchema.Score(instructions="x", criteria=["Calm", ""])


def test_invalid_question_fails_at_class_definition():
    with pytest.raises(SchemaDefinitionError):

        class Broken(TypeSafeSchema):
            only = TypeSafeSchema.Choice(instructions="x", criteria={"a": "a"})


# ================= Schema collection =================


class TestCollection:
    def test_questions_in_definition_order(self):
        assert list(Triage.__questions__) == ["is_urgent", "department", "frustration"]

    def test_question_records_attribute_name(self):
        assert Triage.__questions__["department"].name == "department"

    def test_class_access_returns_the_question(self):
        assert isinstance(Triage.is_urgent, NoulQuestion)
        assert isinstance(Triage.department, ChoiceQuestion)
        assert isinstance(Triage.frustration, ScoreQuestion)

    def test_subclass_inherits_parent_questions_first(self):
        class Extended(Triage):
            is_spam = TypeSafeSchema.Noul(instructions="The message is spam")

        assert list(Extended.__questions__) == [
            "is_urgent",
            "department",
            "frustration",
            "is_spam",
        ]
        assert list(Triage.__questions__) == ["is_urgent", "department", "frustration"]

    def test_subclass_override_keeps_position(self):
        class Overridden(Triage):
            is_urgent = TypeSafeSchema.Noul(instructions="Needs a reply today")

        assert list(Overridden.__questions__) == [
            "is_urgent",
            "department",
            "frustration",
        ]
        assert Overridden.is_urgent.instructions == "Needs a reply today"

    def test_empty_schema_rejected(self):
        with pytest.raises(SchemaDefinitionError, match="no questions"):

            class Empty(TypeSafeSchema):
                pass

    @pytest.mark.parametrize("name", ["encode", "Noul", "Choice", "Score"])
    def test_name_clash_with_schema_attribute_rejected(self, name):
        with pytest.raises(SchemaDefinitionError, match=name):
            type(
                "Clashing",
                (TypeSafeSchema,),
                {name: TypeSafeSchema.Noul(instructions="x")},
            )

    def test_question_reused_under_two_names_rejected(self):
        shared = TypeSafeSchema.Noul(instructions="x")
        with pytest.raises(SchemaDefinitionError, match="more than one"):

            class Reused(TypeSafeSchema):
                first = shared
                second = shared


# ================= Instances hold the answers =================


class TestInstance:
    def test_instance_access_returns_the_answer(self):
        triage = Triage(_answers())
        assert triage.is_urgent.noul == 0.93
        assert triage.department.probabilities["technical"] == 0.88
        assert triage.frustration.legend[2] == "Very angry"

    def test_missing_answer_rejected(self):
        answers = _answers()
        del answers["frustration"]
        with pytest.raises(ValueError, match="frustration"):
            Triage(answers)

    def test_wrong_answer_type_rejected(self):
        answers = _answers()
        answers["is_urgent"] = answers["department"]
        with pytest.raises(ValueError, match="is_urgent"):
            Triage(answers)

    def test_encode_is_plain_json_in_definition_order(self):
        encoded = Triage(_answers()).encode()
        assert list(encoded) == ["is_urgent", "department", "frustration"]
        assert encoded["is_urgent"] == {"noul": 0.93}
        assert encoded["frustration"]["legend"] == {
            "0": "Calm",
            "1": "Frustrated but civil",
            "2": "Very angry",
        }

    def test_equality(self):
        assert Triage(_answers()) == Triage(_answers())


# ================= Answer summaries =================


class TestAnswerStr:
    def test_noul_yes(self):
        assert str(NoulAnswer(noul=0.93)) == "yes 0.93"

    def test_noul_no_still_shows_p_yes(self):
        assert str(NoulAnswer(noul=0.12)) == "no 0.12"

    def test_noul_half_is_yes(self):
        assert str(NoulAnswer(noul=0.5)) == "yes 0.50"

    def test_choice_shows_probability_of_choice(self):
        assert str(_answers()["department"]) == "technical 0.88"

    def test_score_shows_expected_over_max_level(self):
        assert str(_answers()["frustration"]) == "1.7/2"
