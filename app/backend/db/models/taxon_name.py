# """Taxon-name model."""
#
# from sqlalchemy import Column, ForeignKey, Integer, Text, String, Float
# from sqlalchemy.orm import relationship
# from db.database import Base
#
#
# class TaxonName(Base):
#     __tablename__ = "taxon_names"
#
#     id = Column(Integer, primary_key=True, index=True)
#     scientific_name_input = Column(String, nullable=False)
#     name_status = Column(String, nullable=True)
#     accepted_name = Column(String, nullable=True)
#     rank = Column(String, nullable=True)