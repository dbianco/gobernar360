"""Request and response building blocks shared by dashboard modules."""

from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Year = Annotated[int, Field(ge=1900, le=2200)]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PatchModel(BaseModel):
    """Partial update: absent fields are left alone; only `nullable` ones may be set to null."""

    nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def required_fields_are_not_cleared(cls, data: Any) -> Any:
        if isinstance(data, dict):
            cleared = sorted(k for k, v in data.items() if v is None and k not in cls.nullable)
            if cleared:
                raise ValueError(f"{', '.join(cleared)} cannot be null")
        return data
