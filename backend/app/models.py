from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field

class Choice(BaseModel):
    slot: str
    level: int=Field(ge=1,le=20)
    kind: str
    value: Any
    parent: str|None=None
    confirmed: bool=False
    note: str=''

class SpellPick(BaseModel):
    id: str=Field(default_factory=lambda:str(uuid4()))
    rule_id: str
    level: int=Field(default=1,ge=1,le=20)
    cast_rank: int=Field(default=1,ge=0,le=10)
    source: str='class'
    mode: Literal['prepared','repertoire','known','focus','innate']='prepared'
    signature: bool=False
    used: bool=False

class ItemPick(BaseModel):
    id: str=Field(default_factory=lambda:str(uuid4()))
    rule_id: str=''
    name: str=''
    count: int=Field(default=1,ge=1,le=99999)
    equipped: bool=False
    kind: str='item'
    values: dict=Field(default_factory=dict)
    runes: list[str]=Field(default_factory=list)
    custom: bool=False
    notes: str=''

class ManualEffect(BaseModel):
    id: str=Field(default_factory=lambda:str(uuid4()))
    label: str=''
    target: str
    value: int=Field(ge=-1000,le=1000)
    type: Literal['item','status','circumstance','untyped','rank']='untyped'
    active: bool=False
    source: str=''
    level: int=Field(default=1,ge=1,le=20)

class Character(BaseModel):
    schema_version: Literal[1]=1
    id: str=Field(default_factory=lambda:str(uuid4()))
    revision: int=0
    name: str=Field(default='Новый персонаж',max_length=200)
    level: int=Field(default=1,ge=1,le=20)
    class_id: str=''
    ancestry_id: str=''
    heritage_id: str=''
    background_id: str=''
    free_archetype: bool=False
    choices: list[Choice]=Field(default_factory=list)
    spells: list[SpellPick]=Field(default_factory=list)
    inventory: list[ItemPick]=Field(default_factory=list)
    effects: list[ManualEffect]=Field(default_factory=list)
    notes: str=''
    tradition: str=''
    rules_version: int|None=None
