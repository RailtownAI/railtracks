"""TypeSafeSchema: question validation for the Noul, Choice and Score question types."""

import pytest
from railtracks.decisions import SchemaDefinitionError
from railtracks.decisions.models.typesafe_compatible.schema import (
    NoulAnswer,
    TypeSafeSchema,
)

DEPARTMENTS = {
    "billing": "Charges, refunds, invoices, or plan changes",
    "technical": "Bugs, outages, errors, or integration problems",
    "sales": "Pricing questions, upgrades, or new purchases",
}
FRUSTRATION = ["Calm", "Frustrated but civil", "Very angry"]


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


class TestNoulAnswerStr:
    def test_yes(self):
        assert str(NoulAnswer(noul=0.93)) == "yes 0.93"

    def test_no_still_shows_p_yes(self):
        assert str(NoulAnswer(noul=0.12)) == "no 0.12"

    def test_half_is_yes(self):
        assert str(NoulAnswer(noul=0.5)) == "yes 0.50"
