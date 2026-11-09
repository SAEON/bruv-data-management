import factory
from backend.db.schemas import role

class RoleFactory(factory.Factory):
    class Meta:
        model = role

    id = factory.Sequence(lambda n: n)
    name = factory.Faker("name")