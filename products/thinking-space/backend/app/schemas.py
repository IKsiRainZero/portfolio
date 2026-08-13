from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LayerResponse(BaseModel):
    id: str
    dimension_id: str
    name: str
    level: int
    description: str
    entry_count: int = 0
    model_config = {"from_attributes": True}

class DimensionResponse(BaseModel):
    id: str
    name: str
    description: str
    sort_order: int
    layers: list[LayerResponse] = []
    model_config = {"from_attributes": True}

class EntryCreate(BaseModel):
    title: str
    content: str = ""
    entry_type: str = "known"
    layer_id: Optional[str] = None
    dimension_id: str
    source_type: str = "manual"
    source_link: str = ""
    tags: list[str] = []
    confidence: int = 100
    x: float = 0.0
    y: float = 0.0
    width: float = 200.0
    height: float = 120.0
    z_depth: float = 0.0
    tag_ids: list[str] = []

class EntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    entry_type: Optional[str] = None
    layer_id: Optional[str] = None
    source_link: Optional[str] = None
    tags: Optional[list[str]] = None
    confidence: Optional[int] = None
    z_depth: Optional[float] = None
    tag_ids: Optional[list[str]] = None

class EntryGeometryUpdate(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    z_depth: Optional[float] = None

class EntryResponse(BaseModel):
    id: str
    title: str
    content: str
    entry_type: str
    layer_id: Optional[str]
    dimension_id: str
    source_type: str
    source_link: str
    status: str
    tags: list
    confidence: int
    x: float
    y: float
    width: float
    height: float
    z_depth: float
    tag_ids: list[str] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class CrossLinkCreate(BaseModel):
    source_entry_id: str
    target_entry_id: str
    relation_type: str = "relates_to"
    note: str = ""

class CrossLinkResponse(BaseModel):
    id: str
    source_entry_id: str
    target_entry_id: str
    relation_type: str
    note: str
    created_at: datetime
    model_config = {"from_attributes": True}

class DiagnoseRequest(BaseModel):
    question: str
    dimension_id: str

class LayerLinkCreate(BaseModel):
    source_layer_id: str
    target_layer_id: str
    relation_type: str = "leads_to"
    note: str = ""

class LayerLinkResponse(BaseModel):
    id: str
    source_layer_id: str
    target_layer_id: str
    relation_type: str
    note: str
    model_config = {"from_attributes": True}

class DimensionCreate(BaseModel):
    name: str
    description: str = ""
    sort_order: int = 0

class DimensionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None

class LayerCreate(BaseModel):
    name: str
    description: str = ""

class LayerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class LayerReorderRequest(BaseModel):
    layer_ids: list[str]
