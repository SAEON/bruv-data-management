from pydantic import BaseModel


class RoleCreate(BaseModel):
    name: str


class RoleUpdate(BaseModel):
    name: str
