from pydantic import BaseModel


class ManifestoPolicyResponse(BaseModel):
    category: str
    title: str
    description: str
    priority: str
    target_personas: list[str]


class PartyManifestoResponse(BaseModel):
    party_id: str
    party_name: str
    policies: list[ManifestoPolicyResponse]


class IssueCategoryCount(BaseModel):
    category: str
    category_name: str
    party_count: int
    total_policies: int


class ManifestoSummaryResponse(BaseModel):
    total_parties: int
    total_categories: int
    total_policies: int
    parties: list[PartyManifestoResponse]
    persona_party_alignment: dict[str, dict[str, float]]
    persona_names: dict[str, str]
    issue_category_breakdown: list[IssueCategoryCount]
    policy_comparison_matrix: dict[str, dict[str, str]]
