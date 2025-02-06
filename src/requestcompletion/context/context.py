from pydantic import BaseModel, model_validator


class BaseContext(BaseModel):
    """
    A frozen pydantic data model for context information.
    Subclass this to set up your own context variables, while ensuring immutability.
    """

    class Config:
        frozen = True

    @model_validator(mode="after")
    def check_immutability(self, values):
        # makes sure that the base class has not overwritten `self.Config` and that it is immutable.
        if not (hasattr(self, "Config") and hasattr(self.Config, "frozen") and self.Config.frozen == True):
            raise Exception(
                "Your pydantic `context` must be immutable (ie. must contain a `Config` class with attribute `frozen=True`)"
            )

        return self

    @classmethod
    def from_dict(cls, json_data: dict):
        """
        A special function to handle the conversion of a dictionary into the complete pydantic model for context

        The default implementation is to simply deconstruct the dict, if you need for complex decomposition you should
         implement it
        """
        return cls(**json_data)


class EmptyContext(BaseContext):
    """
    An example class containing an empty context variable
    """

    pass
