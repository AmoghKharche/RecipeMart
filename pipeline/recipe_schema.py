"""Pydantic models for structured recipe extraction and macro estimates."""
from typing import Literal

from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    name: str
    amount: float | None = None
    unit: Literal["g", "ml", "count"] | None = None
    note: str | None = None


class Recipe(BaseModel):
    title: str = "Recipe"
    servings: float | None = Field(
        default=None,
        description="Baseline number of servings the recipe yields; null if unknown.",
    )
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)

    def baseline_servings(self, default: float = 4.0) -> float:
        if self.servings is not None and self.servings > 0:
            return float(self.servings)
        return default

    def is_insufficient(self) -> bool:
        if not self.ingredients and not self.steps:
            return True
        lower = self.title.lower()
        if len(lower) < 3 and not self.ingredients:
            return True
        return False


class MacroTotals(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class MacroEstimate(BaseModel):
    total: MacroTotals
    per_serving: MacroTotals


def scaled_ingredients(recipe: Recipe, scale_factor: float) -> list[Ingredient]:
    """Return a new ingredient list with numeric amounts multiplied by scale_factor."""
    out: list[Ingredient] = []
    for ing in recipe.ingredients:
        if ing.amount is not None and ing.unit:
            out.append(
                Ingredient(
                    name=ing.name,
                    amount=ing.amount * scale_factor,
                    unit=ing.unit,
                    note=ing.note,
                )
            )
        else:
            out.append(ing.model_copy())
    return out
