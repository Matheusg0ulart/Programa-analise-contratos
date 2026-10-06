from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone

Base = declarative_base()

def get_uuid() -> str:
    return str(uuid.uuid4())

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(String, primary_key=True, default=get_uuid)
    name = Column(String, nullable=False)
    cnpj = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=now_utc)
    
    # Relações
    users = relationship("User", back_populates="company")
    folders = relationship("Folder", back_populates="company")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True, default=get_uuid)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    company_id = Column(String, ForeignKey("companies.id"))
    created_at = Column(DateTime, default=now_utc)
    
    # Relações
    company = relationship("Company", back_populates="users")
    contracts = relationship("Contract", back_populates="uploaded_by_user")

class Folder(Base):
    __tablename__ = 'folders'
    
    id = Column(String, primary_key=True, default=get_uuid)
    name = Column(String, nullable=False)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    created_at = Column(DateTime, default=now_utc)
    
    # Relações
    company = relationship("Company", back_populates="folders")
    contracts = relationship("Contract", back_populates="folder")

class Contract(Base):
    __tablename__ = 'contracts'
    
    id = Column(String, primary_key=True, default=get_uuid)
    filename = Column(String, nullable=False)
    status = Column(String, default="pending") # pending, analyzing, completed, failed
    file_path = Column(String, nullable=True) # Caminho onde o S3/Local gravou
    
    # Relações
    folder_id = Column(String, ForeignKey("folders.id"), nullable=True)
    uploaded_by = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=now_utc)
    
    folder = relationship("Folder", back_populates="contracts")
    uploaded_by_user = relationship("User", back_populates="contracts")
    audit_reports = relationship("AuditReportDB", back_populates="contract")

class AuditReportDB(Base):
    """Guarda o histórico do relatório JSON inteiro para podermos exibir no dashboard depois"""
    __tablename__ = 'audit_reports'
    
    id = Column(String, primary_key=True, default=get_uuid)
    contract_id = Column(String, ForeignKey("contracts.id"))
    session_id = Column(String, nullable=False)
    final_verdict = Column(String)
    overall_risk_score = Column(Integer)
    report_data = Column(JSON) # O JSON inteiro do ConsolidatedAuditReport
    created_at = Column(DateTime, default=now_utc)
    
    contract = relationship("Contract", back_populates="audit_reports")
